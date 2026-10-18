"""New student work retains history and atomically invalidates derived learning data."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def student_work(endpoint, env, query):
    def account():
        return request(
            endpoint,
            "POST",
            "/api/v1/auth/register",
            {
                "name": "作答测试",
                "email": f"work-{uuid4()}@example.test",
                "password": "test-password-123",
            },
        )

    user, other = account(), account()
    token = user["access_token"]
    q = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "解方程 x+1=2", "student_steps": ["旧步骤"]},
        token=token,
    )
    qid = q["id"]
    base = f"/api/v1/questions/{qid}"
    path = base + "/student-work"
    insert = fixture_insert(env, query)
    old_analysis = insert("problem_analyses", question_id=qid, subject="数学")
    reference = insert(
        "reference_steps", analysis_id=old_analysis, step_index=0, text="旧参考"
    )
    diagnosis = insert("diagnoses", question_id=qid)
    insert(
        "diagnosis_evidence",
        diagnosis_id=diagnosis,
        reference_step_id=reference,
        kind="step_alignment",
        content="旧证据",
    )
    job = insert("processing_jobs", question_id=qid, kind="ocr", status="running")
    review = insert(
        "review_plans",
        question_id=qid,
        user_id=user["id"],
        due_at="2026-10-01 00:00:00",
        status="pending",
    )
    request(endpoint, "POST", path, {}, expected=401)
    request(endpoint, "POST", path, {}, token=other["access_token"], expected=404)
    for payload in (
        {"answer": None},
        {"steps": [{}]},
        {"steps": ["x"] * 101},
        {"explanation": "x" * 12001},
    ):
        request(endpoint, "POST", path, payload, token=token, expected=422)
    query(
        env,
        "ALTER TABLE student_steps ADD CONSTRAINT work_failure CHECK (text <> 'rollback-work')",
    )
    try:
        request(
            endpoint,
            "POST",
            path,
            {"answer": "2", "steps": ["rollback-work"]},
            token=token,
            expected=503,
        )
        assert (
            query(
                env, f"SELECT COUNT(*) FROM problem_analyses WHERE id='{old_analysis}'"
            )
            == "1"
        )
        assert (
            query(env, f"SELECT status FROM processing_jobs WHERE id='{job}'")
            == "running"
        )
        assert (
            query(env, f"SELECT COUNT(*) FROM student_works WHERE question_id='{qid}'")
            == "1"
        )
    finally:
        query(env, "ALTER TABLE student_steps DROP CHECK work_failure")
    work = request(
        endpoint,
        "POST",
        path,
        {
            "answer": " 1 ",
            "explanation": "移项",
            "steps": [" x = 1 ", "核对"],
            "user_id": other["id"],
        },
        token=token,
    )
    assert work["user_id"] == user["id"] and work["question_id"] == qid
    assert work["answer"] == " 1 " and work["explanation"] == "移项"
    detail = request(endpoint, "GET", base, token=token)
    assert detail["status"] == "confirmed" and detail["student_answer"] == " 1 "
    assert detail["analysis"] is None and detail["diagnosis"] is None
    assert [s["text"] for s in detail["student_steps"]] == [" x = 1 ", "核对"]
    assert detail["student_steps"][0]["normalized_text"] == "x = 1"
    assert all(
        s["source"] == "user" and s["user_confirmed"] for s in detail["student_steps"]
    )
    assert (
        query(env, f"SELECT COUNT(*) FROM student_works WHERE question_id='{qid}'")
        == "2"
    )
    assert (
        query(env, f"SELECT status FROM processing_jobs WHERE id='{job}'")
        == "cancelled"
    )
    assert (
        query(env, f"SELECT status FROM review_plans WHERE id='{review}'")
        == "cancelled"
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda n: request(
                    endpoint,
                    "POST",
                    path,
                    {"answer": str(n), "steps": [f"step-{n}"]},
                    token=token,
                ),
                range(2),
            )
        )
    assert len({item["id"] for item in results}) == 2
    latest = max(results, key=lambda item: (item["created_at"], item["id"]))
    detail = request(endpoint, "GET", base, token=token)
    assert detail["student_answer"] == latest["answer"]
    assert detail["student_steps"][0]["work_id"] == latest["id"]
    empty = request(endpoint, "POST", path, {}, token=token)
    assert empty["answer"] == empty["explanation"] == ""
    detail = request(endpoint, "GET", base, token=token)
    assert detail["student_answer"] is None and detail["student_steps"] == []
    assert (
        query(env, f"SELECT COUNT(*) FROM student_works WHERE question_id='{qid}'")
        == "5"
    )
    request(endpoint, "DELETE", base, token=token)
    request(endpoint, "POST", path, {}, token=token, expected=409)
    print(
        "Cangjie student work passed: ownership, validation, rollback, history, invalidation, cancellation and concurrent latest revision"
    )
