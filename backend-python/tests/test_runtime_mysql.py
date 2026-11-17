import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from cuoti_backend.question_data import execute
from test_questions_mysql import (
    question_app as question_app,  # noqa: PLC0414 -- Export a shared pytest fixture.
)

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        os.environ.get("CUOTI_TEST_MYSQL") != "1",
        reason="local MySQL check not enabled",
    ),
]
ROOT = Path(__file__).resolve().parents[2]


def test_admin_cli_password_stdin_and_duplicate_protection(question_app):
    app, client, student, _ = question_app
    existing, _ = student()
    email = "migration-cli-" + uuid4().hex + "@example.test"
    env = {**os.environ, "CUOTI_PYTHON": sys.executable}

    def command(address, *args, password=None):
        return subprocess.run(
            [
                "bash",
                "scripts/local_user.sh",
                "--email",
                address,
                "--role",
                "admin",
                *args,
            ],
            cwd=ROOT,
            env=env,
            input=password,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )

    try:
        checked = command(email, "--check")
        assert (
            checked.returncode == 0 and json.loads(checked.stdout)["available"] is True
        )
        created = command(
            email, "--password-stdin", password="migration-test-password\n"
        )
        assert created.returncode == 0 and json.loads(created.stdout)["created"] is True
        assert "migration-test-password" not in created.stdout + created.stderr
        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "migration-test-password"},
        )
        assert login.status_code == 200 and login.json()["data"]["role"] == "admin"
        duplicate = command(email, "--password-stdin", password="different-password\n")
        assert duplicate.returncode == 1
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "migration-test-password"},
            ).status_code
            == 200
        )
        protected = command(existing["email"], "--check")
        assert json.loads(protected.stdout)["existing_role"] == "student"
        assert (
            command(
                existing["email"],
                "--password-stdin",
                password="cannot-promote-password\n",
            ).returncode
            == 1
        )
    finally:
        with app.state.database.session() as db, db.begin():
            execute(db, "DELETE FROM users WHERE email=?", [email])
