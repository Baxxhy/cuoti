import importlib
import socket
from datetime import datetime, timezone
from typing import Annotated

import pytest
from cuoti_backend.config import Settings
from cuoti_backend.database import Database, get_session
from cuoti_backend.main import create_app
from cuoti_backend.protocol import ApiError, envelope
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import OperationalError


@pytest.fixture
def app():
    return create_app(Settings())


def test_live_without_database(app):
    with TestClient(app) as client:
        response = client.get("/livez")
        assert response.json()["service"] == "cuoti-python"
        assert response.headers["x-request-id"]
        assert client.get("/readyz").status_code == 503


def test_readiness_and_database_failure(app, monkeypatch):
    monkeypatch.setattr(app.state.database, "probe", lambda: None)
    with TestClient(app) as client:
        assert client.get("/readyz").json()["status"] == "database_ready"

        def fail():
            raise OperationalError("secret-sql", {}, Exception("secret-password"))

        monkeypatch.setattr(app.state.database, "probe", fail)
        response = client.get("/readyz")
        assert response.status_code == 503
        assert "secret" not in response.text


@pytest.mark.parametrize(
    "method,path,status",
    [
        ("POST", "/livez", 405),
        ("HEAD", "/livez", 405),
        ("POST", "/readyz", 405),
        ("GET", "/missing", 404),
        ("GET", "/livez/", 404),
    ],
)
def test_http_boundaries(app, method, path, status):
    with TestClient(app) as client:
        response = client.request(method, path)
        assert response.status_code == status
        if method == "HEAD":
            assert response.content == b""
        else:
            assert isinstance(response.json()["detail"], str)
        if status == 405:
            assert response.headers["allow"] == "GET"


def test_response_types_and_request_id(app):
    @app.get("/api/test")
    def sample(request: Request):
        return envelope(
            request,
            {
                "empty": None,
                "flag": False,
                "number": 2,
                "fraction": 0.5,
                "time": datetime(2026, 11, 16, tzinfo=timezone.utc),
            },
        )

    with TestClient(app) as client:
        response = client.get("/api/test")
        body = response.json()
        assert body["success"] is True and body["error"] is None
        assert body["data"] == {
            "empty": None,
            "flag": False,
            "number": 2,
            "fraction": 0.5,
            "time": "2026-11-16T00:00:00+00:00",
        }
        assert body["request_id"] == response.headers["x-request-id"]
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/test").headers["x-request-id"] != body["request_id"]


def test_exception_mapping_and_no_secret_logs(app, caplog):
    @app.get("/api/failure/{kind}")
    def failure(kind: str):
        if kind == "business":
            raise ApiError(409, "记录已更新")
        if kind == "database":
            raise OperationalError("secret-sql", {}, Exception("secret-password"))
        raise RuntimeError("secret-password")

    with TestClient(app, raise_server_exceptions=False) as client:
        for kind, status in [("business", 409), ("database", 503), ("unknown", 500)]:
            response = client.get("/api/failure/" + kind)
            assert response.status_code == status
            assert response.headers["x-request-id"]
            assert "secret" not in response.text
    assert "secret-password" not in caplog.text
    assert "secret-sql" not in caplog.text


def test_json_validation(app):
    class Input(BaseModel):
        count: int

    @app.post("/api/input")
    def submit(body: Input):
        return body

    with TestClient(app) as client:
        for data in ["not json", '{"count": "bad"}']:
            response = client.post(
                "/api/input", content=data, headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 422
            assert isinstance(response.json()["detail"], str)


def test_size_limit_including_chunked_body():
    app = create_app(Settings(max_request_bytes=4))
    with TestClient(app) as client:
        response = client.post("/livez", content=iter([b"123", b"456"]))
        assert response.status_code == 413
        assert response.headers["x-request-id"]


def test_configuration_precedence_and_secret(tmp_path, monkeypatch):
    path = tmp_path / ".env.cangjie"
    path.write_text(
        "CANGJIE_DB_NAME=example\nCANGJIE_DB_USER=student\nCANGJIE_DB_PASSWORD='private-value'\n"
    )
    monkeypatch.setenv("CUOTI_ENV_FILE", str(path))
    monkeypatch.setenv("CUOTI_DB_NAME", "override")
    settings = Settings.load()
    assert settings.db_name == "override"
    assert settings.database_url().password == "private-value"
    assert "private-value" not in repr(settings)
    assert "private-value" not in settings.model_dump_json()
    with pytest.raises(ValidationError):
        Settings(port=0)
    with pytest.raises(ValueError):
        Settings().database_url()


def test_session_dependency_closes_on_failure(app):
    from contextlib import contextmanager

    events = []

    @contextmanager
    def session():
        events.append("open")
        try:
            yield object()
        finally:
            events.append("close")

    app.state.database.session = session

    @app.get("/api/session")
    def sample(session: Annotated[object, Depends(get_session)]):
        raise ApiError(409, "测试失败")

    with TestClient(app) as client:
        assert client.get("/api/session").status_code == 409
        assert client.get("/api/session").status_code == 409
    assert events == ["open", "close", "open", "close"]


def test_import_existing_algorithms_without_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("unexpected network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    algorithms = importlib.import_module("cuoti_backend.algorithms")
    original = importlib.import_module("learning_core.services.math_tools")
    assert algorithms.compare_equivalence is original.compare_equivalence
    assert algorithms.compare_equivalence("x+x", "2*x") == (True, True)
    assert callable(algorithms.build_learning_graph)
    assert callable(algorithms.run_learning_workflow)


def test_engine_is_lazy_and_disposed(monkeypatch):
    from sqlalchemy import event

    database = Database(Settings(db_name="unused", db_user="unused"))

    @event.listens_for(database.engine, "do_connect")
    def refuse(*args):
        raise AssertionError("should not connect on creation")

    database.close()


def test_literal_question_routes_preserve_method_precedence(app):
    with TestClient(app) as client:
        for path in ["/api/v1/questions/manual", "/api/v1/questions/ingest"]:
            for method in ["GET", "PATCH", "DELETE"]:
                response = client.request(method, path)
                assert response.status_code == 405
                assert response.headers["allow"] == "POST"


def test_openapi_operation_ids_are_unique():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        schema = create_app(Settings()).openapi()
    operations = [
        operation["operationId"]
        for path in schema["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "patch", "delete", "head", "options"}
    ]
    assert len(operations) == len(set(operations))
