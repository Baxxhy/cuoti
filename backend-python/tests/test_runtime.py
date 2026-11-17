import importlib.util
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from cuoti_backend.config import Settings
from cuoti_backend.main import create_app
from cuoti_backend.runtime import environment

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def local_config(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(("CUOTI_", "CANGJIE_", "ZHIWEI_")):
            monkeypatch.delenv(key)
    path = tmp_path / ".env.python"
    monkeypatch.setenv("CUOTI_ENV_FILE", str(path))
    return path


def test_legacy_configuration_preserves_identity_media_and_ports(local_config):
    root = local_config.parent
    (root / "backend-cangjie/media").mkdir(parents=True)
    (root / ".runtime").mkdir()
    original = "a" * 64
    (root / ".runtime/cangjie-auth-secret").write_text(original)
    local_config.write_text(
        "CANGJIE_DB_NAME=existing\nCANGJIE_DB_USER=student\nCANGJIE_BACKEND_PORT=8102\nCANGJIE_API_POOL_PATH=/existing/pool.json\n"
    )
    settings = Settings.load()
    assert settings.port == 8102
    assert settings.auth_secret.get_secret_value() == original
    assert settings.media_root == str(root / "backend-cangjie/media")
    env = environment()
    assert env["CUOTI_AUTH_SECRET"] == original
    assert env["CUOTI_API_POOL_PATH"] == "/existing/pool.json"
    assert env["ZHIWEI_BACKEND_URL"] == "http://127.0.0.1:8102"
    assert env["CUOTI_LEARNING_TASK_WORKER_ENABLED"] == "true"
    assert not (root / ".runtime/cuoti-auth-secret").exists()
    generated = root / ".runtime/cuoti-algorithm-secret"
    assert generated.stat().st_mode & 0o777 == 0o600
    assert environment()["CUOTI_ALGORITHM_SECRET"] == env["CUOTI_ALGORITHM_SECRET"]


def test_new_configuration_relative_media_and_explicit_worker(local_config):
    local_config.write_text(
        "CUOTI_DB_NAME=local\nCUOTI_DB_USER=student\nCUOTI_PORT=8202\nCANGJIE_BACKEND_PORT=8102\nCUOTI_MEDIA_ROOT=files\nCUOTI_LEARNING_TASK_WORKER_ENABLED=false\n"
    )
    settings = Settings.load()
    app = create_app(settings)
    assert settings.port == 8202
    assert app.state.media.root == local_config.parent / "files"
    env = environment()
    assert env["CUOTI_LEARNING_TASK_WORKER_ENABLED"] == "false"
    assert len(env["CUOTI_AUTH_SECRET"]) >= 32
    assert environment()["CUOTI_AUTH_SECRET"] == env["CUOTI_AUTH_SECRET"]
    assert not (local_config.parent / "backend-cangjie").exists()


def test_supervisor_owned_process_groups_and_port_conflicts(local_config, tmp_path):
    spec = importlib.util.spec_from_file_location("cuoti_dev", ROOT / "scripts/dev.py")
    dev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dev)
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        with pytest.raises(RuntimeError, match="已被占用"):
            dev.available({"CUOTI_PORT": str(port)}, False)
    with pytest.raises(RuntimeError, match="不能相同"):
        dev.available({"CUOTI_PORT": "8102", "ZHIWEI_FRONTEND_PORT": "8102"}, True)
    # Actual process groups: a sibling's failure must stop the long-running child.
    pidfile = tmp_path / "owned.pid"
    code = (
        "import os,time,pathlib; pathlib.Path("
        + repr(str(pidfile))
        + ").write_text(str(os.getpid())); time.sleep(60)"
    )
    assert (
        dev.supervise(
            [
                [sys.executable, "-c", code],
                [
                    sys.executable,
                    "-c",
                    "import time; time.sleep(0.4); raise SystemExit(7)",
                ],
            ],
            dict(os.environ),
        )
        == 7
    )
    pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_supervisor_signal_cleanup(local_config, tmp_path):
    # A real SIGTERM to the supervisor should clean up only its own subprocesses.
    pidfile = tmp_path / "signal-child.pid"
    source = f"""
import sys
sys.path.insert(0, {str(ROOT / "scripts")!r})
from dev import supervise
raise SystemExit(supervise([[sys.executable, '-c', {("import os,time,pathlib; pathlib.Path(" + repr(str(pidfile)) + ").write_text(str(os.getpid())); time.sleep(60)")!r}]], dict(__import__('os').environ)))
"""
    process = subprocess.Popen([sys.executable, "-c", source], start_new_session=True)
    try:
        for _ in range(100):
            if pidfile.exists():
                break
            if process.poll() is not None:
                pytest.fail("supervisor exited before child started")
            time.sleep(0.05)
        assert pidfile.exists()
        child = int(pidfile.read_text())
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=20) == 0
        with pytest.raises(ProcessLookupError):
            os.kill(child, 0)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=20)


def test_algorithm_configuration_accepts_new_names(local_config, monkeypatch):
    from fastapi.testclient import TestClient
    from service import create_app as algorithm_app

    monkeypatch.setenv("CUOTI_ALGORITHM_SECRET", "new-secret-" * 4)
    monkeypatch.setenv("CANGJIE_ALGORITHM_SECRET", "old-secret-" * 4)
    monkeypatch.setenv("CUOTI_API_POOL_PATH", "/new/configured/pool.json")
    with TestClient(algorithm_app()) as client:
        payload = {"operation": "math_compare", "left": "x+x", "right": "2*x"}
        old = client.post(
            "/v1/compute",
            headers={"Authorization": "Bearer " + "old-secret-" * 4},
            json=payload,
        )
        assert old.status_code == 401
        response = client.post(
            "/v1/compute",
            headers={"Authorization": "Bearer " + "new-secret-" * 4},
            json=payload,
        )
        assert response.status_code == 200 and response.json()["result"]["equivalent"]
    # Retrieval settings are initialized in a new process, as in the real launcher.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import retrieval_compute as r; assert r.settings.qdrant_url=='http://new-qdrant:6333'; assert r.settings.qdrant_collection=='new_questions'",
        ],
        env={
            **os.environ,
            "CUOTI_QDRANT_URL": "http://new-qdrant:6333",
            "CUOTI_QDRANT_COLLECTION": "new_questions",
            "CANGJIE_QDRANT_URL": "http://old-qdrant:6333",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "新检索配置未生效"


@pytest.mark.parametrize("missing", ["version", "table", "column", None])
def test_readiness_requires_existing_schema_without_writing(missing):
    from contextlib import contextmanager

    from cuoti_backend.database import Database
    from cuoti_backend.protocol import ApiError
    from cuoti_backend.question_data import TYPES
    from cuoti_backend.schema import VERSIONS

    class Result:
        def scalars(self):
            return (
                VERSIONS - {"013_bank_grade_index"}
                if missing == "version"
                else VERSIONS
            )

        def __iter__(self):
            for table, fields in TYPES.items():
                if missing == "table" and table == "users":
                    continue
                for field in fields:
                    if (
                        missing == "column"
                        and table == "users"
                        and field == "password_hash"
                    ):
                        continue
                    yield table, field
            yield "historical_extra_table", "id"

    class Session:
        def execute(self, statement):
            assert str(statement).startswith("SELECT")
            return Result()

    @contextmanager
    def session():
        yield Session()

    database = Database(Settings())
    database.session = session
    if missing:
        with pytest.raises(ApiError):
            database.probe()
    else:
        database.probe()


def test_direct_module_loads_file_before_algorithm_import(local_config, monkeypatch):
    monkeypatch.delenv("XIAOJING_API_KEY", raising=False)
    local_config.write_text(
        "CUOTI_ALGORITHM_SECRET="
        + "test-secret-" * 4
        + "\nCUOTI_QDRANT_URL=http://file-qdrant:6333\nCUOTI_QDRANT_COLLECTION=file_questions\nXIAOJING_API_KEY=fixture-key\n"
    )
    source = """
import os, uvicorn

def run(app, **kwargs):
    import retrieval_compute
    assert retrieval_compute.settings.qdrant_url == 'http://file-qdrant:6333'
    assert retrieval_compute.settings.qdrant_collection == 'file_questions'
    assert os.environ['XIAOJING_API_KEY'] == 'fixture-key'
    assert app.state.algorithm_app is not None
uvicorn.run = run
from cuoti_backend.__main__ import main
main()
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        env=dict(os.environ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "配置文件应先于算法模块加载"
