"""Exercise deployment account creation against real Cangjie and isolated MySQL."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from smoke_cangjie_accounts import request


def local_users(endpoint, env, query):
    project = Path(__file__).resolve().parents[1]
    secret = "LocalIdentity-" + uuid4().hex

    def native(payload, expected=0, raw=None):
        done = subprocess.run(
            ["bash", "scripts/cangjie.sh", "create-user-built"],
            input=(json.dumps(payload) if raw is None else raw) + "\n",
            env=env,
            cwd=project,
            text=True,
            capture_output=True,
            check=False,
        )
        assert done.returncode == expected
        assert secret not in done.stdout + done.stderr
        assert "password_hash" not in done.stdout + done.stderr
        return json.loads(done.stdout)

    counts = query(
        env,
        "SELECT (SELECT COUNT(*) FROM users),(SELECT COUNT(*) FROM student_profiles),(SELECT COUNT(*) FROM cognitive_updates)",
    )
    for role in ("teacher", "guardian", "admin"):
        email = f"local-{role}-{uuid4().hex}@example.test"
        payload = {
            "email": email,
            "role": role,
            "name": "本地角色配置",
            "password": secret,
        }
        before = query(env, "SELECT COUNT(*) FROM users")
        checked = native({**payload, "check_only": True})
        assert checked["available"] is True and checked["created"] is False
        assert query(env, "SELECT COUNT(*) FROM users") == before
        created = native(payload)
        assert created["created"] is True and created["role"] == role
        assert native({**payload, "check_only": True})["existing_role"] == role
        duplicate = native(
            {**payload, "role": "guardian", "password": "different-password"}, 1
        )
        assert duplicate["code"] == 409
        logged = request(
            endpoint,
            "POST",
            "/api/v1/auth/login",
            {"email": email.upper(), "password": secret},
        )
        assert logged["role"] == role
        request(
            endpoint,
            "POST",
            "/api/v1/auth/login",
            {"email": email, "password": "different-password"},
            expected=401,
        )
        route = {
            "teacher": "/teachers/classes",
            "guardian": "/guardians/students",
            "admin": "/admin/workbench",
        }[role]
        request(endpoint, "GET", "/api/v1" + route, token=logged["access_token"])
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM student_profiles WHERE user_id='{created['id']}'",
            )
            == "0"
        )
    student = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"local-student-{uuid4().hex}@example.test",
            "name": "已有学习记录",
            "password": secret,
            "role": "admin",
        },
    )
    assert student["role"] == "student"
    question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "保留的学生题目"},
        token=student["access_token"],
    )
    before = query(
        env, f"SELECT role,password_hash FROM users WHERE id='{student['id']}'"
    )
    native(
        {
            "email": student["email"],
            "name": "不能改角色",
            "role": "admin",
            "password": secret,
        },
        1,
    )
    assert (
        query(env, f"SELECT role,password_hash FROM users WHERE id='{student['id']}'")
        == before
    )
    request(
        endpoint,
        "GET",
        "/api/v1/questions/" + question["id"],
        token=student["access_token"],
    )
    bad = {
        "email": f"bad-{uuid4().hex}@example.test",
        "name": "无效配置",
        "role": "admin",
        "password": secret,
    }
    for delta in (
        {"role": "student"},
        {"role": "root"},
        {"password": "short"},
        {"check_only": "true"},
        {"email": "invalid"},
    ):
        assert native({**bad, **delta}, 1)["code"] == 422
    assert native({}, 1, raw='{"password":"' + secret)["code"] == 422
    race = {**bad, "email": f"race-{uuid4().hex}@example.test"}

    def create(_):
        done = subprocess.run(
            ["bash", "scripts/cangjie.sh", "create-user-built"],
            input=json.dumps(race) + "\n",
            env=env,
            cwd=project,
            text=True,
            capture_output=True,
            check=False,
        )
        assert secret not in done.stdout + done.stderr
        return done.returncode, json.loads(done.stdout)

    with ThreadPoolExecutor(max_workers=2) as pool:
        raced = list(pool.map(create, range(2)))
    assert sorted(row[0] for row in raced) == [0, 1]
    assert sorted(row[1].get("code", 0) for row in raced) == [0, 409]
    # Public wrapper uses stdin for secrets and performs the same native operation.
    wrapper_email = f"wrapper-{uuid4().hex}@example.test"
    cmd = [
        sys.executable,
        "scripts/local_user.py",
        "--email",
        wrapper_email,
        "--role",
        "guardian",
    ]
    check = subprocess.run(
        [*cmd, "--check"],
        env=env,
        cwd=project,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(check.stdout)["available"] is True
    made = subprocess.run(
        [*cmd, "--password-stdin"],
        input=secret + "\n",
        env=env,
        cwd=project,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(made.stdout)["created"] is True
    assert secret not in made.stdout + made.stderr
    assert secret not in check.stdout + check.stderr
    after = query(
        env,
        "SELECT (SELECT COUNT(*) FROM users),(SELECT COUNT(*) FROM student_profiles),(SELECT COUNT(*) FROM cognitive_updates)",
    )
    first = [int(x) for x in counts.split()]
    last = [int(x) for x in after.split()]
    assert last == [first[0] + 6, first[1] + 1, first[2]]
    print(
        "Cangjie local identities passed: native create/check, three roles/login, no overwrite, student record retention, invalid inputs, concurrent email collision and password-stdin wrapper"
    )
