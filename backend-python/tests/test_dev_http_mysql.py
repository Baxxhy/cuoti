import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from cuoti_backend.config import Settings
from test_questions_mysql import (
    question_app as question_app,  # noqa: PLC0414 -- Export a shared pytest fixture.
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.mysql
@pytest.mark.skipif(
    os.environ.get("CUOTI_TEST_DEV_HTTP") != "1",
    reason="actual frontend/backend launcher check not enabled",
)
def test_actual_dev_launcher_proxy_login_and_compute(question_app, tmp_path):
    _, _, student, _ = question_app
    user, _ = student()

    def free_port():
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    backend, frontend = free_port(), free_port()
    env = {
        **os.environ,
        "CUOTI_PYTHON": sys.executable,
        "CUOTI_PORT": str(backend),
        "ZHIWEI_FRONTEND_PORT": str(frontend),
        "CUOTI_MEDIA_ROOT": str(tmp_path / "media"),
        "CUOTI_LEARNING_TASK_WORKER_ENABLED": "false",
    }
    log = (tmp_path / "dev.log").open("w")
    process = subprocess.Popen(
        ["bash", "scripts/final.sh", "start"],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{frontend}", trust_env=False, timeout=10
        ) as client:
            for _ in range(150):
                if process.poll() is not None:
                    pytest.fail("launcher exited; inspect local dev.log")
                try:
                    if client.get("/api/v1/auth/me").status_code == 401:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.2)
            else:
                pytest.fail("frontend proxy/backend startup timed out")
            assert client.get("/").status_code == 200
            login = client.post(
                "/api/v1/auth/login",
                json={"email": user["email"], "password": "test-password"},
            )
            assert login.status_code == 200
            headers = {
                "Authorization": "Bearer " + login.json()["data"]["access_token"]
            }
            q = client.post(
                "/api/v1/questions/manual",
                headers=headers,
                json={"question_text": "3x=15"},
            )
            assert q.status_code == 200
            qid = q.json()["data"]["id"]
            assert (
                client.get("/api/v1/questions/" + qid, headers=headers).json()["data"][
                    "question_text"
                ]
                == "3x=15"
            )
            assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
            ready = httpx.get(f"http://127.0.0.1:{backend}/readyz", trust_env=False)
            assert ready.status_code == 200
            live = httpx.get(f"http://127.0.0.1:{backend}/livez", trust_env=False)
            assert live.json()["service"] == "cuoti-python"
            secret = Settings.load().algorithm_secret.get_secret_value()
            computed = httpx.post(
                f"http://127.0.0.1:{backend}/v1/compute",
                headers={"Authorization": "Bearer " + secret},
                json={"operation": "math_compare", "left": "x+x", "right": "2*x"},
                trust_env=False,
            )
            assert (
                computed.status_code == 200
                and computed.json()["result"]["equivalent"] is True
            )
            check = subprocess.run(
                ["bash", "scripts/final.sh", "check"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            assert check.returncode == 0, check.stdout + check.stderr
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
        process.wait(timeout=25)
        log.close()
    for port in [backend, frontend]:
        with socket.socket() as probe:
            assert probe.connect_ex(("127.0.0.1", port)) != 0
