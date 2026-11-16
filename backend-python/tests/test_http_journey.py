"""Opt-in real HTTP and model journey against the local development database."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from cuoti_backend.config import Settings
from cuoti_backend.database import Database
from cuoti_backend.question_data import execute, rows


@pytest.mark.mysql
@pytest.mark.skipif(
    os.environ.get("CUOTI_TEST_HTTP_REAL") != "1",
    reason="real HTTP/model journey explicitly enabled only",
)
def test_real_http_question_journey(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {
        **os.environ,
        "CUOTI_PORT": str(port),
        "CUOTI_MEDIA_ROOT": str(tmp_path / "media"),
    }
    log = (tmp_path / "backend.log").open("w")
    process = subprocess.Popen(
        [sys.executable, "-m", "cuoti_backend"], env=env, stdout=log, stderr=log
    )
    database = Database(Settings.load())
    emails = []
    trace = []
    started = time.perf_counter()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=15
        ) as client:
            for _ in range(100):
                assert process.poll() is None, "backend startup failed"
                try:
                    if client.get("/readyz").status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                time.sleep(0.1)
            else:
                pytest.fail("backend startup timeout")

            def student():
                email = "migration-" + uuid4().hex + "@example.test"
                emails.append(email)
                response = client.post(
                    "/api/v1/auth/register",
                    json={"email": email, "password": "real-http-student"},
                )
                assert response.status_code == 200
                logged = client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": "real-http-student"},
                )
                assert logged.status_code == 200
                return {
                    "Authorization": "Bearer " + logged.json()["data"]["access_token"]
                }

            headers = student()
            other = student()
            trace.append("登录")
            sample = Path(
                os.environ.get(
                    "CUOTI_HTTP_SAMPLE",
                    str(Path(__file__).parent / "fixtures/手写方程.png"),
                )
            )
            raw = sample.read_bytes()
            response = client.post(
                "/api/v1/questions/ingest",
                headers=headers,
                files={"file": (sample.name, raw, "image/jpeg")},
                data={"defer_processing": "true"},
            )
            assert response.status_code == 200
            id = response.json()["data"]["question_id"]
            trace.append("上传")
            response = client.post(
                "/api/v1/questions/" + id + "/crop",
                headers=headers,
                json={"box": [0, 0, 1, 1]},
            )
            assert response.status_code == 200
            job = response.json()["data"]["job_id"]
            trace.append("创建识别任务")

            def wait():
                for _ in range(420):
                    response = client.get("/api/v1/jobs/" + job, headers=headers)
                    assert response.status_code == 200
                    task = response.json()["data"]
                    if task["status"] not in ["pending", "running"]:
                        return task
                    time.sleep(0.5)
                pytest.fail("recognition timeout")

            task = wait()
            trace.append("查询任务")
            if task["status"] == "failed":
                assert (
                    client.post(
                        "/api/v1/jobs/" + job + "/retry", headers=headers
                    ).status_code
                    == 200
                )
                task = wait()
            assert task["status"] == "completed", task.get("error")
            detail = client.get("/api/v1/questions/" + id, headers=headers).json()[
                "data"
            ]
            assert detail["ocr"] and detail["question_text"]
            trace.append("读取真实识别结果")
            corrected = detail["question_text"] + "（人工核对）"
            response = client.post(
                "/api/v1/questions/" + id + "/draft",
                headers=headers,
                json={"question_text": corrected},
            )
            assert response.status_code == 200
            trace.append("人工修改")
            confirmed = client.post(
                "/api/v1/questions/" + id + "/confirm", headers=headers, json={}
            )
            assert (
                confirmed.status_code == 200 and confirmed.json()["data"]["confirmed"]
            )
            trace.append("确认入库")
            assert client.get(
                "/api/v1/questions?search=人工核对", headers=headers
            ).json()["data"]
            trace.append("列表查看")
            detail = client.get("/api/v1/questions/" + id, headers=headers).json()[
                "data"
            ]
            assert detail["question_text"] == corrected
            trace.append("详情查看")
            original = next(
                a for a in detail["assets"] if a["kind"] == "uploaded_original"
            )
            assert client.get(original["url"]).content == raw
            assert (
                client.get("/api/v1/questions/" + id, headers=other).status_code == 404
            )
            assert client.get("/api/v1/jobs/" + job, headers=other).status_code == 404
            assert client.get(original["url"], headers=other).status_code == 404
            trace.append("第二用户隔离")
            assert (
                client.patch(
                    "/api/v1/questions/" + id, headers=headers, json={"favorite": True}
                ).status_code
                == 200
            )
            trace.append("编辑")
            assert client.get("/api/v1/questions/" + id, headers=headers).json()[
                "data"
            ]["favorite"]
            trace.append("复查编辑")
            assert client.delete("/api/v1/questions/" + id, headers=headers).json()[
                "data"
            ]["deleted"]
            trace.append("归档")
            archived = client.get("/api/v1/questions/" + id, headers=headers).json()[
                "data"
            ]
            assert archived["status"] == "archived" and archived["ocr_runs"]
            assert client.get(original["url"], headers=headers).content == raw
            trace.append("历史记录和原图保留")
            output = (
                Path(Settings.load().project_root)
                / ".runtime/第三阶段真实HTTP闭环验证.json"
            )
            output.write_text(
                json.dumps(
                    {
                        "steps": trace,
                        "elapsed_seconds": round(time.perf_counter() - started, 2),
                        "status": "passed",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
    finally:
        process.terminate()
        process.wait(timeout=20)
        log.close()
        with database.session() as db, db.begin():
            for email in emails:
                for user in rows(db, "SELECT id FROM users WHERE email=?", [email]):
                    for q in rows(
                        db, "SELECT id FROM questions WHERE user_id=?", [user["id"]]
                    ):
                        id = q["id"]
                        execute(
                            db,
                            "DELETE s FROM student_steps s JOIN student_works w ON s.work_id=w.id WHERE w.question_id=?",
                            [id],
                        )
                        for table in [
                            "teacher_marks",
                            "student_works",
                            "ocr_runs",
                            "question_assets",
                            "processing_jobs",
                        ]:
                            execute(
                                db, f"DELETE FROM {table} WHERE question_id=?", [id]
                            )
                        execute(db, "DELETE FROM questions WHERE id=?", [id])
                    execute(
                        db, "DELETE FROM student_profiles WHERE user_id=?", [user["id"]]
                    )
                    execute(db, "DELETE FROM users WHERE id=?", [user["id"]])
        database.close()
