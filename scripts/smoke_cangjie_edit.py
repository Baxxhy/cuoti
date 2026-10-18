"""Question edit contract and transactional learning invalidation verification."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def question_edit(endpoint, env, query):
    account = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"edit-{uuid4().hex}@example.test",
            "password": "test-password-123",
            "name": "编辑测试",
        },
    )
    token, owner = account["access_token"], account["id"]
    options = [{"label": "A", "text": "1"}, {"label": "B", "text": "2"}]
    created = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "question_text": "原题",
            "question_type": "单选题",
            "options": options,
            "student_steps": ["原作答"],
        },
        token=token,
    )
    qid = created["id"]
    path = "/api/v1/questions/" + qid
    insert = fixture_insert(env, query)
    analysis = insert("problem_analyses", question_id=qid, subject="数学")
    reference = insert(
        "reference_steps", analysis_id=analysis, step_index=0, text="旧参考"
    )
    diagnosis = insert("diagnoses", question_id=qid)
    insert(
        "diagnosis_evidence",
        diagnosis_id=diagnosis,
        kind="step_alignment",
        content="旧证据",
        reference_step_id=reference,
    )
    session = insert(
        "tutor_sessions", user_id=owner, question_id=qid, state={"keep": "保留"}
    )
    turn = insert("tutor_turns", session_id=session, role="user", content="保留对话")
    asset = insert(
        "question_assets", question_id=qid, kind="original", path="uploads/original.png"
    )
    knowledge = insert(
        "knowledge_points", code="edit-" + uuid4().hex, subject="数学", name="知识点"
    )
    insert(
        "user_question_knowledge_links",
        user_id=owner,
        question_id=qid,
        knowledge_point_id=knowledge,
    )
    source = insert("dataset_sources", key="edit-" + uuid4().hex, name="测试来源")
    dataset = insert(
        "dataset_questions",
        dataset_source_id=source,
        source_item_id="1",
        subject="数学",
        grade_band="初中",
        question_text="测试练习",
        content_hash="test",
    )
    insert(
        "practice_recommendations",
        user_id=owner,
        mistake_id=qid,
        dataset_question_id=dataset,
        mode="near",
    )
    attempt = insert(
        "dataset_practice_attempts",
        user_id=owner,
        mistake_id=qid,
        dataset_question_id=dataset,
        source_dataset="test",
        mode="near",
        student_answer=["1"],
        grading_details={"keep": 7},
    )
    pending = insert(
        "review_plans", user_id=owner, question_id=qid, due_at="2026-10-01 00:00:00"
    )
    completed = insert(
        "review_plans",
        user_id=owner,
        question_id=qid,
        due_at="2026-09-01 00:00:00",
        status="completed",
    )
    record = insert(
        "review_records", plan_id=completed, grade="good", grading_details={"score": 80}
    )
    other_q = insert("questions", user_id=owner, question_text="另题")
    other_analysis = insert("problem_analyses", question_id=other_q, subject="数学")
    empty_session = insert("tutor_sessions", user_id=owner, question_id=qid)
    query(env, f"UPDATE tutor_sessions SET state='null' WHERE id='{empty_session}'")
    empty_attempt = insert(
        "dataset_practice_attempts",
        user_id=owner,
        mistake_id=qid,
        dataset_question_id=dataset,
        source_dataset="test",
        mode="near",
        student_answer=[],
        grading_details=[],
    )
    empty_record = insert(
        "review_records", plan_id=completed, grade="good", grading_details=[]
    )

    def patch(payload, expected=200):
        return request(endpoint, "PATCH", path, payload, token=token, expected=expected)

    def scalar(table, field, id):
        return query(env, f"SELECT {field} FROM {table} WHERE id='{id}'")

    def exists(table, id):
        return scalar(table, "COUNT(*)", id) == "1"

    request(endpoint, "PATCH", path, {}, expected=401)
    other = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"edit-other-{uuid4().hex}@example.test",
            "password": "test-password-123",
            "name": "其他账号",
        },
    )
    request(
        endpoint,
        "PATCH",
        path,
        {"title": "越权"},
        token=other["access_token"],
        expected=404,
    )
    request(
        endpoint,
        "PATCH",
        "/api/v1/questions/" + str(uuid4()),
        {},
        token=token,
        expected=404,
    )
    same = patch(
        {
            "question_text": "原题",
            "options": [{"text": "1", "label": " A "}, {"text": "2", "label": "B"}],
            "subject": "\u3000数学\u3000",
            "student_steps": [{"text": "不会覆盖", "confidence": "0.5"}],
            "teacher_marks": ["不会覆盖"],
        }
    )
    assert same["options"] == options and exists("problem_analyses", analysis)
    metadata = patch(
        {
            "title": "新标题",
            "favorite": "YES",
            "tags": ["\u3000重点\u3000"],
            "user_id": other["id"],
            "status": "archived",
        }
    )
    assert (
        metadata["title"] == "新标题"
        and metadata["favorite"] is True
        and metadata["tags"] == ["重点"]
    )
    assert metadata["user_id"] == owner and metadata["status"] == "confirmed"
    assert exists("problem_analyses", analysis) and exists("diagnoses", diagnosis)
    assert json.loads(scalar("tutor_sessions", "state", session)) == {"keep": "保留"}
    for invalid in [
        {"subject": "　"},
        {"question_text": None},
        {"question_text": 123},
        {"title": "x" * 256},
        {"favorite": 2},
        {"tags": [""]},
        {"tags": ["x"] * 51},
        {"formulas": ["x"] * 101},
        {"options": [{"label": "A"}]},
        {"options": [{"label": "x" * 9, "text": ""}]},
        {"student_steps": [{"confidence": 1.1}]},
        {"student_steps": [{"confidence": "NaN"}]},
        {"teacher_marks": [{"bbox": [0] * 5}]},
        {"teacher_marks": [{"bbox": ["inf"]}]},
        {"student_steps": [123]},
        {"teacher_marks": [None]},
        {"grade": "x" * 31},
        {"knowledge_points": ["x" * 31]},
        {"question_type": ""},
        {"options": None},
    ]:
        patch(invalid, 422)
    assert exists("diagnoses", diagnosis)
    # Fail the final question UPDATE after all invalidation writes have run.
    query(
        env,
        f"ALTER TABLE questions ADD CONSTRAINT edit_failure CHECK (id <> '{qid}' OR question_text = '原题')",
    )
    try:
        patch({"question_text": "新题"}, 503)
        assert exists("problem_analyses", analysis) and exists("diagnoses", diagnosis)
        assert exists("reference_steps", reference)
        assert json.loads(scalar("tutor_sessions", "state", session)) == {
            "keep": "保留"
        }
        assert scalar("review_plans", "status", pending) == "pending"
        assert json.loads(
            scalar("dataset_practice_attempts", "grading_details", attempt)
        ) == {"keep": 7}
    finally:
        query(env, "ALTER TABLE questions DROP CHECK edit_failure")
    result = patch(
        {
            "question_text": "新题",
            "student_answer": None,
            "grade": None,
            "formulas": ["x=1"],
            "knowledge_points": [" 方程 "],
            "favorite": 0,
        }
    )
    assert result["question_text"] == "新题" and result["favorite"] is False
    assert result["knowledge_points"] == ["方程"] and result["status"] == "confirmed"
    for table, id in (
        ("problem_analyses", analysis),
        ("reference_steps", reference),
        ("diagnoses", diagnosis),
    ):
        assert not exists(table, id)
    for table, field in (
        ("diagnosis_evidence", "diagnosis_id"),
        ("user_question_knowledge_links", "question_id"),
        ("practice_recommendations", "mistake_id"),
    ):
        identifier = diagnosis if table == "diagnosis_evidence" else qid
        assert (
            query(env, f"SELECT COUNT(*) FROM {table} WHERE {field}='{identifier}'")
            == "0"
        )
    assert json.loads(scalar("tutor_sessions", "state", session)) == {
        "keep": "保留",
        "question_changed": True,
    }
    assert json.loads(
        scalar("dataset_practice_attempts", "grading_details", attempt)
    ) == {"keep": 7, "question_changed": True}
    assert json.loads(scalar("review_records", "grading_details", record)) == {
        "score": 80,
        "question_changed": True,
    }
    assert scalar("review_plans", "status", pending) == "cancelled"
    assert scalar("review_plans", "status", completed) == "completed"
    for table, field, id in (
        ("tutor_sessions", "state", empty_session),
        ("dataset_practice_attempts", "grading_details", empty_attempt),
        ("review_records", "grading_details", empty_record),
    ):
        assert json.loads(scalar(table, field, id)) == {"question_changed": True}
    assert (
        exists("tutor_turns", turn)
        and exists("question_assets", asset)
        and exists("problem_analyses", other_analysis)
    )
    details = request(endpoint, "GET", path, token=token)
    assert [s["text"] for s in details["student_steps"]] == ["原作答"]
    # Independent concurrent edits merge under the question row lock.
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(patch, [{"title": "并发标题"}, {"tags": ["并发标签"]}]))
    merged = request(endpoint, "GET", path, token=token)
    assert merged["title"] == "并发标题" and merged["tags"] == ["并发标签"]
    unconfirmed = request(
        endpoint,
        "PATCH",
        "/api/v1/questions/" + other_q,
        {"question_text": "修改待确认题"},
        token=token,
    )
    assert unconfirmed["status"] == "needs_confirmation"
    request(endpoint, "DELETE", path, token=token)
    patch({"question_text": "不能恢复"}, 409)
    assert scalar("questions", "status", qid) == "archived"
    print(
        "Cangjie edit passed: validation, field whitelist, metadata preservation, invalidation, history, rollback and concurrent edits"
    )
