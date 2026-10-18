"""Exercise the independent Cangjie process; does not start the Python backend."""

import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from smoke_cangjie_accounts import accounts, request
from smoke_cangjie_edit import question_edit
from smoke_cangjie_ingest import ingest
from smoke_cangjie_insights import insights
from smoke_cangjie_list import question_list
from smoke_cangjie_media import media
from smoke_cangjie_ocr_edits import ocr_edits
from smoke_cangjie_questions import manual_questions, query
from smoke_cangjie_review_mutations import review_mutations
from smoke_cangjie_school import school
from smoke_cangjie_student_work import student_work


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {**os.environ, "CANGJIE_BACKEND_PORT": str(port)}
    env.setdefault("CANGJIE_AUTH_SECRET", secrets.token_hex(32))
    with (
        tempfile.TemporaryDirectory(prefix="zhiwei-cangjie-media-") as media_parent,
        tempfile.TemporaryFile() as output,
    ):
        env["CANGJIE_MEDIA_ROOT"] = str(Path(media_parent) / "media")
        env["CANGJIE_QUESTION_BANK_ROOT"] = str(
            Path(media_parent) / "question_bank_assets"
        )
        process = subprocess.Popen(
            ["bash", "scripts/cangjie.sh", "run"],
            cwd=project,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        recovery = None
        try:
            endpoint = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 60
            while True:
                if process.poll() is not None:
                    raise RuntimeError(
                        "Cangjie process exited before becoming available"
                    )
                try:
                    with urlopen(endpoint + "/livez", timeout=1) as response:
                        assert response.status == 200
                        assert response.headers.get_content_type() == "application/json"
                        assert json.load(response) == {
                            "service": "zhiwei-cangjie",
                            "status": "alive",
                            "version": "0.1.0",
                        }
                    break
                except (URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Cangjie startup timed out") from None
                    time.sleep(0.1)
            retired = json.loads(
                (project / "docs/cangjie/routes_retired.json").read_text()
            )
            for path, method, status in [
                ("/livez", "POST", 405),
                ("/api/v1/not-implemented", "GET", 404),
                *[
                    (
                        row["path"].replace("{session_id}", "removed-test-session"),
                        row["method"],
                        404,
                    )
                    for row in retired
                ],
            ]:
                try:
                    with urlopen(Request(endpoint + path, method=method), timeout=2):
                        raise AssertionError(f"Expected HTTP {status}")
                except HTTPError as error:
                    assert error.code == status
                    if status == 405:
                        assert error.headers["Allow"] == "GET"
            if (
                env.get("CANGJIE_DB_NAME")
                and env.get("CANGJIE_VERIFY_FOCUS") == "question-bank"
            ):
                from smoke_cangjie_question_bank import question_bank

                question_bank(env, query)
                return
            if (
                env.get("CANGJIE_DB_NAME")
                and env.get("CANGJIE_VERIFY_FOCUS") == "release-inputs"
            ):
                from smoke_cangjie_release_inputs import release_inputs

                release_inputs(endpoint, env, query)
                return
            if (
                env.get("CANGJIE_DB_NAME")
                and env.get("CANGJIE_VERIFY_FOCUS") == "student-personas"
            ):
                from smoke_cangjie_personas import verify_personas

                verify_personas(endpoint, env, query)
                return
            if (
                env.get("CANGJIE_DB_NAME")
                and env.get("CANGJIE_VERIFY_FOCUS") == "local-users"
            ):
                from smoke_cangjie_local_users import local_users

                local_users(endpoint, env, query)
                return
            if env.get("CANGJIE_VERIFY_FOCUS") in {
                "original-upload",
                "task-images",
                "task-figures",
                "task-visuals",
                "task-sources",
                "task-memory",
                "task-budget",
                "task-contract",
                "practice-evidence",
                "review-recovery",
            } and env.get("CANGJIE_DB_NAME"):
                recovery = ingest(endpoint, env, query)
                print(
                    "Cangjie focused task check passed; full acceptance remains separate"
                )
                return
            if (
                env.get("CANGJIE_DB_NAME")
                and env.get("CANGJIE_VERIFY_FOCUS") == "practice-alignment"
            ):
                from smoke_cangjie_alignment import alignment

                alignment(endpoint, env, query)
                return
            media(endpoint, env, process.pid)
            if env.get("CANGJIE_DB_NAME"):
                with urlopen(endpoint + "/readyz", timeout=5) as response:
                    assert json.load(response) == {
                        "database": "mysql",
                        "schema": "009_task_sources",
                        "status": "database_ready",
                        "ai": "not_connected",
                    }
                from smoke_cangjie_local_users import local_users
                from smoke_cangjie_question_bank import question_bank

                question_bank(env, query)
                local_users(endpoint, env, query)
                token = accounts(endpoint, env)
                review_mutations(endpoint, env, query)
                manual_questions(endpoint, env, token)
                question_list(endpoint, env, query)
                question_edit(endpoint, env, query)
                ocr_edits(endpoint, env, query)
                student_work(endpoint, env, query)
                insights(endpoint, env, query)
                from smoke_cangjie_experience import experience
                experience(endpoint, env, query)
                from smoke_cangjie_release_inputs import release_inputs

                release_inputs(endpoint, env, query)
                school(endpoint, env, query)
                from smoke_cangjie_alignment import alignment

                alignment(endpoint, env, query)
                recovery = ingest(endpoint, env, query)
                if env.get("CANGJIE_VERIFY_FOCUS") in {
                    "task-images",
                    "task-figures",
                    "task-visuals",
                    "task-sources",
                    "task-memory",
                    "task-budget",
                }:
                    print(
                        "Cangjie focused task check passed; full acceptance remains a separate command"
                    )
                    return
                process.terminate()
                process.wait(timeout=5)
                process = subprocess.Popen(
                    ["bash", "scripts/cangjie.sh", "run"],
                    cwd=project,
                    env=env,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
                deadline = time.monotonic() + 60
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Cangjie exited during restart")
                    try:
                        request(endpoint, "GET", "/api/v1/auth/me", token=token)
                        break
                    except (URLError, TimeoutError, ConnectionError):
                        if time.monotonic() >= deadline:
                            raise RuntimeError("Cangjie restart timed out") from None
                        time.sleep(0.1)
                print("Cangjie account session survived process restart")
                visual = request(
                    endpoint,
                    "GET",
                    "/api/v1/learning-tasks/" + recovery["visual_task_id"],
                    token=recovery["token"],
                )["student_view"]["visualization"]
                assert (
                    visual["values"] == {"delta": 2}
                    and visual["observation"] == "重启后继续看同一图示"
                )
                print(
                    "Cangjie task visualization parameters and observation survived process restart"
                )
                recovered = request(
                    endpoint,
                    "GET",
                    "/api/v1/jobs/" + recovery["job_id"],
                    token=recovery["token"],
                )
                assert recovered["status"] == "failed" and "重启" in recovered["error"]
                recovered_question = request(
                    endpoint,
                    "GET",
                    "/api/v1/questions/" + recovery["question_id"],
                    token=recovery["token"],
                )
                assert recovered_question["status"] == "partial"
                print("Cangjie interrupted recognition recovered after restart")
                from smoke_cangjie_learning_tasks import wait_task

                task_id = recovery["learning_task_id"]
                assert (
                    query(
                        env, f"SELECT status FROM learning_tasks WHERE id='{task_id}'"
                    )
                    == "running"
                )
                query(
                    env,
                    f"UPDATE learning_tasks SET lease_until=UTC_TIMESTAMP()-INTERVAL 1 SECOND WHERE id='{task_id}'",
                )
                restored = wait_task(endpoint, task_id, recovery["token"])
                assert restored["status"] == "waiting_student"
                assert restored["student_view"]["handwriting"]["id"] == query(
                    env,
                    f"SELECT id FROM learning_task_images WHERE task_id='{task_id}'",
                )
                assert (
                    query(
                        env,
                        f"SELECT COUNT(*) FROM learning_task_steps WHERE task_id='{task_id}' AND request_id='restart_probe'",
                    )
                    == "1"
                )
                print(
                    "Cangjie handwriting task recovered the same original after process restart without duplicate images or steps"
                )
                if env.get("CANGJIE_VERIFY_BROWSER") == "1":
                    from smoke_cangjie_browser import browser

                    browser(endpoint, env)
            else:
                try:
                    with urlopen(endpoint + "/readyz", timeout=5):
                        raise AssertionError(
                            "An unconfigured database must not report ready"
                        )
                except HTTPError as error:
                    assert error.code == 503
                    assert json.load(error) == {"status": "database_unavailable"}
            print(
                "Cangjie HTTP smoke passed: liveness, database readiness, methods, missing route"
            )
        finally:
            if recovery is not None:
                recovery["close_upstream"]()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
