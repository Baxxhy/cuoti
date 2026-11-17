import asyncio
import hashlib
import io
import os
import threading
import time
from uuid import uuid4

import pytest
from cuoti_backend.config import Settings
from cuoti_backend.main import create_app
from cuoti_backend.question_data import execute, insert, rows
from cuoti_backend.security import create_token
from fastapi.testclient import TestClient
from PIL import Image

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        os.environ.get("CUOTI_TEST_MYSQL") != "1",
        reason="local MySQL check not enabled",
    ),
]


class FakeVision:
    logical_model = "synthetic-vision"

    def __init__(self):
        self.fail = False
        self.hold = threading.Event()
        self.hold.set()
        self.calls = 0

    async def generate_multimodal(self, prompt, images, schema, **kwargs):
        from learning_core.providers.api_pool import ApiPoolUnavailable

        self.calls += 1
        await asyncio.to_thread(self.hold.wait, 10)
        if self.fail:
            raise ApiPoolUnavailable("synthetic failure")
        return schema.model_validate(
            {
                "subject": "数学",
                "grade": "初一",
                "question_type": "calculation",
                "question_text": "解方程：3x+2=17",
                "options": [],
                "student_answer": "19/3",
                "student_steps": [
                    {"index": 1, "text": "3x=17+2"},
                    {"index": 2, "text": "x=19/3"},
                ],
                "teacher_annotations": [],
                "question_figures": [
                    {
                        "bbox": [0.1, 0.1, 0.3, 0.3],
                        "role": "diagram",
                        "description": "原题配图",
                    },
                    {
                        "bbox": [0.4, 0.1, 0.7, 0.3],
                        "role": "table",
                        "description": "原题表格",
                    },
                ],
                "student_working_figures": [
                    {
                        "bbox": [0.1, 0.5, 0.3, 0.8],
                        "role": "student_working_figure",
                        "description": "学生草图",
                    }
                ],
                "teacher_annotation_regions": [],
                "printed_irrelevant": [],
                "has_answer": True,
                "has_working": True,
                "has_teacher_annotation": False,
                "recognition_confidence": 0.95,
                "uncertain_fields": [],
            }
        )

    async def close(self):
        pass


@pytest.fixture
def question_app(tmp_path):
    settings = Settings.load().model_copy(update={"media_root": str(tmp_path)})
    app = create_app(settings)
    emails = []
    provider = FakeVision()
    with TestClient(app) as client:
        app.state.algorithm_app.state.provider = provider

        def student():
            email = "migration-" + uuid4().hex + "@example.test"
            emails.append(email)
            response = client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "test-password"},
            )
            assert response.status_code == 200, response.text
            user = response.json()["data"]
            return user, {"Authorization": "Bearer " + user["access_token"]}

        try:
            yield app, client, student, provider
        finally:
            provider.hold.set()
            app.state.recognition.executor.shutdown(wait=True)
            with app.state.database.session() as db, db.begin():
                for email in emails:
                    users = rows(db, "SELECT id FROM users WHERE email=?", [email])
                    if not users:
                        continue
                    owner = users[0]["id"]
                    for question in rows(
                        db, "SELECT id FROM questions WHERE user_id=?", [owner]
                    ):
                        id = question["id"]
                        execute(
                            db,
                            "DELETE e FROM diagnosis_evidence e JOIN diagnoses d ON e.diagnosis_id=d.id WHERE d.question_id=?",
                            [id],
                        )
                        execute(
                            db,
                            "DELETE r FROM reference_steps r JOIN problem_analyses a ON r.analysis_id=a.id WHERE a.question_id=?",
                            [id],
                        )
                        execute(
                            db,
                            "DELETE c FROM agent_tool_calls c JOIN agent_runs a ON c.agent_run_id=a.id JOIN tutor_sessions t ON a.session_id=t.id WHERE t.question_id=?",
                            [id],
                        )
                        execute(
                            db,
                            "DELETE a FROM agent_runs a JOIN tutor_sessions t ON a.session_id=t.id WHERE t.question_id=?",
                            [id],
                        )
                        execute(
                            db,
                            "DELETE t FROM tutor_turns t JOIN tutor_sessions s ON t.session_id=s.id WHERE s.question_id=?",
                            [id],
                        )
                        execute(
                            db,
                            "DELETE a FROM variant_attempts a JOIN variant_questions v ON a.variant_id=v.id WHERE v.question_id=?",
                            [id],
                        )
                        execute(
                            db,
                            "DELETE FROM cognitive_updates WHERE question_id=?",
                            [id],
                        )
                        execute(
                            db,
                            "DELETE FROM variant_questions WHERE question_id=?",
                            [id],
                        )
                        for table in [
                            "diagnoses",
                            "problem_analyses",
                            "review_plans",
                            "tutor_sessions",
                        ]:
                            execute(
                                db, f"DELETE FROM {table} WHERE question_id=?", [id]
                            )
                        execute(
                            db,
                            "DELETE FROM agent_runs WHERE agent_name='question_revision' AND JSON_UNQUOTE(JSON_EXTRACT(result,'$.question_id'))=?",
                            [id],
                        )
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
                        db,
                        "DELETE i FROM study_session_items i JOIN study_sessions s ON i.session_id=s.id WHERE s.user_id=?",
                        [owner],
                    )
                    execute(db, "DELETE FROM study_sessions WHERE user_id=?", [owner])
                    execute(db, "DELETE FROM student_profiles WHERE user_id=?", [owner])
                    execute(
                        db, "DELETE FROM knowledge_lessons WHERE user_id=?", [owner]
                    )
                    execute(db, "DELETE FROM mastery_states WHERE user_id=?", [owner])
                    execute(
                        db, "DELETE FROM misconception_states WHERE user_id=?", [owner]
                    )
                    execute(db, "DELETE FROM users WHERE id=?", [owner])


def picture():
    output = io.BytesIO()
    Image.new("RGB", (480, 360), "white").save(output, format="PNG")
    return output.getvalue()


def ingest(client, headers, deferred=True, raw=None):
    response = client.post(
        "/api/v1/questions/ingest",
        headers=headers,
        files={"file": ("example.png", raw or picture(), "image/png")},
        data={"defer_processing": str(deferred).lower()},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def wait_job(client, headers, id, timeout=15):
    for _ in range(int(timeout / 0.05)):
        response = client.get("/api/v1/jobs/" + id, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        if data["status"] not in ["pending", "running"]:
            return data
        time.sleep(0.05)
    raise AssertionError("recognition timeout")


def test_manual_list_edit_archive_and_isolation(question_app):
    _app, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    value = {
        "question_text": "解方程 3x+2=17",
        "student_answer": "19/3",
        "student_steps": ["3x=19", "x=19/3"],
        "grade": "初一",
    }
    response = client.post("/api/v1/questions/manual", headers=headers, json=value)
    assert response.status_code == 200, response.text
    id = response.json()["data"]["id"]
    detail = client.get("/api/v1/questions/" + id, headers=headers).json()["data"]
    assert detail["confirmed"] is True and len(detail["student_steps"]) == 2
    assert client.get("/api/v1/questions/" + id, headers=other).status_code == 404
    assert (
        client.patch(
            "/api/v1/questions/" + id, headers=other, json={"title": "forbidden"}
        ).status_code
        == 404
    )
    assert client.delete("/api/v1/questions/" + id, headers=other).status_code == 404
    response = client.patch(
        "/api/v1/questions/" + id,
        headers=headers,
        json={
            "favorite": "yes",
            "tags": ["方程"],
            "knowledge_points": ["一元一次方程"],
        },
    )
    assert response.status_code == 200 and response.json()["data"]["favorite"] is True
    result = client.get(
        "/api/v1/questions?grade=初一&search=方程&knowledge_point=一元一次方程&page=1&page_size=1",
        headers=headers,
    )
    assert result.status_code == 200 and result.json()["data"][0]["id"] == id
    assert client.get("/api/v1/questions", headers=other).json()["data"] == []
    assert client.get("/api/v1/questions?page=0", headers=headers).status_code == 422
    assert client.delete("/api/v1/questions/" + id, headers=headers).json()["data"] == {
        "deleted": True
    }
    assert client.get("/api/v1/questions", headers=headers).json()["data"] == []
    assert (
        client.get("/api/v1/questions/" + id, headers=headers).json()["data"]["status"]
        == "archived"
    )
    assert (
        client.patch(
            "/api/v1/questions/" + id, headers=headers, json={"title": "no"}
        ).status_code
        == 409
    )


def test_upload_crop_recognize_confirm_and_media(question_app):
    app, client, student, provider = question_app
    _, headers = student()
    _, other = student()
    raw = picture()
    uploaded = ingest(client, headers, raw=raw)
    id = uploaded["question_id"]
    detail = client.get("/api/v1/questions/" + id, headers=headers).json()["data"]
    assert detail["status"] == "awaiting_crop"
    original = next(v for v in detail["assets"] if v["kind"] == "uploaded_original")
    url = original["url"]
    assert client.get(url).content == raw
    assert client.head(url).headers["content-length"] == str(len(raw))
    ranged = client.get(url, headers={"Range": "bytes=0-9"})
    assert ranged.status_code == 206 and ranged.content == raw[:10]
    invalid_range = client.get(url, headers={"Range": "bytes=999999-"})
    assert invalid_range.status_code == 416
    assert invalid_range.headers["content-type"].startswith("application/json")
    etag = client.get(url).headers["etag"]
    assert client.get(url, headers={"If-None-Match": etag}).status_code == 304
    assert client.get(url.replace("signature=", "signature=x")).status_code == 403
    assert client.get("/uploads/" + id + "/uploaded.png").status_code == 403
    provider.hold.clear()
    crop = client.post(
        "/api/v1/questions/" + id + "/crop", headers=headers, json={"box": [0, 0, 1, 1]}
    )
    assert crop.status_code == 200, crop.text
    job = crop.json()["data"]["job_id"]
    again = client.post(
        "/api/v1/questions/" + id + "/crop", headers=headers, json={"box": [0, 0, 1, 1]}
    )
    assert again.status_code == 200 and again.json()["data"]["resumed"]
    assert (
        client.post(
            "/api/v1/questions/" + id + "/crop",
            headers=headers,
            json={"box": [0, 0, 0.5, 0.5]},
        ).status_code
        == 409
    )
    assert client.get("/api/v1/jobs/" + job, headers=other).status_code == 404
    assert (
        client.post("/api/v1/jobs/" + job + "/retry", headers=other).status_code == 404
    )
    provider.hold.set()
    assert wait_job(client, headers, job)["status"] == "completed"
    detail = client.get("/api/v1/questions/" + id, headers=headers).json()["data"]
    assert (
        detail["question_text"] == "解方程：3x+2=17"
        and detail["student_answer"] == "19/3"
    )
    assert len(detail["student_steps"]) == 2 and detail["question_figures"]
    assert {v["role"] for v in detail["question_figures"]} == {"diagram", "table"}
    assert detail["student_working_figures"]
    assert detail["crop_box"] == [0, 0, 1, 1]
    assert detail["ocr"]["raw_result"]["has_working"] is True
    assert (
        client.post("/api/v1/jobs/" + job + "/retry", headers=headers).status_code
        == 409
    )
    changed = client.post(
        "/api/v1/questions/" + id + "/draft",
        headers=headers,
        json={
            "question_text": "人工核对题干",
            "student_steps": [{"text": "3x=15", "confidence": 1, "bbox": []}],
            "student_answer": "5",
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["student_steps"][0]["text"] == "3x=15"
    confirmed = client.post(
        "/api/v1/questions/" + id + "/confirm", headers=headers, json={}
    )
    assert (
        confirmed.status_code == 200 and confirmed.json()["data"]["confirmed"] is True
    )
    assert client.delete("/api/v1/questions/" + id, headers=headers).status_code == 200
    assert client.get(url).content == raw
    assert (
        hashlib.sha256(app.state.media.read(original["path"])).hexdigest()
        == original["sha256"]
    )


def test_failure_retry_and_manual_cancel_inflight(question_app):
    _, client, student, provider = question_app
    _, headers = student()
    provider.fail = True
    uploaded = ingest(client, headers, deferred=False)
    id = uploaded["question_id"]
    job = uploaded["job_id"]
    assert wait_job(client, headers, job)["status"] == "failed"
    assert (
        client.get("/api/v1/questions/" + id, headers=headers).json()["data"]["status"]
        == "partial"
    )
    provider.fail = False
    assert (
        client.post("/api/v1/jobs/" + job + "/retry", headers=headers).status_code
        == 200
    )
    assert wait_job(client, headers, job)["status"] == "completed"
    provider.hold.clear()
    crop = client.post(
        "/api/v1/questions/" + id + "/crop", headers=headers, json={"box": [0, 0, 1, 1]}
    )
    assert crop.status_code == 200, crop.text
    second = crop.json()["data"]["job_id"]
    saved = client.post(
        "/api/v1/questions/" + id + "/confirm",
        headers=headers,
        json={"question_text": "保留人工修改"},
    )
    assert saved.status_code == 200
    provider.hold.set()
    assert wait_job(client, headers, second)["status"] == "cancelled"
    assert (
        client.get("/api/v1/questions/" + id, headers=headers).json()["data"][
            "question_text"
        ]
        == "保留人工修改"
    )


def test_upload_validation_and_crop_validation(question_app):
    _, client, student, _ = question_app
    _, headers = student()
    assert (
        client.post("/api/v1/questions/ingest", headers=headers, json={}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/questions/ingest",
            headers=headers,
            files={"file": ("bad.png", b"not an image", "image/png")},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/questions/ingest",
            headers=headers,
            files={"file": ("empty.png", b"", "image/png")},
        ).status_code
        == 422
    )
    uploaded = ingest(client, headers)
    id = uploaded["question_id"]
    assert (
        client.post(
            "/api/v1/questions/" + id + "/ocr", headers=headers, json={}
        ).status_code
        == 422
    )
    for box in [[0, 0, 0, 1], [-1, 0, 1, 1], [0, 0, 2, 1], [0, 0, float("inf"), 1]]:
        if any(v == float("inf") for v in box):
            continue
        assert (
            client.post(
                "/api/v1/questions/" + id + "/crop", headers=headers, json={"box": box}
            ).status_code
            == 422
        )


def test_history_read_and_legacy_shape(question_app):
    import httpx

    app, client, _student, _ = question_app
    with app.state.database.session() as db, db.begin():
        history = rows(
            db,
            "SELECT q.id,q.user_id,u.password_hash FROM questions q JOIN users u ON u.id=q.user_id WHERE q.status<>'archived' AND u.role IN ('student','admin') ORDER BY q.created_at LIMIT 1",
        )
    if not history:
        pytest.skip("no historical question")
    item = history[0]
    token = create_token(
        item["user_id"],
        app.state.settings.auth_secret.get_secret_value(),
        item["password_hash"],
    )
    headers = {"Authorization": "Bearer " + token}
    response = client.get("/api/v1/questions/" + item["id"], headers=headers)
    assert response.status_code == 200, response.text
    if os.environ.get("CUOTI_LEGACY_URL"):
        with httpx.Client(
            base_url=os.environ["CUOTI_LEGACY_URL"], trust_env=False, timeout=10
        ) as legacy:
            old = legacy.get("/api/v1/questions/" + item["id"], headers=headers)
            assert old.status_code == 200
        before, after = old.json()["data"], response.json()["data"]
        assert set(before) == set(after)
        for key in [
            "question_text",
            "student_answer",
            "confirmed",
            "favorite",
            "status",
            "options",
            "knowledge_points",
        ]:
            assert before[key] == after[key]


def test_startup_recovery_only_python_jobs(question_app):
    app, client, student, _ = question_app
    _user, headers = student()
    uploaded = ingest(client, headers)
    id = uploaded["question_id"]
    with app.state.database.session() as db, db.begin():
        own = insert(
            db,
            "processing_jobs",
            question_id=id,
            kind="ingest",
            status="running",
            progress=15,
        )
        native = insert(
            db,
            "processing_jobs",
            question_id=id,
            kind="ingest",
            status="running",
            progress=15,
        )
    app.state.recognition.track(own, id, f"uploads/{id}/original.jpg", False)
    app.state.recognition.recover()
    assert (
        client.get("/api/v1/jobs/" + own, headers=headers).json()["data"]["status"]
        == "failed"
    )
    assert (
        client.get("/api/v1/jobs/" + native, headers=headers).json()["data"]["status"]
        == "running"
    )
    with app.state.database.session() as db, db.begin():
        execute(
            db, "UPDATE processing_jobs SET status='cancelled' WHERE id=?", [native]
        )
    assert (
        client.post("/api/v1/jobs/" + own + "/retry", headers=headers).status_code
        == 200
    )
    assert wait_job(client, headers, own)["status"] == "completed"


@pytest.mark.skipif(
    os.environ.get("CUOTI_TEST_REAL_OCR") != "1",
    reason="real vision model explicitly enabled only",
)
def test_real_model_upload_to_confirmation(question_app):
    import json
    from pathlib import Path

    app, client, student, _ = question_app
    app.state.algorithm_app.state.provider = None
    _, headers = student()
    raw = (Path(__file__).parent / "fixtures/手写方程.png").read_bytes()
    uploaded = ingest(client, headers, raw=raw)
    id = uploaded["question_id"]
    response = client.post(
        "/api/v1/questions/" + id + "/crop", headers=headers, json={"box": [0, 0, 1, 1]}
    )
    assert response.status_code == 200, response.text
    job = wait_job(client, headers, response.json()["data"]["job_id"], timeout=210)
    detail = client.get("/api/v1/questions/" + id, headers=headers).json()["data"]
    provider = app.state.algorithm_app.state.provider
    report = {
        "status": job["status"],
        "logical_model": getattr(provider, "logical_model", "unconfigured"),
        "provider_status": getattr(
            getattr(provider, "state", None), "last_status", "unknown"
        ),
        "question_text": detail["question_text"],
        "student_answer": detail["student_answer"],
        "student_steps": [s["text"] for s in detail["student_steps"]],
    }
    target = (
        Path(app.state.settings.project_root) / ".runtime/第三阶段真实识别验证.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    assert job["status"] == "completed", job.get("error")
    assert "17" in detail["question_text"] and detail["student_answer"]
    assert len(detail["student_steps"]) >= 2
    confirmed = client.post(
        "/api/v1/questions/" + id + "/confirm",
        headers=headers,
        json={
            "question_text": detail["question_text"],
            "student_answer": detail["student_answer"],
            "student_steps": [s["text"] for s in detail["student_steps"]],
        },
    )
    assert (
        confirmed.status_code == 200 and confirmed.json()["data"]["confirmed"] is True
    )


def test_upload_database_failure_removes_uncommitted_files(question_app):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    app, client, student, _ = question_app
    _, headers = student()

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO `questions`"):
            raise OperationalError("synthetic", {}, Exception("synthetic failure"))

    event.listen(app.state.database.engine, "before_cursor_execute", fail)
    try:
        response = client.post(
            "/api/v1/questions/ingest",
            headers=headers,
            files={"file": ("example.png", picture(), "image/png")},
            data={"defer_processing": "true"},
        )
        assert response.status_code == 503
    finally:
        event.remove(app.state.database.engine, "before_cursor_execute", fail)
    assert not [p for p in app.state.media.root.rglob("*") if p.is_file()]


def test_edit_during_recognition_discards_stale_results(question_app):
    _, client, student, provider = question_app
    _, headers = student()
    provider.hold.clear()
    uploaded = ingest(client, headers, deferred=False)
    id, job = uploaded["question_id"], uploaded["job_id"]
    # Ensure a fingerprint was captured before the edit.
    for _ in range(100):
        if provider.calls:
            break
        time.sleep(0.03)
    assert provider.calls
    assert (
        client.patch(
            "/api/v1/questions/" + id,
            headers=headers,
            json={"question_text": "保留这个人工版本"},
        ).status_code
        == 200
    )
    provider.hold.set()
    assert wait_job(client, headers, job)["status"] == "cancelled"
    detail = client.get("/api/v1/questions/" + id, headers=headers).json()["data"]
    assert detail["question_text"] == "保留这个人工版本"
    assert detail["ocr"] is None


def test_choice_confirmation_and_edit_validation(question_app):
    _, client, student, _ = question_app
    _, headers = student()
    response = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "选择正确答案",
            "question_type": "单选题",
            "options": [{"label": "A", "text": "1"}, {"label": "B", "text": "2"}],
        },
    )
    assert response.status_code == 200
    id = response.json()["data"]["id"]
    assert (
        client.patch(
            "/api/v1/questions/" + id, headers=headers, json={"options": []}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/questions/" + id,
            headers=headers,
            json={
                "options": [{"label": "A", "text": "1"}, {"label": "A", "text": "2"}]
            },
        ).status_code
        == 422
    )
    confirmed = client.post(
        "/api/v1/questions/" + id + "/confirm",
        headers=headers,
        json={"student_answer": "", "student_steps": ["A"], "question_type": "choice"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["student_answer"] == "A"
    assert confirmed.json()["data"]["student_steps"] == []


def test_study_snapshot_manual_import_is_owned_and_idempotent(question_app):
    import json

    app, client, student, _ = question_app
    user, headers = student()
    _, other = student()
    session_id, item_id = str(uuid4()), str(uuid4())
    bank = app.state.media.root / "bank"
    bank.mkdir()
    source_file = bank / "source.png"
    source_file.write_bytes(picture())
    app.state.settings.question_bank_root = str(bank)
    snapshot = {
        "id": str(uuid4()),
        "question_text": "从练习加入的错题",
        "subject": "数学",
        "grade": "初一",
        "question_type": "综合题",
        "options": [],
        "knowledge_points": ["方程"],
        "quality_status": "ready",
        "source_metadata": {},
        "image_paths": [str(source_file)],
        "answer": "4",
        "solution": "解题过程",
    }
    with app.state.database.session() as db, db.begin():
        execute(
            db,
            "INSERT INTO study_sessions (id,user_id,mode,title,subject,grade_band,status,duration_seconds,version,created_at,updated_at) VALUES (?,?,'practice','测试练习','数学','初中','submitted',600,1,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",
            [session_id, user["id"]],
        )
        execute(
            db,
            "INSERT INTO study_session_items (id,session_id,position,snapshot,student_answer,grading) VALUES (?,?,0,?,?,?)",
            [
                item_id,
                session_id,
                json.dumps(snapshot, ensure_ascii=False),
                json.dumps(["3"]),
                json.dumps({"correct": False}),
            ],
        )
    body = {
        "study_session_id": session_id,
        "study_item_id": item_id,
        "tags": ["自定义标签"],
    }
    assert (
        client.post("/api/v1/questions/manual", headers=other, json=body).status_code
        == 404
    )
    first = client.post("/api/v1/questions/manual", headers=headers, json=body)
    assert first.status_code == 200, first.text
    assert (
        client.post("/api/v1/questions/manual", headers=headers, json=body).json()[
            "data"
        ]["id"]
        == first.json()["data"]["id"]
    )
    detail = client.get(
        "/api/v1/questions/" + first.json()["data"]["id"], headers=headers
    ).json()["data"]
    assert detail["knowledge_points"] == ["方程"]
    assert "study-item:" + item_id in detail["tags"]
    assert "自定义标签" in detail["tags"]
    assert (
        detail["question_figures"]
        and client.get(detail["question_figures"][0]["url"]).content == picture()
    )


def test_batch_list_queries_and_type_filters(question_app):
    from sqlalchemy import event

    app, client, student, _ = question_app
    _, headers = student()
    for i in range(8):
        response = client.post(
            "/api/v1/questions/manual",
            headers=headers,
            json={
                "question_text": f"批量列表第{i}题",
                "grade": "初一",
                "knowledge_points": ["方程"],
            },
        )
        assert response.status_code == 200
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(app.state.database.engine, "before_cursor_execute", capture)
    try:
        first = client.get(
            "/api/v1/questions?page=1&page_size=1&question_type=综合题&knowledge_point=方程&grade=初一",
            headers=headers,
        )
        assert first.status_code == 200 and len(first.json()["data"]) == 1
        small = len(statements)
        statements.clear()
        all_items = client.get(
            "/api/v1/questions?page=1&page_size=8&question_type=综合题", headers=headers
        )
        assert len(all_items.json()["data"]) == 8
        assert len(statements) == small and small <= 8
    finally:
        event.remove(app.state.database.engine, "before_cursor_execute", capture)
    assert (
        client.get("/api/v1/questions?question_type=单选题", headers=headers).json()[
            "data"
        ]
        == []
    )
    assert (
        client.get("/api/v1/questions?page=99&page_size=8", headers=headers).json()[
            "data"
        ]
        == []
    )


def test_manual_reference_and_history_preservation(question_app):
    app, client, student, _ = question_app
    user, headers = student()
    response = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "correct_answer": "x=5",
            "explanation": "先移项，再除以3。",
            "source_info": "练习册第一课",
        },
    )
    assert response.status_code == 200, response.text
    id = response.json()["data"]["id"]
    detail = client.get("/api/v1/questions/" + id, headers=headers).json()["data"]
    assert detail["reference_information"]["correct_answer"] == "x=5"
    assert detail["analysis"]["verified"] is False
    with app.state.database.session() as db, db.begin():
        session = insert(
            db,
            "tutor_sessions",
            user_id=user["id"],
            question_id=id,
            stage="repair",
            hint_level=0,
            turn_count=0,
            mastery_score=0,
            state={},
            status="active",
        )
        plan = insert(
            db,
            "review_plans",
            user_id=user["id"],
            question_id=id,
            due_at="2030-01-01 00:00:00",
            interval_days=1,
            reason="原学习记录",
            status="pending",
        )
    response = client.patch(
        "/api/v1/questions/" + id,
        headers=headers,
        json={
            "correct_answer": "5",
            "explanation": "x=(17-2)/3",
            "source_info": "人工核对",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["reference_information"]["correct_answer"] == "5"
    detail = client.get("/api/v1/questions/" + id, headers=headers).json()["data"]
    assert detail["reference_information"]["correct_answer"] == "5"
    assert detail["reference_history"][0]["analysis"][0]["final_answer"] == "x=5"
    with app.state.database.session() as db, db.begin():
        assert (
            rows(db, "SELECT status FROM review_plans WHERE id=?", [plan])[0]["status"]
            == "cancelled"
        )
        assert rows(db, "SELECT id FROM tutor_sessions WHERE id=?", [session])
    assert (
        client.patch(
            "/api/v1/questions/" + id, headers=headers, json={"explanation": 123}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/questions/" + id, headers=headers, json={"status": "running"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/questions/" + id, headers=headers, json={"status": "ocr_draft"}
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/questions/" + id, headers=headers).json()["data"][
            "confirmed"
        ]
        is False
    )
    assert (
        client.patch(
            "/api/v1/questions/" + id, headers=headers, json={"status": "confirmed"}
        ).status_code
        == 200
    )


def test_picture_attachment_replacement_and_bearer_ownership(question_app):
    _app, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    uploaded = ingest(client, headers)
    id = uploaded["question_id"]
    original = client.get("/api/v1/questions/" + id, headers=headers).json()["data"][
        "assets"
    ][0]
    assert client.get(original["url"], headers=other).status_code == 404
    assert client.get(original["url"], headers=headers).status_code == 200
    assert (
        client.post(
            "/api/v1/questions/" + id + "/images",
            headers=other,
            files={"file": ("extra.png", picture(), "image/png")},
        ).status_code
        == 404
    )
    attached = client.post(
        "/api/v1/questions/" + id + "/images",
        headers=headers,
        files={"file": ("extra.png", picture(), "image/png")},
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["data"]["asset"]["kind"] == "question_figure"
    repeated = client.post(
        "/api/v1/questions/" + id + "/images",
        headers=headers,
        files={"file": ("extra.png", picture(), "image/png")},
    )
    assert repeated.json()["data"]["resumed"] is True
    assert (
        repeated.json()["data"]["asset"]["id"] == attached.json()["data"]["asset"]["id"]
    )
    changed = io.BytesIO()
    Image.new("RGB", (500, 400), "#ffeeaa").save(changed, format="PNG")
    replacement = client.post(
        "/api/v1/questions/" + id + "/images?replace=true",
        headers=headers,
        files={"file": ("new.png", changed.getvalue(), "image/png")},
        data={"defer_processing": "true"},
    )
    assert replacement.status_code == 200, replacement.text
    detail = client.get("/api/v1/questions/" + id, headers=headers).json()["data"]
    assert detail["status"] == "awaiting_crop"
    assert len([a for a in detail["assets"] if a["kind"] == "original"]) == 1
    assert client.get(original["url"]).status_code == 200
    assert any(a["kind"] == "previous_original" for a in detail["assets"])
    assert (
        client.post(
            "/api/v1/questions/" + id + "/crop",
            headers=headers,
            json={"box": [0, 0, 1, 1]},
        ).status_code
        == 200
    )


def test_duplicate_execution_and_timeout_retry(question_app, monkeypatch):
    app, client, student, provider = question_app
    _, headers = student()
    from cuoti_backend.protocol import ApiError

    original = app.state.compute.compute

    def timeout(operation, **kwargs):
        if operation == "recognize":
            raise ApiError(504, "算法计算超时")
        return original(operation, **kwargs)

    monkeypatch.setattr(app.state.compute, "compute", timeout)
    uploaded = ingest(client, headers, deferred=False)
    id = uploaded["question_id"]
    job = uploaded["job_id"]
    assert wait_job(client, headers, job)["status"] == "failed"
    monkeypatch.setattr(app.state.compute, "compute", original)
    provider.hold.clear()
    assert (
        client.post("/api/v1/jobs/" + job + "/retry", headers=headers).status_code
        == 200
    )
    for _ in range(100):
        if provider.calls:
            break
        time.sleep(0.02)
    app.state.recognition.submit(job, id, f"uploads/{id}/original.jpg")
    provider.hold.set()
    assert wait_job(client, headers, job)["status"] == "completed"
    app.state.recognition.run(job, id, f"uploads/{id}/original.jpg")
    with app.state.database.session() as db, db.begin():
        assert len(rows(db, "SELECT id FROM ocr_runs WHERE question_id=?", [id])) == 1
    assert provider.calls == 1


@pytest.mark.parametrize("case_index", range(6))
@pytest.mark.skipif(
    not os.environ.get("CUOTI_REAL_CASES_DIR"),
    reason="representative real model samples not configured",
)
def test_representative_real_images(question_app, case_index):
    import json
    from pathlib import Path

    app, client, student, _ = question_app
    folder = Path(os.environ["CUOTI_REAL_CASES_DIR"])
    case = json.loads((folder / "清单.json").read_text())[case_index]
    app.state.algorithm_app.state.provider = None
    _, headers = student()
    raw = (folder / case["file"]).read_bytes()
    started = time.perf_counter()
    uploaded = ingest(client, headers, raw=raw)
    id = uploaded["question_id"]
    response = client.post(
        "/api/v1/questions/" + id + "/crop",
        headers=headers,
        json={"box": case.get("box", [0, 0, 1, 1])},
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["data"]["job_id"]
    result = wait_job(client, headers, job_id, timeout=210)
    attempts = [result["status"]]
    if result["status"] == "failed":
        retry = client.post("/api/v1/jobs/" + job_id + "/retry", headers=headers)
        if retry.status_code == 200:
            result = wait_job(client, headers, job_id, timeout=210)
            attempts.append(result["status"])
    detail = client.get("/api/v1/questions/" + id, headers=headers).json()["data"]
    provider = app.state.algorithm_app.state.provider
    checks = {}
    text = detail["question_text"] + " " + (detail["student_answer"] or "")
    checks["key_symbols"] = all(key.lower() in text.lower() for key in case["keywords"])
    if case.get("no_answer"):
        checks["no_fabricated_student_answer"] = (
            not detail["student_answer"] and not detail["student_steps"]
        )
    if case.get("expected_options"):
        checks["options_count"] = len(detail["options"]) == case["expected_options"]
    if case.get("expected_figures"):
        checks["figure_region"] = bool(detail["question_figures"])
    report = {
        "case": case["name"],
        "sha256": case["sha256"],
        "status": result["status"],
        "attempts": attempts,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "model": getattr(provider, "logical_model", "unconfigured"),
        "checks": checks,
        "quality_checks_passed": all(checks.values()),
        "question_text": detail["question_text"],
        "student_answer": detail["student_answer"],
        "steps": [s["text"] for s in detail["student_steps"]],
        "options": detail["options"],
        "regions": [
            {
                "role": a.get("role"),
                "bbox": a.get("bbox"),
                "description": a.get("description"),
            }
            for a in detail["question_figures"]
        ],
    }
    report["confidence"] = (detail.get("ocr") or {}).get("confidence")
    report["uncertain_fields"] = (
        (detail.get("ocr") or {}).get("raw_result") or {}
    ).get("uncertain_fields", [])
    try:
        assert result["status"] == "completed", result.get("error")
        correction = case.get("manual_correction")
        payload = (
            {"question_text": correction} if isinstance(correction, str) else correction
        )
        if payload:
            response = client.post(
                "/api/v1/questions/" + id + "/draft", headers=headers, json=payload
            )
            assert response.status_code == 200
            report["manual_correction"] = payload
        saved = client.post(
            "/api/v1/questions/" + id + "/confirm", headers=headers, json={}
        )
        assert saved.status_code == 200
        expected_text = (
            payload.get("question_text", detail["question_text"])
            if payload
            else detail["question_text"]
        )
        assert saved.json()["data"]["question_text"] == expected_text
        if payload and "student_answer" in payload:
            assert saved.json()["data"]["student_answer"] == payload["student_answer"]
        report["saved_answer"] = saved.json()["data"]["student_answer"]
        report["saved_text"] = saved.json()["data"]["question_text"]
        report["confirmed"] = saved.json()["data"]["confirmed"]
    finally:
        output = (
            Path(app.state.settings.project_root)
            / ".runtime/第三阶段代表图片真实验证.jsonl"
        )
        with output.open("a") as file:
            file.write(json.dumps(report, ensure_ascii=False) + "\n")


@pytest.mark.skipif(
    not os.environ.get("CUOTI_LEGACY_URL"), reason="legacy comparison not enabled"
)
def test_question_contract_parity_including_business_results(question_app):
    from datetime import datetime
    from urllib.parse import urlsplit

    import httpx

    _, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    response = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "接口对照 3x+2=17",
            "student_answer": "19/3",
            "student_steps": ["3x=19"],
            "grade": "初一",
        },
    )
    id = response.json()["data"]["id"]

    def normalize(value, key=""):
        if isinstance(value, dict):
            return {k: normalize(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [normalize(v, key) for v in value]
        if isinstance(value, str) and key.endswith("_url"):
            return urlsplit(value).path
        if isinstance(value, str) and key in [
            "created_at",
            "updated_at",
            "due_at",
            "review_due_at",
        ]:
            return datetime.fromisoformat(value).isoformat()
        return value

    with httpx.Client(
        base_url=os.environ["CUOTI_LEGACY_URL"], trust_env=False, timeout=15
    ) as old:
        for path in ["/api/v1/questions/" + id, "/api/v1/questions?search=接口对照"]:
            before = old.get(path, headers=headers)
            after = client.get(path, headers=headers)
            assert before.status_code == after.status_code == 200
            assert normalize(before.json()["data"]) == normalize(after.json()["data"])
        for path in ["/api/v1/questions/" + id, "/api/v1/jobs/" + str(uuid4())]:
            before = old.get(path, headers=other)
            after = client.get(path, headers=other)
            assert before.status_code == after.status_code == 404
            assert before.json() == after.json()
        payload = {"favorite": True, "tags": ["接口兼容"]}
        updated = client.patch("/api/v1/questions/" + id, headers=headers, json=payload)
        same = old.patch("/api/v1/questions/" + id, headers=headers, json=payload)
        assert normalize(updated.json()["data"]) == normalize(same.json()["data"])
        deleted = client.delete("/api/v1/questions/" + id, headers=headers)
        again = old.delete("/api/v1/questions/" + id, headers=headers)
        assert deleted.json()["data"] == again.json()["data"] == {"deleted": True}


def test_diagnosis_persistence_ownership_and_stale_write(question_app, monkeypatch):
    from cuoti_backend.protocol import ApiError

    app, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    id = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "student_answer": "19/3",
            "student_steps": ["3x=19", "x=19/3"],
        },
    ).json()["data"]["id"]
    calls = []

    def compute(operation, **payload):
        calls.append(operation)
        if operation == "analyze":
            return {
                "analysis": {"final_answer": "5", "reference_steps": ["3x=15", "x=5"]},
                "reference_math_valid": [True, True],
            }
        step = payload["student_records"][0]
        ref = payload["reference_steps"][0]
        return {
            "diagnosis": {
                "first_error_step": 0,
                "error_type": "calculation",
                "first_error_text": step["text"],
            },
            "alignment": [
                {
                    "index": 0,
                    "reference_step_id": ref["id"],
                    "student_step_id": step["id"],
                    "student_text": step["text"],
                    "alignment": "calculation",
                    "equivalent": False,
                    "math_valid": False,
                    "uses_condition": True,
                    "is_first_error": True,
                    "propagated": False,
                }
            ],
            "counterfactual": {
                "status": "partial",
                "root_cause_confirmed": False,
                "conclusion": "待核对",
            },
            "evidence_diagnosis": {},
        }

    monkeypatch.setattr(app.state.compute, "compute", compute)
    assert (
        client.post(f"/api/v1/questions/{id}/diagnose", headers=other).status_code
        == 404
    )
    result = client.post(f"/api/v1/questions/{id}/diagnose", headers=headers)
    assert result.status_code == 200, result.text
    assert calls == ["analyze", "diagnose"]
    data = result.json()["data"]
    assert data["first_error_step"] == 0 and len(data["evidence"]) == 1
    assert data["counterfactual"]["root_cause_confirmed"] is False
    assert (
        client.get(f"/api/v1/questions/{id}/diagnosis", headers=headers).json()["data"][
            "id"
        ]
        == data["id"]
    )
    assert (
        client.get(f"/api/v1/questions/{id}/diagnosis", headers=other).status_code
        == 404
    )
    corrected = client.patch(
        f"/api/v1/questions/{id}/diagnosis",
        headers=headers,
        json={"first_error_step": 1, "error_type": "sign_error"},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["data"]["first_error_text"] == "x=19/3"
    assert (
        client.patch(
            f"/api/v1/questions/{id}/diagnosis",
            headers=other,
            json={"error_type": "exact"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/questions/{id}/diagnosis",
            headers=headers,
            json={"first_error_step": True},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/questions/{id}/diagnosis",
            headers=headers,
            json={"first_error_step": 100},
        ).status_code
        == 422
    )
    cached = client.post(
        f"/api/v1/questions/{id}/diagnosis/counterfactual", headers=headers
    )
    assert (
        cached.status_code == 200
        and cached.json()["data"]["root_cause_confirmed"] is False
    )
    assert calls == ["analyze", "diagnose"]
    original_compute = compute

    def stale(operation, **payload):
        client.patch(
            f"/api/v1/questions/{id}",
            headers=headers,
            json={"question_text": "3x+2=20"},
        )
        return original_compute(operation, **payload)

    monkeypatch.setattr(app.state.compute, "compute", stale)
    assert (
        client.post(f"/api/v1/questions/{id}/diagnose", headers=headers).status_code
        == 409
    )
    history = client.get(f"/api/v1/questions/{id}", headers=headers).json()["data"]
    assert history["diagnosis"] is None and history["reference_history"]

    def failed(*args, **kwargs):
        raise ApiError(504, "算法计算超时")

    monkeypatch.setattr(app.state.compute, "compute", failed)
    assert (
        client.post(f"/api/v1/questions/{id}/analyze", headers=headers).status_code
        == 504
    )


@pytest.mark.skipif(
    os.environ.get("CUOTI_TEST_REAL_DIAGNOSIS") != "1",
    reason="real diagnosis not enabled",
)
def test_real_diagnosis_business_roundtrip(question_app):
    app, client, student, _ = question_app
    app.state.algorithm_app.state.provider = None
    _, headers = student()
    id = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "解方程3x+2=17",
            "student_answer": "19/3",
            "student_steps": ["3x=17+2", "x=19/3"],
        },
    ).json()["data"]["id"]
    result = client.post(f"/api/v1/questions/{id}/diagnose", headers=headers)
    assert result.status_code == 200, result.text
    value = result.json()["data"]
    assert value["id"] and value["evidence"] and value["counterfactual"]
    assert (
        client.get(f"/api/v1/questions/{id}/diagnosis", headers=headers).json()["data"][
            "id"
        ]
        == value["id"]
    )


def test_submit_new_work_preserves_previous_work(question_app):
    app, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    id = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "student_answer": "6",
            "student_steps": ["x=6"],
        },
    ).json()["data"]["id"]
    path = f"/api/v1/questions/{id}/student-work"
    payload = {"answer": "5", "explanation": "重新核对", "steps": ["3x=15", "x=5"]}
    assert client.post(path, headers=other, json=payload).status_code == 404
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/v1/questions/{id}", headers=headers).json()["data"]
    assert detail["student_answer"] == "5"
    assert [s["text"] for s in detail["student_steps"]] == payload["steps"]
    with app.state.database.session() as db:
        assert (
            len(rows(db, "SELECT id FROM student_works WHERE question_id=?", [id])) == 2
        )
    assert client.post(path, headers=headers, json={"steps": [123]}).status_code == 422
    client.delete(f"/api/v1/questions/{id}", headers=headers)
    assert client.post(path, headers=headers, json=payload).status_code == 409


def test_knowledge_dashboard_and_legacy_content_parity(question_app):
    import httpx

    _, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    assert client.get("/api/v1/dashboard").status_code == 401
    denied = client.post("/api/v1/dashboard", headers=headers)
    assert denied.status_code == 405 and denied.headers["allow"] == "GET"
    empty = client.get("/api/v1/dashboard", headers=headers).json()["data"]
    assert empty["weekly_questions"] == 0 and empty["estimated_minutes"] == 0
    for text in ["解方程：3x=15", "解方程: 3x=15"]:
        assert (
            client.post(
                "/api/v1/questions/manual",
                headers=headers,
                json={"question_text": text},
            ).status_code
            == 200
        )
    assert (
        client.get("/api/v1/dashboard", headers=headers).json()["data"][
            "weekly_questions"
        ]
        == 1
    )
    assert (
        client.get("/api/v1/dashboard", headers=other).json()["data"][
            "weekly_questions"
        ]
        == 0
    )
    assert (
        client.get("/api/v1/analytics/overview?days=0", headers=headers).status_code
        == 422
    )
    paths = [
        "/dashboard",
        "/analytics/overview",
        "/analytics/overview?days=1",
        "/knowledge/framework",
        "/knowledge/cards",
        "/knowledge/cards?subject=数学&grade=初一",
        "/knowledge/cards?q=方程，移项、等式&misconception=符号",
    ]
    listing = client.get("/api/v1/knowledge/cards").json()["data"]
    if listing:
        paths.append("/knowledge/cards/" + listing[0]["code"])
    assert client.get("/api/v1/knowledge/cards/does-not-exist").status_code == 404
    if os.environ.get("CUOTI_LEGACY_URL"):
        with httpx.Client(
            base_url=os.environ["CUOTI_LEGACY_URL"], trust_env=False, timeout=20
        ) as legacy:
            for path in paths:
                actual = client.get("/api/v1" + path, headers=headers)
                original = legacy.get("/api/v1" + path, headers=headers)
                assert actual.status_code == original.status_code == 200, (
                    path,
                    actual.text,
                    original.text,
                )
                assert actual.json()["data"] == original.json()["data"], path


@pytest.mark.skipif(
    not os.environ.get("CUOTI_LEGACY_URL"), reason="legacy comparison not enabled"
)
def test_historical_dashboard_and_framework_parity(question_app):
    import httpx

    app, client, _, _ = question_app
    with app.state.database.session() as db:
        users = rows(
            db,
            "SELECT id,password_hash FROM users WHERE role='student' AND email NOT LIKE 'migration-%@example.test' ORDER BY created_at LIMIT 3",
        )
    if not users:
        pytest.skip("no historical students")
    with httpx.Client(
        base_url=os.environ["CUOTI_LEGACY_URL"], trust_env=False, timeout=20
    ) as legacy:
        for user in users:
            token = create_token(
                user["id"],
                app.state.settings.auth_secret.get_secret_value(),
                user["password_hash"],
            )
            headers = {"Authorization": "Bearer " + token}
            for path in [
                "/dashboard",
                "/knowledge/framework",
                "/analytics/overview?days=365",
            ]:
                new = client.get("/api/v1" + path, headers=headers)
                old = legacy.get("/api/v1" + path, headers=headers)
                assert new.status_code == old.status_code == 200, path
                assert new.json()["data"] == old.json()["data"], path


def test_knowledge_lessons_idempotency_history_and_legacy(question_app, monkeypatch):
    import httpx

    app, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    cards = client.get("/api/v1/knowledge/cards").json()["data"]
    if not cards:
        pytest.skip("no knowledge cards")
    code = cards[0]["code"]
    path = f"/api/v1/knowledge/cards/{code}/lessons"
    calls = []

    def compute(operation, **values):
        calls.append(values)
        assert operation == "knowledge_lesson"
        return {
            "explanation": "根据公开知识内容作出的讲解。",
            "check_question": "你能举一个例子吗？",
            "sources": [],
            "can_update_learning": False,
        }

    monkeypatch.setattr(app.state.compute, "compute", compute)
    assert client.post(path, headers=headers, json={}).status_code == 422
    body = {"request_id": str(uuid4()), "prompt": "给个例子"}
    first = client.post(path, headers=headers, json=body)
    assert first.status_code == 200, first.text
    assert (
        client.post(path, headers=headers, json=body).json()["data"]
        == first.json()["data"]
    )
    assert len(calls) == 1
    assert (
        client.post(
            path, headers=headers, json={**body, "prompt": "不同问题"}
        ).status_code
        == 409
    )
    assert client.get(path, headers=other).json()["data"] == []
    history = client.get(path, headers=headers)
    assert history.json()["data"][0]["source_current"] is True
    if os.environ.get("CUOTI_LEGACY_URL"):
        with httpx.Client(
            base_url=os.environ["CUOTI_LEGACY_URL"], trust_env=False, timeout=10
        ) as old:
            original = old.get(path, headers=headers)
            assert original.status_code == 200
            assert original.json()["data"] == history.json()["data"]
            replay = old.post(path, headers=headers, json=body)
            assert replay.status_code == 200, replay.text
            assert replay.json()["data"] == first.json()["data"]
    follow = client.post(
        path, headers=headers, json={"request_id": str(uuid4()), "prompt": "再解释一下"}
    )
    assert follow.status_code == 200
    assert calls[-1]["knowledge_history"][0]["question"] == body["prompt"]


def test_lesson_invalid_results_source_conflicts_and_concurrency(
    question_app, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor

    from cuoti_backend import lessons

    app, client, student, _ = question_app
    _, headers = student()
    cards = client.get("/api/v1/knowledge/cards").json()["data"]
    if not cards:
        pytest.skip("no knowledge cards")
    path = f"/api/v1/knowledge/cards/{cards[0]['code']}/lessons"
    payload = {"request_id": str(uuid4()), "prompt": "讲解"}
    monkeypatch.setattr(
        app.state.compute, "compute", lambda *a, **k: {"can_update_learning": True}
    )
    assert client.post(path, headers=headers, json=payload).status_code == 503
    assert client.get(path, headers=headers).json()["data"] == []

    def compute(*args, **kwargs):
        return {
            "explanation": "有效讲解",
            "check_question": "举例",
            "can_update_learning": False,
        }

    monkeypatch.setattr(app.state.compute, "compute", compute)
    original = lessons.lesson_cards
    counter = []

    def changed(db, code):
        values = original(db, code)
        counter.append(1)
        if len(counter) > 1:
            values[0]["name"] += "新版"
        return values

    monkeypatch.setattr(lessons, "lesson_cards", changed)
    assert client.post(path, headers=headers, json=payload).status_code == 409
    monkeypatch.setattr(lessons, "lesson_cards", original)
    assert client.get(path, headers=headers).json()["data"] == []
    barrier = threading.Barrier(2)

    def simultaneous(*args, **kwargs):
        barrier.wait(timeout=10)
        return compute()

    monkeypatch.setattr(app.state.compute, "compute", simultaneous)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: client.post(path, headers=headers, json=payload), range(2)
            )
        )
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    assert results[0].json()["data"]["id"] == results[1].json()["data"]["id"]
    assert len(client.get(path, headers=headers).json()["data"]) == 1


@pytest.mark.skipif(
    os.environ.get("CUOTI_TEST_REAL_LESSON") != "1", reason="real lesson not enabled"
)
def test_real_knowledge_lesson_roundtrip(question_app):
    app, client, student, _ = question_app
    app.state.algorithm_app.state.provider = None
    _, headers = student()
    cards = client.get("/api/v1/knowledge/cards?subject=数学").json()["data"]
    assert cards
    path = f"/api/v1/knowledge/cards/{cards[0]['code']}/lessons"
    result = client.post(
        path,
        headers=headers,
        json={"request_id": str(uuid4()), "prompt": "请解释这个知识点并举一个例子。"},
    )
    assert result.status_code == 200, result.text
    content = result.json()["data"]["result"]
    assert (
        content["can_update_learning"] is False
        and content["sources"]
        and content["explanation"]
    )
    assert (
        client.get(path, headers=headers).json()["data"][0]["id"]
        == result.json()["data"]["id"]
    )


def test_tutor_start_read_navigation_and_legacy_contract(question_app):
    import httpx

    app, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "解方程3x+2=17",
            "student_steps": ["3x=19"],
            "student_answer": "19/3",
            "knowledge_points": ["方程"],
            "correct_answer": "5",
            "explanation": "3x=15，然后x=5",
        },
    ).json()["data"]["id"]
    start = client.post(
        "/api/v1/tutor/sessions", headers=headers, json={"question_id": q}
    )
    assert start.status_code == 200, start.text
    item = start.json()["data"]
    sid = item["id"]
    path = "/api/v1/tutor/sessions/" + sid
    assert item["teaching_policy"]["mode"] == "full"
    assert (
        "correct_answers" not in item["activity"]
        and "understanding_plan" not in item["state"]
    )
    assert item["turns"] and item["stage"] == "understanding"
    assert client.get(path, headers=other).status_code == 404
    assert (
        client.post(
            path + "/advance", headers=headers, json={"target_stage": "teach_back"}
        ).status_code
        == 409
    )
    current = client.get(path, headers=headers)
    assert current.status_code == 200
    if os.environ.get("CUOTI_LEGACY_URL"):
        with httpx.Client(
            base_url=os.environ["CUOTI_LEGACY_URL"], trust_env=False, timeout=15
        ) as old:
            legacy = old.get(path, headers=headers)
            assert legacy.status_code == 200, legacy.text
            assert current.json()["data"] == legacy.json()["data"]
    with app.state.database.session() as db, db.begin():
        # Seed an already-earned gate to test navigation independently of grading.
        execute(
            db,
            "UPDATE tutor_sessions SET state=JSON_SET(state,'$.understanding_passed',CAST('true' AS JSON)) WHERE id=?",
            [sid],
        )
    advanced = client.post(
        path + "/advance", headers=headers, json={"target_stage": "teach_back"}
    )
    assert (
        advanced.status_code == 200 and advanced.json()["data"]["stage"] == "teach_back"
    )
    assert (
        client.get(path, headers=headers).json()["data"]["activity"]["type"]
        == "teach_back"
    )
    assert (
        client.post(path + "/rewind", headers=headers, json={}).json()["data"]["stage"]
        == "understanding"
    )
    client.patch(
        "/api/v1/questions/" + q,
        headers=headers,
        json={"question_text": "解方程3x+2=20"},
    )
    assert (
        client.post(
            path + "/advance", headers=headers, json={"target_stage": "teach_back"}
        ).status_code
        == 409
    )


def test_tutor_compressed_start_and_missing_analysis(question_app, monkeypatch):
    app, client, student, _ = question_app
    _, headers = student()
    data = {
        "question_text": "选择3x=15的解",
        "options": [{"label": "A", "text": "5"}, {"label": "B", "text": "6"}],
        "question_type": "单选题",
    }
    no_analysis = client.post(
        "/api/v1/questions/manual", headers=headers, json=data
    ).json()["data"]["id"]
    assert (
        client.post(
            "/api/v1/tutor/sessions", headers=headers, json={"question_id": no_analysis}
        ).status_code
        == 409
    )
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={**data, "correct_answer": "A", "student_answer": "B"},
    ).json()["data"]["id"]
    calls = []

    def brief(operation, **values):
        calls.append(operation)
        return {
            "brief": {
                "topic": "方程",
                "correct_answer": "A",
                "key_explanation": "3x=15两边除以3",
                "option_explanations": [],
                "check": {
                    "id": "check-1",
                    "type": "single_choice",
                    "title": "检查",
                    "question": "等式两边可以同时除以非零数吗？",
                    "options": [],
                    "correct_answers": ["yes"],
                },
            }
        }

    monkeypatch.setattr(app.state.compute, "compute", brief)
    response = client.post(
        "/api/v1/tutor/sessions", headers=headers, json={"question_id": q}
    )
    assert response.status_code == 200, response.text
    value = response.json()["data"]
    assert calls == ["teaching_brief"]
    assert value["teaching_policy"]["mode"] == "compressed"
    assert value["activity"]["id"] == "answer-reveal"
    assert "teaching_brief" not in value["state"]
    assert value["answer_reveal"]["student_answer"] == "B"
    assert (
        client.get("/api/v1/tutor/sessions/" + value["id"], headers=headers).json()[
            "data"
        ]["activity"]["id"]
        == "answer-reveal"
    )


def test_tutor_variant_generation_revalidation_and_teach_back(
    question_app, monkeypatch
):
    from cuoti_backend.protocol import ApiError

    app, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "student_steps": ["3x=19"],
            "correct_answer": "5",
            "knowledge_points": ["一元一次方程"],
        },
    ).json()["data"]["id"]
    sid = client.post(
        "/api/v1/tutor/sessions", headers=headers, json={"question_id": q}
    ).json()["data"]["id"]
    base = "/api/v1/tutor/sessions/" + sid
    assert client.post(base + "/variant", headers=headers, json={}).status_code == 409
    assert (
        client.post(
            base + "/variant", headers=headers, json={"transfer_type": "invalid"}
        ).status_code
        == 422
    )
    calls = []
    flags = {"valid": True, "passed": False, "retrieval": True}

    def compute(operation, **values):
        calls.append(operation)
        if operation == "evaluate_teach_back":
            return {
                "passed": flags["passed"],
                "feedback": "补充依据",
                "matched_concepts": [],
            }
        if operation == "retrieval_prepare":
            return {"query": "一元一次方程"}
        if operation == "retrieval_search":
            if not flags["retrieval"]:
                raise ApiError(503, "检索不可用")
            return {"hits": []}
        if operation == "retrieval_rank":
            return {"references": []}
        if operation == "validate_variant":
            return {"valid": flags["valid"]}
        assert operation == "generate_variant"
        return {
            "variant": {
                "question_text": f"2x+1={5 + 2 * calls.count(operation)}",
                "answer": str(2 + calls.count(operation)),
                "explanation": "先减1，再除以2",
                "reference_solution": ["先移项", "再求解"],
                "options": [],
            },
            "verified": True,
            "generation": {"retrieval_ids": []},
        }

    monkeypatch.setattr(app.state.compute, "compute", compute)
    with app.state.database.session() as db, db.begin():
        execute(db, "UPDATE tutor_sessions SET stage='teach_back' WHERE id=?", [sid])
    first = client.post(
        base + "/teach-back", headers=headers, json={"explanation": "不知道"}
    )
    assert first.status_code == 200 and first.json()["data"]["stage"] == "teach_back"
    second = client.post(
        base + "/teach-back", headers=headers, json={"explanation": "仍不确定"}
    )
    assert (
        second.status_code == 200 and second.json()["data"]["stage"] == "near_transfer"
    )
    assert (
        second.json()["data"]["assisted"] is True
        and second.json()["data"]["passed"] is False
    )
    assert client.post(base + "/variant", headers=other, json={}).status_code == 404
    record = client.post(base + "/variant", headers=headers, json={}).json()["data"]
    assert "answer" not in record and calls.count("generate_variant") == 1
    loaded = client.get(base, headers=headers)
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["data"]["activity"]["variant_id"] == record["id"]
    flags.update(valid=False, retrieval=False)
    replacement = client.post(base + "/variant", headers=headers, json={})
    assert replacement.status_code == 200, replacement.text
    assert replacement.json()["data"]["id"] != record["id"]
    with app.state.database.session() as db:
        saved = rows(
            db,
            "SELECT generation_metadata FROM variant_questions WHERE session_id=?",
            [sid],
        )
        assert len(saved) == 2
    flags["valid"] = True
    with app.state.database.session() as db, db.begin():
        execute(db, "UPDATE tutor_sessions SET stage='far_transfer' WHERE id=?", [sid])
    far = client.post(base + "/variant", headers=headers, json={"transfer_type": "far"})
    assert far.status_code == 200 and far.json()["data"]["transfer_type"] == "far"
    assert (
        client.get(base, headers=headers).json()["data"]["activity"]["variant_id"]
        == far.json()["data"]["id"]
    )
    client.patch(
        "/api/v1/questions/" + q, headers=headers, json={"question_text": "3x+2=20"}
    )
    assert (
        client.post(
            base + "/variant", headers=headers, json={"transfer_type": "far"}
        ).status_code
        == 409
    )


@pytest.mark.skipif(
    os.environ.get("CUOTI_TEST_REAL_VARIANT") != "1",
    reason="real transfer exercise not enabled",
)
def test_real_tutor_variant_generation_and_persistence(question_app):
    import json
    from pathlib import Path

    started = time.perf_counter()
    app, client, student, _ = question_app
    app.state.algorithm_app.state.provider = None
    _, headers = student()
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "解方程3x+2=17",
            "question_type": "综合题",
            "grade": "初一",
            "student_steps": ["3x=19", "x=19/3"],
            "correct_answer": "5",
            "explanation": "3x=15，x=5",
            "knowledge_points": ["一元一次方程"],
        },
    ).json()["data"]["id"]
    assert (
        client.patch(
            "/api/v1/questions/" + q,
            headers=headers,
            json={"question_type": "calculation"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            "/api/v1/questions/" + q,
            headers=headers,
            json={"correct_answer": "5", "explanation": "3x=15，x=5"},
        ).status_code
        == 200
    )
    created = client.post(
        "/api/v1/tutor/sessions", headers=headers, json={"question_id": q}
    )
    assert created.status_code == 200, created.text
    sid = created.json()["data"]["id"]
    with app.state.database.session() as db, db.begin():
        execute(db, "UPDATE tutor_sessions SET stage='near_transfer' WHERE id=?", [sid])
    response = client.post(
        "/api/v1/tutor/sessions/" + sid + "/variant", headers=headers, json={}
    )
    record = {
        "status_code": response.status_code,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "response": response.json(),
    }
    output = Path(app.state.settings.project_root) / ".runtime/真实迁移练习验证.jsonl"
    with output.open("a") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["question_text"] and type(data["verified"]) is bool
    with app.state.database.session() as db:
        saved = rows(
            db,
            "SELECT answer,generation_metadata FROM variant_questions WHERE id=? AND session_id=?",
            [data["id"], sid],
        )
        assert len(saved) == 1 and saved[0]["answer"]


def tutor_compute_adapter(app, monkeypatch):
    original = app.state.compute.compute
    flags = {"undecidable": False}

    def compute(operation, **values):
        if operation in ["retrieval_prepare", "retrieval_search", "retrieval_rank"]:
            return {"query": "方程", "hits": [], "references": []}
        if operation == "teaching_brief":
            return {
                "brief": {
                    "topic": "方程",
                    "correct_answer": "5",
                    "key_explanation": "移项求解",
                    "option_explanations": [],
                    "check": {
                        "id": "check-1",
                        "type": "single_choice",
                        "title": "检查",
                        "question": "先检查条件吗？",
                        "options": [],
                        "correct_answers": ["yes"],
                    },
                }
            }
        if operation == "evaluate_teach_back":
            return {
                "passed": True,
                "feedback": "讲清楚了",
                "matched_concepts": ["等式性质"],
            }
        if operation == "generate_variant":
            near = values["transfer_type"] == "near"
            return {
                "variant": {
                    "question_text": "2x+1=7" if near else "4x-3=13",
                    "answer": "3" if near else "4",
                    "explanation": "依据等式性质求解",
                    "reference_solution": ["2x=6", "x=3"] if near else ["4x=16", "x=4"],
                    "options": [],
                },
                "verified": True,
                "generation": {"retrieval_ids": []},
            }
        if operation == "grade_answer" and flags["undecidable"]:
            return {
                "correct": False,
                "can_update_learning": False,
                "feedback": "证据不足",
                "verdict": "uncertain",
            }
        return original(operation, **values)

    monkeypatch.setattr(app.state.compute, "compute", compute)
    return flags


def test_complete_tutor_activity_flow_and_finish_idempotency(question_app, monkeypatch):
    app, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    tutor_compute_adapter(app, monkeypatch)
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "student_steps": ["3x=19"],
            "correct_answer": "5",
            "knowledge_points": ["一元一次方程"],
        },
    ).json()["data"]["id"]
    created = client.post(
        "/api/v1/tutor/sessions", headers=headers, json={"question_id": q}
    ).json()["data"]
    path = "/api/v1/tutor/sessions/" + created["id"]

    def answer(activity, value):
        response = client.post(
            path + "/activity/answer",
            headers=headers,
            json={"activity_id": activity, "answer": value},
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]

    assert client.post(path + "/finish", headers=headers, json={}).status_code == 409
    assert (
        client.post(
            path + "/activity/answer",
            headers=other,
            json={"activity_id": created["activity"]["id"], "answer": "key"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            path + "/activity/answer",
            headers=headers,
            json={"activity_id": "old", "answer": "key"},
        ).status_code
        == 409
    )
    result = answer(created["activity"]["id"], "key")
    result = answer(result["activity"]["id"], "reference")
    assert result["stage_status"] == "passed"
    assert (
        client.post(
            path + "/advance", headers=headers, json={"target_stage": "teach_back"}
        ).status_code
        == 200
    )
    result = answer("teach-back", "依据等式性质移项再求解")
    assert result["stage"] == "near_transfer"
    result = answer(result["activity"]["id"], "3")
    assert result["stage"] == "far_transfer"
    result = answer(result["activity"]["id"], "4")
    assert result["stage"] == "finished" and result["status"] == "completed"
    assert result["state"]["mastery_proven"] is True
    one = client.post(path + "/finish", headers=headers, json={})
    two = client.post(path + "/finish", headers=headers, json={})
    assert one.status_code == two.status_code == 200
    assert one.json()["data"]["review"]["id"] == two.json()["data"]["review"]["id"]
    assert one.json()["data"]["review"]["interval_days"] == 15
    if os.environ.get("CUOTI_LEGACY_URL"):
        import httpx

        with httpx.Client(
            base_url=os.environ["CUOTI_LEGACY_URL"], trust_env=False, timeout=15
        ) as old:
            legacy = old.post(path + "/finish", headers=headers, json={})
            assert legacy.status_code == 200
            assert legacy.json()["data"] == one.json()["data"]
            original_dashboard = old.get("/api/v1/dashboard", headers=headers)
            assert (
                original_dashboard.json()["data"]
                == client.get("/api/v1/dashboard", headers=headers).json()["data"]
            )
    with app.state.database.session() as db:
        assert (
            len(rows(db, "SELECT id FROM cognitive_updates WHERE question_id=?", [q]))
            == 2
        )
        assert (
            len(rows(db, "SELECT id FROM review_plans WHERE question_id=?", [q])) == 1
        )
    assert (
        client.post(
            path + "/activity/answer",
            headers=headers,
            json={"activity_id": "old", "answer": "4"},
        ).status_code
        == 409
    )


def test_tutor_help_uncertain_and_insufficient_completion(question_app, monkeypatch):
    app, client, student, _ = question_app
    _, headers = student()
    flags = tutor_compute_adapter(app, monkeypatch)
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "correct_answer": "5",
            "knowledge_points": ["一元一次方程"],
        },
    ).json()["data"]["id"]
    created = client.post(
        "/api/v1/tutor/sessions", headers=headers, json={"question_id": q}
    ).json()["data"]
    path = "/api/v1/tutor/sessions/" + created["id"]

    def answer(item, value, **extra):
        response = client.post(
            path + "/activity/answer",
            headers=headers,
            json={"activity_id": item, "answer": value, **extra},
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]

    result = answer("answer-reveal", "understood")
    assert result["stage"] == "near_transfer"
    aid = result["activity"]["id"]
    assert (
        client.post(
            path + "/activity/answer",
            headers=headers,
            json={"activity_id": aid, "answer": "3", "handwriting_recognition": {}},
        ).status_code
        == 422
    )
    assert (
        client.post(
            path + "/activity/answer",
            headers=headers,
            json={
                "activity_id": aid,
                "answer": "3",
                "handwriting_image_url": "/uploads/another-user.jpg",
            },
        ).status_code
        == 422
    )
    result = answer(aid, "不会做", unknown=True)
    assert result["assisted"] is True and result["activity"]["teaching"]
    flags["undecidable"] = True
    answer(aid, "maybe")
    with app.state.database.session() as db:
        assert not rows(
            db,
            "SELECT a.id FROM variant_attempts a JOIN variant_questions v ON a.variant_id=v.id WHERE v.session_id=?",
            [created["id"]],
        )
        assert not rows(db, "SELECT id FROM cognitive_updates WHERE question_id=?", [q])
    flags["undecidable"] = False
    answer(aid, "0")
    result = answer(aid, "0")
    assert result["stage"] == "finished" and result["state"]["mastery_proven"] is False
    finished = client.post(path + "/finish", headers=headers, json={}).json()["data"]
    assert finished["review"]["interval_days"] == 1
    assert (
        client.post(
            path + "/activity/answer",
            headers=headers,
            json={"activity_id": aid, "answer": "0", "elapsed_seconds": -1},
        ).status_code
        == 422
    )


@pytest.mark.skipif(
    not os.environ.get("CUOTI_LEGACY_URL"),
    reason="legacy source stamp comparison not enabled",
)
def test_learning_evidence_source_stamp_matches_legacy(question_app):
    import json

    import httpx
    from cuoti_backend.learning_evidence import question_version
    from cuoti_backend.question_data import select_rows

    app, client, student, _ = question_app
    user, headers = student()
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "student_steps": ["3x=15", "x=5"],
            "correct_answer": "5",
            "knowledge_points": ["一元一次方程"],
        },
    ).json()["data"]["id"]
    with app.state.database.session() as db, db.begin():
        sid = insert(
            db,
            "tutor_sessions",
            user_id=user["id"],
            question_id=q,
            stage="finished",
            hint_level=0,
            turn_count=0,
            mastery_score=0,
            state={
                "teach_back": True,
                "near_transfer": True,
                "far_transfer": True,
                "assisted": False,
            },
            status="active",
        )
    with httpx.Client(
        base_url=os.environ["CUOTI_LEGACY_URL"], trust_env=False, timeout=20
    ) as old:
        result = old.post(
            "/api/v1/tutor/sessions/" + sid + "/finish", headers=headers, json={}
        )
        assert result.status_code == 200, result.text
    with app.state.database.session() as db:
        updates = rows(
            db, "SELECT evidence FROM cognitive_updates WHERE question_id=?", [q]
        )
        assert len(updates) == 2
        recorded = json.loads(updates[0]["evidence"])["memory_source"][
            "question_version"
        ]
        question = select_rows(
            db, "questions", "SELECT * FROM questions WHERE id=?", [q]
        )[0]
        from pathlib import Path
        from unittest.mock import patch

        from cuoti_backend.lessons import digest

        captured = []

        def capture(value):
            captured.append(value)
            return digest(value)

        with patch("cuoti_backend.learning_evidence.digest", side_effect=capture):
            actual = question_version(db, question)
        (
            Path(app.state.settings.project_root) / ".runtime/学习来源指纹核对.json"
        ).write_text(
            json.dumps(
                {"expected": recorded, "actual": actual, "source_json": captured[-1]},
                ensure_ascii=False,
            )
        )
        assert actual == recorded


def test_tutor_dialogue_persistence_and_stale_write_protection(
    question_app, monkeypatch
):
    app, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "student_steps": ["3x=19"],
            "correct_answer": "5",
            "knowledge_points": ["一元一次方程"],
        },
    ).json()["data"]["id"]
    sid = client.post(
        "/api/v1/tutor/sessions", headers=headers, json={"question_id": q}
    ).json()["data"]["id"]
    path = "/api/v1/tutor/sessions/" + sid
    observed = []
    flags = {"stale": False}

    def compute(operation, **values):
        observed.append((operation, values))
        if operation == "tutor_dialogue_prepare":
            return {"plan": {"tool_name": "step_alignment", "memory_source_ids": []}}
        assert operation == "tutor_dialogue_finish"
        if flags["stale"]:
            client.patch(
                "/api/v1/questions/" + q,
                headers=headers,
                json={"question_text": "3x+2=20"},
            )
        return {
            "reply": "先检查移项符号。",
            "graph": {
                "branch": "step_check",
                "strategy": "socratic",
                "next_goal": "检查移项",
                "mastery_proven": False,
                "stage": "understanding",
                "hint_level": 1,
            },
            "agent": {
                "tool": {
                    "evidence": {"note": "核对当前步骤"},
                    "executed": True,
                    "consumed_input": {},
                },
                "verification": {"status": "verified"},
                "planner_status": "rule",
                "observation": {},
                "plan": values["dialogue_preparation"]["plan"],
            },
        }

    monkeypatch.setattr(app.state.compute, "compute", compute)
    assert (
        client.post(path + "/turns", headers=headers, json={"message": " "}).status_code
        == 422
    )
    assert (
        client.post(
            path + "/turns", headers=other, json={"message": "怎么办"}
        ).status_code
        == 404
    )
    one = client.post(path + "/turns", headers=headers, json={"message": "移项怎么办"})
    assert one.status_code == 200, one.text
    assert (
        one.json()["data"]["stage"] == "understanding"
        and one.json()["data"]["mastery_proven"] is False
    )
    assert [v[0] for v in observed] == [
        "tutor_dialogue_prepare",
        "tutor_dialogue_finish",
    ]
    assert observed[0][1]["dialogue_context"]["memory_snapshot"]["entries"] == []
    assert client.get(path, headers=headers).json()["data"]["turn_count"] == 1
    assert (
        client.post(
            path + "/turns", headers=headers, json={"message": "移项怎么办"}
        ).status_code
        == 200
    )
    assert observed[-1][1]["dialogue_context"]["repeated_count"] == 1
    flags["stale"] = True
    assert (
        client.post(
            path + "/turns", headers=headers, json={"message": "再看看"}
        ).status_code
        == 409
    )
    with app.state.database.session() as db:
        assert (
            len(rows(db, "SELECT id FROM tutor_turns WHERE session_id=?", [sid])) == 5
        )
        assert not rows(db, "SELECT id FROM cognitive_updates WHERE question_id=?", [q])
        runs = rows(
            db,
            "SELECT result FROM agent_runs WHERE session_id=? AND JSON_EXTRACT(result,'$.memory_manifest') IS NOT NULL",
            [sid],
        )
        assert len(runs) == 2


def test_learning_memory_current_stale_and_user_isolation(question_app):
    from cuoti_backend.learning_evidence import complete
    from cuoti_backend.learning_memory import memory
    from cuoti_backend.question_data import select_rows
    from cuoti_backend.tutoring import session_owned

    app, client, student, _ = question_app
    user, headers = student()
    other, _ = student()
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "student_steps": ["3x=15"],
            "correct_answer": "5",
            "knowledge_points": ["一元一次方程"],
        },
    ).json()["data"]["id"]
    with app.state.database.session() as db, db.begin():
        sid = insert(
            db,
            "tutor_sessions",
            user_id=user["id"],
            question_id=q,
            stage="far_transfer",
            hint_level=0,
            turn_count=0,
            mastery_score=0,
            state={"teach_back": True, "near_transfer": True, "far_transfer": True},
            status="active",
        )
        session = session_owned(db, sid, user["id"])
        complete(
            app.state.questions,
            db,
            session,
            app.state.questions.detail(db, q, user["id"]),
            False,
        )
        update_question = select_rows(
            db, "questions", "SELECT * FROM questions WHERE id=?", [q]
        )[0]
        execute(
            db,
            "UPDATE misconception_states SET status='resolved' WHERE user_id=?",
            [user["id"]],
        )
        result = memory(db, user["id"], update_question)
        assert {entry["kind"] for entry in result["snapshot"]["entries"]} == {
            "mastery",
            "cognitive",
            "review",
        }
        execute(
            db,
            "UPDATE misconception_states SET status='active' WHERE user_id=?",
            [user["id"]],
        )
        result = memory(db, user["id"], update_question)
        kinds = {entry["kind"] for entry in result["snapshot"]["entries"]}
        assert kinds == {"mastery", "misconception", "cognitive", "review"}
        assert (
            next(e for e in result["snapshot"]["entries"] if e["kind"] == "cognitive")[
                "outcome"
            ]
            == "correct"
        )
        assert memory(db, other["id"], update_question)["snapshot"]["entries"] == []
        execute(db, "UPDATE questions SET question_text=? WHERE id=?", ["3x+2=20", q])
        changed = select_rows(
            db, "questions", "SELECT * FROM questions WHERE id=?", [q]
        )[0]
        stale = memory(db, user["id"], changed)
        assert (
            not stale["legacy_rows"]["updates"] and not stale["legacy_rows"]["mastery"]
        )


@pytest.mark.skipif(
    os.environ.get("CUOTI_TEST_REAL_DIALOGUE") != "1",
    reason="real teaching Agent not enabled",
)
def test_real_tutor_agent_dialogue_roundtrip(question_app):
    import json
    from pathlib import Path

    started = time.perf_counter()
    app, client, student, _ = question_app
    app.state.algorithm_app.state.provider = None
    _, headers = student()
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "student_steps": ["3x=19"],
            "correct_answer": "5",
            "explanation": "等式两边同时减2，再除以3",
            "knowledge_points": ["一元一次方程"],
        },
    ).json()["data"]["id"]
    start = client.post(
        "/api/v1/tutor/sessions", headers=headers, json={"question_id": q}
    )
    assert start.status_code == 200, start.text
    sid = start.json()["data"]["id"]
    response = client.post(
        "/api/v1/tutor/sessions/" + sid + "/turns",
        headers=headers,
        json={"message": "请帮我检查第一步移项为什么错了？"},
    )
    output = Path(app.state.settings.project_root) / ".runtime/真实教学对话验证.jsonl"
    with output.open("a") as file:
        file.write(
            json.dumps(
                {
                    "elapsed_seconds": round(time.perf_counter() - started, 2),
                    "status_code": response.status_code,
                    "result": response.json(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["message"] and response.json()["data"]["tool_name"]
    assert response.json()["data"]["stage"] == "understanding"
    with app.state.database.session() as db:
        assert (
            len(rows(db, "SELECT id FROM tutor_turns WHERE session_id=?", [sid])) == 3
        )
        assert not rows(db, "SELECT id FROM cognitive_updates WHERE question_id=?", [q])


def test_task_source_capture_real_database(question_app):
    from cuoti_backend.learning_memory import task_fingerprint
    from cuoti_backend.protocol import ApiError
    from cuoti_backend.task_sources import (
        TaskSourceError,
        capture_source,
        load_snapshot,
        validate_version,
    )

    app, client, student, _ = question_app
    user, headers = student()
    other, _ = student()
    q = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={"question_text": "3x=15", "correct_answer": "5"},
    ).json()["data"]["id"]
    tid = str(uuid4())
    try:
        with app.state.database.session() as db, db.begin():
            current = load_snapshot(db, q, user["id"])
            fingerprint = task_fingerprint(db, q, user["id"])
            insert(
                db,
                "learning_tasks",
                id=tid,
                user_id=user["id"],
                question_id=q,
                input_fingerprint=fingerprint,
                status="waiting_student",
                step_id=str(uuid4()),
                checkpoint={},
                student_view={},
                pending_action={},
            )
            task = {
                "id": tid,
                "input_fingerprint": fingerprint,
                "status": "waiting_student",
                "version": 1,
            }
            from cuoti_backend.task_budget import TaskBudget
            from cuoti_backend.task_leases import claim_lease

            execute(db, "UPDATE learning_tasks SET status='queued' WHERE id=?", [tid])
            reserved = claim_lease(db, tid, TaskBudget())
            assert reserved and reserved["lease"]
            assert reserved["context"]["question_id"] == q
            assert reserved["context"]["source_snapshot_id"] == tid
            assert reserved["context"]["action_id"] == tid + ":"
            from learning_task_compute import TaskContext

            assert TaskContext.model_validate(reserved["context"]).question_id == q

            assert claim_lease(db, tid, TaskBudget()) is None
            execute(
                db,
                "UPDATE learning_tasks SET lease_until=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id=?",
                [tid],
            )
            recovered = claim_lease(db, tid, TaskBudget())
            assert recovered["lease"] != reserved["lease"]
            assert (
                rows(db, "SELECT run_count FROM learning_tasks WHERE id=?", [tid])[0][
                    "run_count"
                ]
                == 2
            )
            assert validate_version(db, task, current)
            assert capture_source(db, task, current) == current
            assert capture_source(db, task, current) == current
            assert (
                len(
                    rows(
                        db,
                        "SELECT task_id FROM learning_task_sources WHERE task_id=?",
                        [tid],
                    )
                )
                == 1
            )
            with pytest.raises(ApiError):
                load_snapshot(db, q, other["id"])
        from cuoti_backend.question_data import select_rows
        from cuoti_backend.task_results import save_traces

        with app.state.database.session() as db, db.begin():
            full_task = select_rows(
                db, "learning_tasks", "SELECT * FROM learning_tasks WHERE id=?", [tid]
            )[0]
            full_task["active_request"] = "__initial__"
            result = {
                "status": "needs_review",
                "traces": [
                    {
                        "tool_name": "check_step",
                        "validation": "needs_review",
                        "memory_refs": [],
                        "evidence": {},
                    }
                ],
                "attempt": {"phase": "repair", "source": {"student_step_id": "forged"}},
                "elapsed_ms": 1,
                "usage": {},
            }
            save_traces(db, full_task, result, TaskBudget(), {"entries": []}, {})
            assert result["attempt"]["source"]["snapshot_id"] == tid
            assert result["attempt"]["source"]["student_step_id"] is None
            assert (
                len(
                    rows(
                        db, "SELECT id FROM learning_task_steps WHERE task_id=?", [tid]
                    )
                )
                == 1
            )
        client.patch(
            "/api/v1/questions/" + q, headers=headers, json={"question_text": "3x=18"}
        )
        with app.state.database.session() as db, pytest.raises(TaskSourceError):
            capture_source(db, task, load_snapshot(db, q, user["id"]))
        with app.state.database.session() as db, db.begin():
            assert not validate_version(db, task, load_snapshot(db, q, user["id"]))
            assert rows(
                db, "SELECT status,version FROM learning_tasks WHERE id=?", [tid]
            )[0] == {"status": "stale", "version": 2}
    finally:
        with app.state.database.session() as db, db.begin():
            runs = rows(
                db,
                "SELECT agent_run_id FROM learning_task_steps WHERE task_id=?",
                [tid],
            )
            execute(db, "DELETE FROM learning_task_steps WHERE task_id=?", [tid])
            for run in runs:
                execute(
                    db,
                    "DELETE FROM agent_tool_calls WHERE agent_run_id=?",
                    [run["agent_run_id"]],
                )
                execute(db, "DELETE FROM agent_runs WHERE id=?", [run["agent_run_id"]])
            execute(db, "DELETE FROM learning_task_sources WHERE task_id=?", [tid])
            execute(db, "DELETE FROM learning_tasks WHERE id=?", [tid])


def test_task_plan_candidates_real_database_scope(question_app):
    from cuoti_backend.question_data import select_rows
    from cuoti_backend.task_context import prepare_context
    from cuoti_backend.task_planning import plan_candidates
    from cuoti_backend.task_sources import load_snapshot

    app, client, student, _ = question_app
    user, headers = student()
    q = client.post(
        "/api/v1/questions/manual", headers=headers, json={"question_text": "3x=15"}
    ).json()["data"]["id"]
    with app.state.database.session() as db:
        question = select_rows(
            db, "questions", "SELECT * FROM questions WHERE id=?", [q]
        )[0]
        candidates = plan_candidates(db, user["id"], question, [])
        context = prepare_context(
            db, load_snapshot(db, q, user["id"], lock=False), user["id"]
        )
        assert context["question_id"] == q and context["expected"] == ""
        assert context["practice_candidates"] == candidates
        assert context["memory_snapshot"]["rule_version"] == "learning-memory-v1"
        assert context["student_step_ids"] == []

        assert len(candidates) <= 200
        assert all(
            c["subject"] == question["subject"] and c["id"] != q for c in candidates
        )
