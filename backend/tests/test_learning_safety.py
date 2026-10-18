from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import BackgroundTasks, HTTPException

from app.auth import create_access_token, hash_password, verify_password
from app.config import settings
from app.db import get_db
from app.main import app, apply_ocr_edits, attempt_practice, grade_review, reset_password, retry_job
from app.models import (
    DatasetPracticeAttempt,
    DatasetQuestion,
    DiagnosisEvidence,
    Paper,
    PracticeRecommendation,
    ProcessingJob,
    Question,
    QuestionAsset,
    ReviewPlan,
    ReviewRecord,
    StudentStep,
    TutorSession,
    User,
    VariantQuestion,
    VisualizationSpec,
)
from app.providers.api_pool import ApiPoolUnavailable
from app.schemas import CroppedQuestionRecognition, PracticeAttemptRequest
from app.services.question_lifecycle import (
    invalidate_question_learning,
    question_source_fingerprint,
    recover_interrupted_recognition,
)
from app.services.vision import MAX_UPLOAD_BYTES


class Rows(list):
    def first(self):
        return self[0] if self else None


class FakeDb:
    def __init__(self, *rows):
        self.rows = {(type(row), row.id): row for row in rows}
        self.added = []
        self.executed = []
        self.get_options = []
        self.commits = 0

    async def get(self, model, row_id, **options):
        self.get_options.append((model, options))
        return self.rows.get((model, row_id))

    async def scalars(self, statement):
        model = statement.column_descriptions[0]["entity"]
        return Rows(row for (kind, _), row in self.rows.items() if kind is model)

    async def execute(self, statement):
        self.executed.append(statement)
        return Rows()

    async def scalar(self, _statement):
        return None

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        for index, row in enumerate(self.added):
            if row.id is None:
                row.id = f"created-{index}"

    async def commit(self):
        await self.flush()
        self.commits += 1

    async def rollback(self):
        return None


@pytest.fixture
def db_override():
    account = User(
        id="student",
        email="student@example.test",
        name="Student",
        role="student",
        password_hash="test-password-hash",
    )
    db = FakeDb(account)

    async def dependency():
        yield db

    app.dependency_overrides[get_db] = dependency
    yield db, account
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/questions/unknown",
        "/jobs/unknown",
        "/tutor/sessions/unknown",
        "/papers/unknown",
        "/visualizations/unknown",
        "/questions/unknown/diagnosis",
    ],
)
async def test_legacy_resource_routes_require_login(db_override, path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1" + path)
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "path", "extra"),
    [
        (Question, "/questions/private", {"user_id": "other"}),
        (Paper, "/papers/private", {"user_id": "other"}),
        (TutorSession, "/tutor/sessions/private", {"user_id": "other"}),
        (ProcessingJob, "/jobs/private", {"question_id": "other-question"}),
        (VisualizationSpec, "/visualizations/private", {"session_id": "other-session"}),
    ],
)
async def test_resource_routes_reject_other_accounts(db_override, model, path, extra):
    db, account = db_override
    db.rows[(model, "private")] = model(id="private", **extra)
    db.rows[(Question, "other-question")] = Question(id="other-question", user_id="other")
    db.rows[(TutorSession, "other-session")] = TutorSession(id="other-session", user_id="other")
    headers = {
        "Authorization": "Bearer "
        + create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1" + path, headers=headers)
    assert response.status_code == 404
    assert db.commits == 0


@pytest.mark.asyncio
async def test_archiving_owned_question_preserves_rows_and_cancels_review(db_override):
    db, account = db_override
    question = Question(id="mine", user_id=account.id, status="diagnosed")
    plan = ReviewPlan(id="plan", user_id=account.id, question_id=question.id, status="pending")
    db.rows.update({(Question, question.id): question, (ReviewPlan, plan.id): plan})
    headers = {
        "Authorization": "Bearer "
        + create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/v1/questions/mine", headers=headers)
    assert response.status_code == 200
    assert question.status == "archived"
    assert plan.status == "cancelled"
    assert not db.executed


@pytest.mark.asyncio
async def test_changed_question_blocks_old_tutor_and_variant(db_override):
    db, account = db_override
    session = TutorSession(id="old", user_id=account.id, state={"question_changed": True})
    variant = VariantQuestion(id="variant", session_id=session.id)
    db.rows.update({(TutorSession, session.id): session, (VariantQuestion, variant.id): variant})
    headers = {
        "Authorization": "Bearer "
        + create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tutor/sessions/old", headers=headers)
        attempt = await client.post("/api/v1/variants/variant/attempt", headers=headers, json={"answer": "A"})
    assert response.status_code == 409
    assert attempt.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["understanding", "near_transfer", "far_transfer"])
async def test_tutor_response_keeps_progress_without_exposing_marking_keys(db_override, monkeypatch, stage):
    from app import main

    db, account = db_override
    question = Question(
        id="question",
        user_id=account.id,
        title="方程练习",
        question_text="解方程",
        subject="数学",
        question_type="填空题",
        knowledge_points=[],
    )
    activity = {
        "id": "check",
        "type": "short_answer",
        "title": "试一试",
        "question": "求解",
        "correct_answers": ["hidden-micro-answer"],
    }
    session = TutorSession(
        id="session",
        user_id=account.id,
        question_id=question.id,
        stage=stage,
        state={
            "understanding_plan": [activity],
            "understanding_index": 0,
            "teaching_brief": {"check": {"correct_answers": ["hidden-targeted-answer"]}},
            "near_confirmation": None,
            "near_variant_id": "variant",
            "far_variant_id": "variant",
            "transfer_insufficient": False,
            "assisted": False,
            "answer_reveal": {"correct_answer": "有意展示的原题讲解"},
        },
    )
    variant = VariantQuestion(
        id="variant",
        session_id=session.id,
        question_id=question.id,
        question_text="迁移题题干",
        answer="hidden-transfer-answer",
        explanation="hidden-transfer-explanation",
        reference_solution=["hidden-transfer-solution"],
    )
    db.rows.update(
        {
            (Question, question.id): question,
            (TutorSession, session.id): session,
            (VariantQuestion, variant.id): variant,
        }
    )

    async def prepared_context(*_args):
        return question, None, []

    monkeypatch.setattr(main, "ensure_tutor_activity_state", prepared_context)
    headers = {
        "Authorization": "Bearer "
        + create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tutor/sessions/session", headers=headers)
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["state"]["transfer_insufficient"] is False
    assert result["answer_reveal"]["correct_answer"] == "有意展示的原题讲解"
    assert "correct_answers" not in response.text
    assert "hidden-" not in response.text
    assert session.state["understanding_plan"][0]["correct_answers"] == ["hidden-micro-answer"]


@pytest.mark.asyncio
@pytest.mark.parametrize("transfer", ["near", "far"])
async def test_variant_response_does_not_reveal_answer_before_attempt(db_override, transfer):
    db, account = db_override
    session = TutorSession(
        id="session",
        user_id=account.id,
        question_id="question",
        stage=f"{transfer}_transfer",
        state={f"{transfer}_variant_id": "variant"},
    )
    variant = VariantQuestion(
        id="variant",
        session_id=session.id,
        question_id="question",
        transfer_type=transfer,
        question_text="可以看见的练习题",
        answer="hidden-answer",
        explanation="hidden-explanation",
        reference_solution=["hidden-solution"],
        generation_metadata={"answer": "hidden-metadata-answer"},
    )
    db.rows.update({(TutorSession, session.id): session, (VariantQuestion, variant.id): variant})
    headers = {
        "Authorization": "Bearer "
        + create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tutor/sessions/session/variant", headers=headers, json={"transfer_type": transfer}
        )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["question_text"] == "可以看见的练习题"
    assert result["id"] == variant.id and result["transfer_type"] == transfer
    assert not {"answer", "explanation", "reference_solution", "generation_metadata"} & result.keys()
    assert "hidden-" not in response.text


@pytest.mark.asyncio
async def test_ai_failure_is_retryable_and_does_not_expose_provider_details(db_override, monkeypatch):
    from app import main

    db, account = db_override
    question = Question(id="mine", user_id=account.id, confirmed=True, question_text="请分析文章")
    db.rows[(Question, question.id)] = question

    async def fail(*_args, **_kwargs):
        raise ApiPoolUnavailable("pretend-private-provider-detail")

    monkeypatch.setattr(main, "analyze_question", fail)
    headers = {
        "Authorization": "Bearer "
        + create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/questions/mine/analyze", headers=headers)
    assert response.status_code == 503
    assert "pretend-private" not in response.text
    assert db.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_stage", ["hybrid", "rerank"])
async def test_practice_dependency_failure_returns_safe_retryable_json(
    db_override, monkeypatch, failed_stage
):
    from app import main
    from app.services.practice_retrieval import RetrievalCandidate

    db, account = db_override
    mistake = Question(
        id="mine",
        user_id=account.id,
        title="方程练习",
        question_text="解方程2x=8",
        subject="数学",
        grade="初一",
        question_type="计算题",
    )
    db.rows[(Question, mistake.id)] = mistake
    candidate = RetrievalCandidate(
        DatasetQuestion(id="candidate", question_text="小明花掉三元钱，还剩多少钱？"),
        "test",
        [],
        1,
        1,
        1,
        0.8,
    )

    async def cards(*_args):
        return []

    async def fail(*_args):
        request = httpx.Request("POST", "http://dependency.invalid")
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("private-dependency-error", request=request, response=response)

    async def hybrid(*_args):
        return [candidate], {}, {}

    async def load(*_args):
        return [candidate]

    monkeypatch.setattr(main, "_practice_knowledge", cards)
    monkeypatch.setattr(main, "hybrid_ids", fail if failed_stage == "hybrid" else hybrid)
    monkeypatch.setattr(main, "load_candidates", load)
    monkeypatch.setattr(main, "rerank_candidates", fail)
    headers = {
        "Authorization": "Bearer "
        + create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/practice/recommend",
            headers=headers,
            json={"mistake_id": mistake.id, "mode": "reinforce", "force_new": True},
        )
    assert response.status_code == 503
    assert "服务" in response.json()["detail"]
    assert "private-dependency-error" not in response.text
    assert "dependency.invalid" not in response.text
    assert not db.added and db.commits == 0


@pytest.mark.asyncio
async def test_password_change_requires_current_password():
    account = User(id="account", email="student@example.test", password_hash=hash_password("old-password"))
    db = FakeDb(account)
    with pytest.raises(HTTPException) as error:
        await reset_password({"email": account.email, "new_password": "hijacked"}, db)
    assert error.value.status_code == 401
    assert verify_password("old-password", account.password_hash)
    await reset_password(
        {"email": account.email, "current_password": "old-password", "new_password": "new-password"}, db
    )
    assert verify_password("new-password", account.password_hash)


@pytest.mark.asyncio
async def test_review_completion_is_locked_and_cannot_be_consumed_twice():
    account = User(id="student")
    plan = ReviewPlan(id="plan", user_id=account.id, question_id="question", status="pending")
    record = ReviewRecord(
        id="answer",
        plan_id=plan.id,
        grade="pending",
        correct=True,
        grading_details={"can_update_learning": True},
    )
    other_record = ReviewRecord(
        id="second-answer",
        plan_id=plan.id,
        grade="pending",
        correct=True,
        grading_details={"can_update_learning": True},
    )
    db = FakeDb(plan, record, other_record)
    await grade_review(plan.id, {"attempt_id": record.id, "grade": "good"}, account, db)
    with pytest.raises(HTTPException) as error:
        await grade_review(plan.id, {"attempt_id": other_record.id, "grade": "easy"}, account, db)
    assert error.value.status_code == 409
    assert len([row for row in db.added if isinstance(row, ReviewPlan)]) == 1
    assert all(options.get("with_for_update") for model, options in db.get_options if model is ReviewPlan)


@pytest.mark.asyncio
async def test_review_completion_rejects_other_owner_and_unknown_grade():
    account = User(id="student")
    plan = ReviewPlan(id="plan", user_id="other", question_id="question", status="pending")
    record = ReviewRecord(
        id="answer",
        plan_id=plan.id,
        grade="pending",
        correct=True,
        grading_details={"can_update_learning": True},
    )
    db = FakeDb(plan, record)
    with pytest.raises(HTTPException) as error:
        await grade_review(plan.id, {"attempt_id": record.id}, account, db)
    assert error.value.status_code == 404
    plan.user_id = account.id
    with pytest.raises(HTTPException) as error:
        await grade_review(plan.id, {"attempt_id": record.id, "grade": "invalid"}, account, db)
    assert error.value.status_code == 422
    assert plan.status == "pending"


@pytest.mark.asyncio
async def test_completed_practice_cannot_repeat_grading_or_mastery_update(monkeypatch):
    from app import main

    account = User(id="student")
    mistake = Question(id="mistake", user_id=account.id, status="diagnosed")
    exercise = DatasetQuestion(id="exercise", usable_for_auto_grade=True)
    attempt = DatasetPracticeAttempt(
        id="attempt",
        user_id=account.id,
        mistake_id=mistake.id,
        dataset_question_id=exercise.id,
        mode="reinforce",
    )
    db = FakeDb(mistake, exercise, attempt)

    async def unexpected_grade(*_args, **_kwargs):
        raise AssertionError("A repeated attempt must not call the model")

    monkeypatch.setattr(main, "grade_answer", unexpected_grade)
    payload = PracticeAttemptRequest(
        mistake_id=mistake.id,
        question_id=exercise.id,
        mode="reinforce",
        student_answer="A",
        duration_seconds=5,
    )
    with pytest.raises(HTTPException) as error:
        await attempt_practice(payload, account, db)
    assert error.value.status_code == 409
    assert (Question, {"with_for_update": True, "populate_existing": True}) in db.get_options
    assert not db.added and db.commits == 0


@pytest.mark.asyncio
async def test_uncertain_practice_can_be_retried_without_learning_updates(monkeypatch):
    from app import main

    account = User(id="student")
    mistake = Question(
        id="mistake",
        user_id=account.id,
        status="diagnosed",
        subject="数学",
        question_type="选择题",
        title="函数",
        knowledge_points=["函数"],
    )
    exercise = DatasetQuestion(
        id="exercise",
        usable_for_auto_grade=True,
        question_text="函数的值",
        answer="A",
        subject="数学",
        question_type="选择题",
        options=[],
    )
    served = PracticeRecommendation(
        id="served",
        user_id=account.id,
        mistake_id=mistake.id,
        dataset_question_id=exercise.id,
        mode="reinforce",
        retrieval_trace={"source_question_fingerprint": question_source_fingerprint(mistake)},
    )
    db = FakeDb(mistake, exercise, served)

    async def uncertain_grade(*_args, **_kwargs):
        return {
            "correct": False,
            "method": "unverified",
            "can_update_learning": False,
            "verdict": "review_required",
            "confidence": 0.2,
            "evidence": [],
            "feedback": "请稍后重试",
        }

    monkeypatch.setattr(main, "grade_answer", uncertain_grade)
    payload = PracticeAttemptRequest(
        mistake_id=mistake.id,
        question_id=exercise.id,
        mode="reinforce",
        student_answer="A",
        duration_seconds=5,
    )
    first = await attempt_practice(payload, account, db)
    second = await attempt_practice(payload, account, db)
    assert not first["data"]["can_update_learning"] and not second["data"]["can_update_learning"]
    assert not db.added


@pytest.mark.asyncio
async def test_invalidation_removes_dependent_evidence_first_and_keeps_history():
    question = Question(id="question", confirmed=True)
    session = TutorSession(
        id="session", question_id=question.id, status="completed", state={"teach_back": True}
    )
    plan = ReviewPlan(id="plan", question_id=question.id, status="pending")
    db = FakeDb(session, plan)
    await invalidate_question_learning(db, question)
    assert [statement.table.name for statement in db.executed] == [
        "diagnosis_evidence",
        "diagnoses",
        "reference_steps",
        "problem_analyses",
        "user_question_knowledge_links",
        "practice_recommendations",
    ]
    assert session.status == "completed"
    assert session.state == {"teach_back": True, "question_changed": True}
    assert plan.status == "cancelled"


@pytest.mark.asyncio
async def test_ocr_correction_rebuilds_formula_from_text_and_preserves_old_steps():
    question = Question(
        id="question", user_id="student", confirmed=True, question_type="计算题", question_text="x+1=3"
    )
    db = FakeDb()
    await apply_ocr_edits(question, {"student_steps": [{"text": "x=2", "formula": "x=4"}]}, db)
    step = next(row for row in db.added if isinstance(row, StudentStep))
    assert step.formula == "x=2"
    assert all(statement.table.name != "student_steps" for statement in db.executed)
    assert any(statement.table.name == DiagnosisEvidence.__tablename__ for statement in db.executed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"question_text": None},
        {"student_steps": 123},
        {"options": {}},
        {"student_steps": [{"text": "x=2", "confidence": "not-a-number"}]},
        {"student_steps": [{"text": "x=2", "confidence": 2}]},
        {"teacher_marks": [{"comment": None}]},
    ],
)
async def test_invalid_ocr_edits_are_422_before_any_data_is_changed(payload):
    question = Question(id="question", question_text="原题")
    db = FakeDb()
    with pytest.raises(HTTPException) as error:
        await apply_ocr_edits(question, payload, db)
    assert error.value.status_code == 422
    assert question.question_text == "原题"
    assert not db.added and not db.executed


@pytest.mark.asyncio
@pytest.mark.parametrize("box", [None, [0, 0, 1], [0, 0, 0, 1], [0.9, 0, 0.5, 1], ["bad", 0, 1, 1]])
async def test_invalid_crop_geometry_is_a_user_error_not_server_failure(db_override, box):
    db, account = db_override
    db.rows[(Question, "mine")] = Question(id="mine", user_id=account.id)
    headers = {
        "Authorization": "Bearer "
        + create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/questions/mine/crop", headers=headers, json={"box": box})
    assert response.status_code == 422
    assert not db.added and db.commits == 0


@pytest.mark.asyncio
async def test_startup_recovers_only_unfinished_recognition_jobs():
    class RecoveryDb(FakeDb):
        async def scalars(self, statement):
            rows = await super().scalars(statement)
            return Rows(
                row
                for row in rows
                if row.status in {"pending", "running"} and row.kind in {"ingest", "crop", "ocr", "reprocess"}
            )

    question = Question(id="question", status="processing")
    archived = Question(id="archived", status="archived")
    pending = ProcessingJob(id="pending", question_id=question.id, kind="ingest", status="pending")
    running = ProcessingJob(id="running", question_id=archived.id, kind="crop", status="running")
    completed = ProcessingJob(
        id="completed", question_id=question.id, kind="ocr", status="completed", error=None
    )
    db = RecoveryDb(question, archived, pending, running, completed)
    assert await recover_interrupted_recognition(db) == 2
    assert pending.status == running.status == "failed"
    assert "重启中断" in pending.error
    assert question.status == "partial" and archived.status == "archived"
    assert completed.status == "completed" and completed.error is None
    assert await recover_interrupted_recognition(db) == 0


@pytest.mark.asyncio
async def test_failed_original_ingest_can_retry_once_without_overwriting_the_original(tmp_path):
    original_path = tmp_path / "original.jpg"
    original_path.write_bytes(b"preserved original")
    question = Question(id="question", status="partial")
    job = ProcessingJob(id="job", question_id=question.id, kind="ingest", status="failed", progress=45)
    asset = QuestionAsset(id="asset", question_id=question.id, kind="original", path=str(original_path))

    class RetryDb(FakeDb):
        async def scalars(self, statement):
            rows = await super().scalars(statement)
            if statement.column_descriptions[0]["entity"] is ProcessingJob:
                return Rows(row for row in rows if row.status in {"pending", "running"})
            kinds = {
                value
                for value in statement.compile().params.values()
                if isinstance(value, str) and value in {"original", "crop"}
            }
            return Rows(row for row in rows if row.kind in kinds)

    db = RetryDb(question, job, asset)
    background = BackgroundTasks()
    await retry_job(job.id, background, db)
    assert job.status == "pending" and job.progress == 0 and question.status == "processing"
    assert len(background.tasks) == 1
    assert background.tasks[0].kwargs["require_crop"] is False
    assert original_path.read_bytes() == b"preserved original"
    with pytest.raises(HTTPException) as error:
        await retry_job(job.id, background, db)
    assert error.value.status_code == 409
    assert len(background.tasks) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "status"),
    [(b"", 422), (b"not-an-image", 422), (b"x" * (MAX_UPLOAD_BYTES + 1), 413)],
    ids=["empty", "invalid", "oversized"],
)
async def test_upload_rejects_empty_invalid_and_oversized_images(
    db_override, monkeypatch, tmp_path, raw, status
):
    db, account = db_override
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    headers = {
        "Authorization": "Bearer "
        + create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/questions/ingest",
            headers=headers,
            files={"file": ("image.jpg", raw, "image/jpeg")},
            data={"defer_processing": "true"},
        )
    assert response.status_code == status
    assert db.commits == 0
    assert not list(tmp_path.rglob("original.jpg"))


@pytest.mark.asyncio
@pytest.mark.parametrize("recognition_fails", [False, True])
async def test_archiving_during_recognition_cannot_be_undone_by_success_or_failure(
    monkeypatch, tmp_path, recognition_fails
):
    from app import main

    question = Question(id="question", user_id="student", status="processing")
    job = ProcessingJob(id="job", question_id=question.id, kind="ingest", status="pending")
    original = tmp_path / question.id / "original.jpg"
    original.parent.mkdir()
    original.write_bytes(b"unchanged original")
    asset = QuestionAsset(id="asset", question_id=question.id, kind="original", path=str(original))
    db = FakeDb(question, job, asset)

    @asynccontextmanager
    async def session():
        yield db

    def preprocess(_original, *targets):
        for target in targets:
            target.write_bytes(b"derived image")

    async def recognize(*_args, **_kwargs):
        question.status = "archived"
        if recognition_fails:
            raise RuntimeError("recognition interrupted after archive")
        return CroppedQuestionRecognition(question_text="新识别的题目", subject="数学")

    monkeypatch.setattr(main, "SessionLocal", session)
    monkeypatch.setattr(main, "preprocess_image", preprocess)
    monkeypatch.setattr(main, "recognize_cropped_question", recognize)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    await main.process_question(job.id, question.id, str(original))
    assert question.status == "archived"
    assert job.status == "cancelled"
    assert original.read_bytes() == b"unchanged original"
    assert not any(isinstance(row, StudentStep) for row in db.added)
    assert (Question, {"with_for_update": True, "populate_existing": True}) in db.get_options


def test_startup_ai_probe_is_opt_in():
    assert type(settings).model_fields["ai_probe_on_startup"].default is False
