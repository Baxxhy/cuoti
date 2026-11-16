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
    body = {"study_session_id": session_id, "study_item_id": item_id}
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
    assert (
        detail["question_figures"]
        and client.get(detail["question_figures"][0]["url"]).content == picture()
    )
