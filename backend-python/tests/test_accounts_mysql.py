import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from cuoti_backend.config import Settings
from cuoti_backend.main import create_app
from cuoti_backend.manage_user import create_admin
from cuoti_backend.models import StudentProfile, User
from cuoti_backend.protocol import ApiError
from cuoti_backend.security import create_token
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        os.environ.get("CUOTI_TEST_MYSQL") != "1",
        reason="local MySQL check not enabled",
    ),
]


@pytest.fixture
def account_app():
    settings = Settings.load()
    app = create_app(settings)
    emails = []

    def email():
        value = "migration-" + uuid4().hex + "@example.test"
        emails.append(value)
        return value

    # Test only newly generated addresses and remove their two account rows.
    with TestClient(app) as client:
        try:
            yield app, client, email
        finally:
            with app.state.database.session() as db, db.begin():
                ids = select(User.id).where(User.email.in_(emails))
                db.execute(
                    delete(StudentProfile).where(StudentProfile.user_id.in_(ids))
                )
                db.execute(delete(User).where(User.email.in_(emails)))


def register(client, email, **extra):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "学生密码 😀", **extra},
    )


def auth(token):
    return {"Authorization": "Bearer " + token}


def test_account_lifecycle_and_existing_password(account_app):
    app, client, email = account_app
    address = email()
    response = register(client, address, role="admin")
    assert response.status_code == 200, response.text
    user = response.json()["data"]
    assert user["role"] == "student" and user["name"] == "智维同学"
    assert "password_hash" not in user and user["created_at"].endswith("+00:00")
    headers = auth(user["access_token"])
    assert (
        client.get("/api/v1/auth/me", headers=headers).json()["data"]["id"]
        == user["id"]
    )
    assert register(client, address).status_code == 409
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": address.upper(), "password": "学生密码 😀"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": address, "password": "wrong"}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get(
            "/api/v1/auth/me", headers=auth(user["access_token"] + "x")
        ).status_code
        == 401
    )
    updated = client.patch(
        "/api/v1/auth/me", headers=headers, json={"name": "新姓名", "grade": "初三"}
    )
    assert updated.status_code == 200 and updated.json()["data"]["name"] == "新姓名"
    assert (
        client.patch(
            "/api/v1/auth/me", headers=headers, json={"role": "admin"}
        ).status_code
        == 422
    )
    new_email = email()
    assert (
        client.patch(
            "/api/v1/auth/me",
            headers=headers,
            json={"email": new_email, "current_password": "wrong"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/auth/me",
            headers=headers,
            json={"email": new_email, "current_password": "学生密码 😀"},
        ).status_code
        == 200
    )
    with app.state.database.session() as db:
        row = db.get(User, user["id"])
        assert row.email == new_email
        old_token = create_token(
            row.id, app.state.settings.auth_secret.get_secret_value(), row.password_hash
        )
    assert client.get("/api/v1/auth/me", headers=auth(old_token)).status_code == 200
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={
                "email": new_email,
                "current_password": "wrong",
                "new_password": "new-password",
            },
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={
                "email": new_email,
                "current_password": "学生密码 😀",
                "new_password": "new-password",
            },
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": new_email, "password": "new-password"}
        ).status_code
        == 200
    )


def test_preferences_permissions_and_version(account_app):
    app, client, email = account_app
    student = register(client, email()).json()["data"]
    other = register(client, email()).json()["data"]
    headers = auth(student["access_token"])
    initial = client.get("/api/v1/student-preferences", headers=headers).json()["data"]
    assert initial == {
        "grade": "初二",
        "subject": "",
        "minutes": 10,
        "goal": "understand",
        "version": 0,
    }
    body = {"subject": "数学", "minutes": 10, "goal": "practice", "version": 0}
    assert (
        client.patch("/api/v1/student-preferences", headers=headers, json=body).json()[
            "data"
        ]["version"]
        == 1
    )
    assert (
        client.patch(
            "/api/v1/student-preferences", headers=headers, json=body
        ).status_code
        == 409
    )
    assert (
        client.get(
            "/api/v1/student-preferences", headers=auth(other["access_token"])
        ).json()["data"]["version"]
        == 0
    )
    for change in [
        {"minutes": True},
        {"subject": "未知"},
        {"goal": "wrong"},
        {"grade": "大学"},
        {"extra": 1},
    ]:
        assert (
            client.patch(
                "/api/v1/student-preferences",
                headers=headers,
                json={**body, "version": 1, **change},
            ).status_code
            == 422
        )
    # Updating profile grade invalidates stale learning-preference versions.
    assert (
        client.patch(
            "/api/v1/auth/me", headers=headers, json={"grade": "初三"}
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/student-preferences", headers=headers).json()["data"][
            "version"
        ]
        == 2
    )
    admin_email = email()
    with app.state.database.session() as db:
        admin = create_admin(
            db,
            app.state.settings,
            {
                "email": admin_email,
                "name": "测试管理员",
                "password": "administrator-pass",
            },
        )
    assert admin["created"]
    admin_token = client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": "administrator-pass"},
    ).json()["data"]["access_token"]
    assert (
        client.get("/api/v1/auth/me", headers=auth(admin_token)).json()["data"]["role"]
        == "admin"
    )
    assert (
        client.get("/api/v1/student-preferences", headers=auth(admin_token)).status_code
        == 403
    )
    with app.state.database.session() as db:
        assert (
            create_admin(
                db,
                app.state.settings,
                {"email": admin_email, "name": "测试管理员", "check_only": True},
            )["available"]
            is False
        )
    with app.state.database.session() as db, pytest.raises(ApiError) as error:
        create_admin(
            db,
            app.state.settings,
            {
                "email": admin_email,
                "name": "测试管理员",
                "password": "administrator-pass",
            },
        )
    assert error.value.status == 409


def test_concurrent_registration_atomicity_and_conflicts(account_app):
    app, client, email = account_app
    address = email()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(lambda _: register(client, address).status_code, range(2))
        )
    assert sorted(results) == [200, 409]
    with app.state.database.session() as db:
        user = db.scalar(select(User).where(User.email == address))
        assert (
            db.scalar(
                select(func.count())
                .select_from(StudentProfile)
                .where(StudentProfile.user_id == user.id)
            )
            == 1
        )
    first = register(client, email()).json()["data"]
    response = client.patch(
        "/api/v1/auth/me",
        headers=auth(first["access_token"]),
        json={"email": address, "current_password": "学生密码 😀", "name": "不应保存"},
    )
    assert response.status_code == 409
    assert (
        client.get("/api/v1/auth/me", headers=auth(first["access_token"])).json()[
            "data"
        ]["name"]
        == first["name"]
    )


def test_registration_rolls_back_when_profile_insert_fails(account_app):
    from sqlalchemy import event

    app, _client, email = account_app
    address = email()

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO student_profiles"):
            raise RuntimeError("synthetic insert failure")

    event.listen(app.state.database.engine, "before_cursor_execute", fail)
    try:
        with TestClient(app, raise_server_exceptions=False) as failure_client:
            assert register(failure_client, address).status_code == 500
    finally:
        event.remove(app.state.database.engine, "before_cursor_execute", fail)
    with app.state.database.session() as db:
        assert db.scalar(select(User).where(User.email == address)) is None


@pytest.mark.parametrize(
    "body",
    [[], None, {"email": "bad", "password": "p"}, {"email": "a@b.c", "password": None}],
)
def test_invalid_registration_body(account_app, body):
    _, client, _ = account_app
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 422


def test_concurrent_preferences_and_method_header(account_app):
    _, client, email = account_app
    student = register(client, email()).json()["data"]
    headers = auth(student["access_token"])
    body = {"subject": "数学", "minutes": 5, "goal": "practice", "version": 0}
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: (
                    client.patch(
                        "/api/v1/student-preferences", headers=headers, json=body
                    ).status_code
                ),
                range(2),
            )
        )
    assert sorted(responses) == [200, 409]
    response = client.delete("/api/v1/auth/me", headers=headers)
    assert response.status_code == 405
    assert set(response.headers["allow"].split(", ")) == {"GET", "PATCH"}


@pytest.mark.skipif(
    not os.environ.get("CUOTI_LEGACY_URL"), reason="legacy comparison not enabled"
)
def test_cross_backend_password_and_tokens(account_app):
    import httpx

    _app, client, email = account_app
    address = email()
    student = register(client, address).json()["data"]
    with httpx.Client(
        base_url=os.environ["CUOTI_LEGACY_URL"], trust_env=False, timeout=10
    ) as legacy:
        before = legacy.get("/livez")
        assert before.status_code == 200
        response = legacy.get("/api/v1/auth/me", headers=auth(student["access_token"]))
        assert response.status_code == 200, response.text
        assert response.json()["data"]["id"] == student["id"]
        original = legacy.post(
            "/api/v1/auth/login", json={"email": address, "password": "学生密码 😀"}
        )
        assert original.status_code == 200
        old_token = original.json()["data"]["access_token"]
        assert client.get("/api/v1/auth/me", headers=auth(old_token)).status_code == 200
        changed = client.post(
            "/api/v1/auth/reset-password",
            json={
                "email": address,
                "current_password": "学生密码 😀",
                "new_password": "changed-by-python",
            },
        )
        assert changed.status_code == 200
        assert legacy.get("/api/v1/auth/me", headers=auth(old_token)).status_code == 401
        assert (
            legacy.post(
                "/api/v1/auth/login",
                json={"email": address, "password": "changed-by-python"},
            ).status_code
            == 200
        )
        # A row and token created by Cangjie are accepted by the new backend.
        legacy_email = email()
        legacy_user = legacy.post(
            "/api/v1/auth/register",
            json={"email": legacy_email, "password": "legacy-password"},
        ).json()["data"]
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": legacy_email, "password": "legacy-password"},
            ).status_code
            == 200
        )
        assert (
            client.get(
                "/api/v1/auth/me", headers=auth(legacy_user["access_token"])
            ).status_code
            == 200
        )
        assert legacy.get("/livez").json() == before.json()
