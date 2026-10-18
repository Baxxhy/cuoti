"""Real Cangjie HTTP + isolated MySQL account regression, called by smoke_cangjie."""

import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4


def request(endpoint, method, path, payload=None, token=None, expected=200, raw=None):
    body = (
        raw
        if raw is not None
        else (json.dumps(payload).encode() if payload is not None else None)
    )
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    try:
        response = urlopen(
            Request(endpoint + path, data=body, headers=headers, method=method),
            timeout=15,
        )
    except HTTPError as error:
        response = error
    with response:
        status = response.status
        assert status in (expected if isinstance(expected, tuple) else (expected,)), (
            path,
            status,
        )
        data = json.load(response)
    if status == 200:
        assert data["success"] is True and data["error"] is None
        UUID(data["request_id"])
        return data["data"]
    assert "password_hash" not in json.dumps(data)
    return status


def b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def python_token(user_id, secret, credential, expires=None):
    claims = {
        "sub": user_id,
        "exp": expires or int(time.time()) + 600,
        "credential": hmac.new(
            secret.encode(), ("credential:v1:" + credential).encode(), hashlib.sha256
        ).hexdigest(),
    }
    payload = b64(json.dumps(claims, separators=(",", ":")).encode())
    return (
        payload
        + "."
        + b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    )


def accounts(endpoint, env):
    assert env["CANGJIE_DB_NAME"].startswith("zhiwei_cangjie_test")
    email = f"cj-{uuid4().hex}@example.test"
    password = "中文密码😀' test"
    payload = {
        "email": email.upper(),
        "password": password,
        "name": "测试同学",
        "grade": "高一",
        "role": "admin",
    }
    user = request(endpoint, "POST", "/api/v1/auth/register", payload)
    assert user["role"] == "student" and user["email"] == email
    assert user["name"] == "测试同学" and "password_hash" not in user
    UUID(user["id"])
    token = user["access_token"]
    me = request(endpoint, "GET", "/api/v1/auth/me", token=token)
    assert me["id"] == user["id"] and me["created_at"].endswith("+00:00")
    request(endpoint, "POST", "/api/v1/auth/register", payload, expected=409)
    request(endpoint, "GET", "/api/v1/auth/me", expected=401)
    request(endpoint, "GET", "/api/v1/auth/me", token=token + "x", expected=401)
    request(
        endpoint,
        "POST",
        "/api/v1/auth/login",
        {"email": email, "password": "wrong"},
        expected=401,
    )
    request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {"email": "bad", "password": "a"},
        expected=422,
    )
    request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {"email": email, "password": 123},
        expected=422,
    )
    request(endpoint, "POST", "/api/v1/auth/login", raw=b"{bad json", expected=422)
    request(endpoint, "POST", "/api/v1/auth/login", raw=b"[]", expected=422)
    request(endpoint, "POST", "/api/v1/auth/login", raw=b"x" * 65537, expected=413)
    request(endpoint, "GET", "/api/v1/auth/login", expected=405)
    changed = request(
        endpoint,
        "PATCH",
        "/api/v1/auth/me",
        {"name": "新名字 ' OR 1=1 --", "role": "admin"},
        token=token,
    )
    assert changed["name"] == "新名字 ' OR 1=1 --" and changed["role"] == "student"
    # Independent read verifies persistence, profile creation, and password format.
    query = (
        "SELECT u.password_hash,p.grade,u.role FROM users u JOIN student_profiles p ON p.user_id=u.id WHERE u.id='"
        + str(UUID(user["id"]))
        + "';"
    )
    mysql_env = {**os.environ, "MYSQL_PWD": env["CANGJIE_DB_PASSWORD"]}
    result = subprocess.run(
        [
            "mysql",
            "--protocol=TCP",
            "-h",
            env["CANGJIE_DB_HOST"],
            "-P",
            env["CANGJIE_DB_PORT"],
            "-u",
            env["CANGJIE_DB_USER"],
            env["CANGJIE_DB_NAME"],
            "-NBe",
            query,
        ],
        env=mysql_env,
        text=True,
        capture_output=True,
        check=True,
    )
    encoded, grade, role = result.stdout.strip().split("\t")
    assert grade == "高一" and role == "student"
    algorithm, salt, digest = encoded.split("$")
    assert algorithm == "pbkdf2_sha256"
    assert hmac.compare_digest(
        base64.urlsafe_b64decode(digest),
        hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.urlsafe_b64decode(salt), 210000
        ),
    )
    token_payload, signature = token.split(".")
    assert hmac.compare_digest(
        signature,
        b64(
            hmac.new(
                env["CANGJIE_AUTH_SECRET"].encode(),
                token_payload.encode(),
                hashlib.sha256,
            ).digest()
        ),
    )
    compatible = python_token(user["id"], env["CANGJIE_AUTH_SECRET"], encoded)
    request(endpoint, "GET", "/api/v1/auth/me", token=compatible)
    expired = python_token(
        user["id"], env["CANGJIE_AUTH_SECRET"], encoded, int(time.time()) - 1
    )
    request(endpoint, "GET", "/api/v1/auth/me", token=expired, expected=401)
    request(
        endpoint,
        "POST",
        "/api/v1/auth/reset-password",
        {"email": email, "current_password": "wrong", "new_password": "new-password"},
        expected=401,
    )
    request(endpoint, "GET", "/api/v1/auth/me", token=token)
    request(
        endpoint,
        "POST",
        "/api/v1/auth/reset-password",
        {"email": email, "current_password": password, "new_password": "新密码😀"},
    )
    request(endpoint, "GET", "/api/v1/auth/me", token=token, expected=401)
    request(endpoint, "GET", "/api/v1/auth/me", token=compatible, expected=401)
    request(
        endpoint,
        "POST",
        "/api/v1/auth/login",
        {"email": email, "password": password},
        expected=401,
    )
    refreshed = request(
        endpoint, "POST", "/api/v1/auth/login", {"email": email, "password": "新密码😀"}
    )
    request(endpoint, "GET", "/api/v1/auth/me", token=refreshed["access_token"])
    race_payload = {
        "email": f"race-{uuid4().hex}@example.test",
        "password": "race-password",
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: request(
                    endpoint,
                    "POST",
                    "/api/v1/auth/register",
                    race_payload,
                    expected=(200, 409),
                ),
                range(2),
            )
        )
    assert (
        sum(isinstance(item, dict) for item in results) == 1 and results.count(409) == 1
    )
    other = next(item for item in results if isinstance(item, dict))
    assert other["id"] != user["id"]
    isolated = request(
        endpoint,
        "PATCH",
        "/api/v1/auth/me",
        {"id": user["id"], "name": "第二个账户", "role": "teacher"},
        token=other["access_token"],
    )
    assert isolated["id"] == other["id"] and isolated["role"] == "student"
    original = request(
        endpoint, "GET", "/api/v1/auth/me", token=refreshed["access_token"]
    )
    assert original["name"] == changed["name"]
    print(
        "Cangjie accounts passed: persistence, Python compatibility, permissions, reset, concurrency"
    )
    return refreshed["access_token"]
