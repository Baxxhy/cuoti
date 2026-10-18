"""Functional review cycle, visibility, feedback intervals and history."""

import json
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert
from smoke_cangjie_handwriting import handwriting


def reviews(endpoint, env, query, token, other, state):
    insert = fixture_insert(env, query)
    question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "question_text": "复习验证：解方程 4*x+2=22",
            "student_answer": "6",
            "question_type": "综合题",
        },
        token=token,
    )
    # Recognition can persist fill-blank types, while manual entry uses three broad categories.
    query(
        env, f"UPDATE questions SET question_type='填空题' WHERE id='{question['id']}'"
    )
    owner = query(
        env, f"SELECT user_id FROM questions WHERE id='{question['id']}'"
    ).strip()
    analysis = insert(
        "problem_analyses",
        question_id=question["id"],
        final_answer="x=5",
        subject="数学",
    )
    insert("reference_steps", analysis_id=analysis, step_index=0, text="4x=20，x=5")
    plan = insert(
        "review_plans",
        user_id=owner,
        question_id=question["id"],
        due_at="2026-01-01 00:00:00",
        interval_days=1,
        status="pending",
        reason="again",
    )
    insert(
        "review_plans",
        user_id=owner,
        question_id=question["id"],
        due_at="2026-01-02 00:00:00",
        interval_days=1,
        status="pending",
    )
    today = request(endpoint, "GET", "/api/v1/reviews/today", token=token)
    visible = [r for r in today if r["question_id"] == question["id"]]
    assert len(visible) == 1 and visible[0]["id"] == plan
    assert (
        len(visible[0]["source_version"]) == 64
        and visible[0]["pending_attempt"] is None
    )
    assert (
        "student_answer" not in visible[0]["question"]
        and "again" not in visible[0]["reason"]
    )
    assert not any(
        r["id"] == plan
        for r in request(endpoint, "GET", "/api/v1/reviews/today", token=other)
    )
    path = "/api/v1/reviews/" + plan
    request(
        endpoint, "POST", path + "/attempt", {"answer": "5"}, token=other, expected=404
    )
    request(
        endpoint, "POST", path + "/grade", {"grade": "good"}, token=token, expected=422
    )
    handwritten = handwriting(
        endpoint,
        env,
        token,
        other,
        {"id": plan, "activity": {"id": ""}},
        state,
        kind="review",
    )
    payload = {
        "answer": "x=5",
        **handwritten,
        "source_version": visible[0]["source_version"],
        "request_id": str(uuid4()),
    }
    attempt = request(
        endpoint,
        "POST",
        path + "/attempt",
        payload,
        token=token,
    )
    assert attempt["correct"] is True and attempt["can_update_learning"]
    assert attempt["expected_answer"] == "x=5"
    replay = request(endpoint, "POST", path + "/attempt", payload, token=token)
    assert replay["attempt_id"] == attempt["attempt_id"]
    assert (
        query(
            env, f"SELECT COUNT(*) FROM review_records WHERE plan_id='{plan}'"
        ).strip()
        == "1"
    )
    recovered = next(
        r
        for r in request(endpoint, "GET", "/api/v1/reviews/today", token=token)
        if r["id"] == plan
    )
    assert recovered["pending_attempt"]["attempt_id"] == attempt["attempt_id"]
    assert recovered["pending_attempt"]["student_answer"] == "x=5"
    assert "signature=" in recovered["pending_attempt"]["handwriting_image_url"]
    assert "memory_question_version" not in recovered["pending_attempt"]["grading"]
    request(
        endpoint,
        "POST",
        path + "/attempt",
        {**payload, "answer": "x=7"},
        token=token,
        expected=409,
    )
    history = request(endpoint, "GET", "/api/v1/reviews/history", token=token)
    assert not any(r["id"] == attempt["attempt_id"] for r in history)
    request(
        endpoint,
        "POST",
        path + "/grade",
        {"attempt_id": attempt["attempt_id"], "grade": "invalid"},
        token=token,
        expected=422,
    )
    graded = request(
        endpoint,
        "POST",
        path + "/grade",
        {"attempt_id": attempt["attempt_id"], "grade": "good"},
        token=token,
    )
    assert (
        graded["record"]["grade"] == "good"
        and graded["next_plan"]["interval_days"] == 7
    )
    assert "signature=" in graded["record"]["grading_details"]["handwriting_image_url"]
    request(
        endpoint,
        "POST",
        path + "/grade",
        {"attempt_id": attempt["attempt_id"]},
        token=token,
        expected=409,
    )
    request(
        endpoint, "POST", path + "/attempt", {"answer": "5"}, token=token, expected=404
    )
    assert any(
        r["id"] == attempt["attempt_id"] and r["plan"]["status"] == "completed"
        for r in request(endpoint, "GET", "/api/v1/reviews/history", token=token)
    )
    next_path = "/api/v1/reviews/" + graded["next_plan"]["id"]
    wrong = request(
        endpoint, "POST", next_path + "/attempt", {"answer": "x=100"}, token=token
    )
    assert wrong["correct"] is False and wrong["can_update_learning"]
    again = request(
        endpoint,
        "POST",
        next_path + "/grade",
        {"attempt_id": wrong["attempt_id"], "grade": "good"},
        token=token,
    )
    assert again["next_plan"]["interval_days"] == 2
    history = request(endpoint, "GET", "/api/v1/reviews/history", token=token)
    text_record = next(r for r in history if r["id"] == wrong["attempt_id"])
    assert text_record["grading_details"]["handwriting_image_url"] == ""
    assert not any(
        r["id"] == wrong["attempt_id"]
        for r in request(endpoint, "GET", "/api/v1/reviews/history", token=other)
    )
    pending_id = again["next_plan"]["id"]
    uncertain = insert(
        "review_records",
        plan_id=pending_id,
        grade="pending",
        grading_details={"can_update_learning": False},
    )
    request(
        endpoint,
        "POST",
        "/api/v1/reviews/" + pending_id + "/grade",
        {"attempt_id": uncertain, "grade": "easy"},
        token=token,
        expected=409,
    )
    saved = json.loads(
        query(
            env,
            f"SELECT grading_details FROM review_records WHERE id='{attempt['attempt_id']}'",
        )
    )
    assert saved["can_update_learning"] and saved["correct"]
    # Independent source for stale receipts, replacement answers and browser checks.
    q = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "question_text": "解方程：3x+2=17",
            "student_answer": "x=6",
            "subject": "数学",
            "grade": "初一",
        },
        token=token,
    )
    a = insert(
        "problem_analyses", question_id=q["id"], final_answer="x=5", subject="数学"
    )
    p = insert(
        "review_plans",
        user_id=owner,
        question_id=q["id"],
        due_at="2026-01-01 00:00:00",
        interval_days=1,
        status="pending",
    )
    url = "/api/v1/reviews/" + p
    original = next(
        r
        for r in request(endpoint, "GET", "/api/v1/reviews/today", token=token)
        if r["id"] == p
    )
    old = request(
        endpoint,
        "POST",
        url + "/attempt",
        {
            "answer": "x=4",
            "request_id": str(uuid4()),
            "source_version": original["source_version"],
        },
        token=token,
    )
    new_payload = {
        "answer": "x=5",
        "request_id": str(uuid4()),
        "source_version": original["source_version"],
    }
    new = request(endpoint, "POST", url + "/attempt", new_payload, token=token)
    current = next(
        r
        for r in request(endpoint, "GET", "/api/v1/reviews/today", token=token)
        if r["id"] == p
    )
    assert current["pending_attempt"]["attempt_id"] == new["attempt_id"]
    request(
        endpoint,
        "POST",
        url + "/grade",
        {"attempt_id": old["attempt_id"], "grade": "good"},
        token=token,
        expected=409,
    )
    query(env, f"UPDATE problem_analyses SET final_answer='x=7' WHERE id='{a}'")
    changed = next(
        r
        for r in request(endpoint, "GET", "/api/v1/reviews/today", token=token)
        if r["id"] == p
    )
    assert (
        changed["source_version"] != original["source_version"]
        and changed["pending_attempt"] is None
    )
    request(endpoint, "POST", url + "/attempt", new_payload, token=token, expected=409)
    request(
        endpoint,
        "POST",
        url + "/grade",
        {"attempt_id": new["attempt_id"], "grade": "good"},
        token=token,
        expected=409,
    )
    query(env, f"UPDATE problem_analyses SET final_answer='x=5' WHERE id='{a}'")
    query(env, f"DELETE FROM review_records WHERE plan_id='{p}'")
    if env.get("CANGJIE_VERIFY_BROWSER") == "1":
        env["QA_REVIEW_PLAN_ID"] = p
        env["QA_REVIEW_TOKEN"] = token
        env["QA_REVIEW_QUESTION_ID"] = q["id"]
    if env.get("CANGJIE_VERIFY_BROWSER") == "1":
        queue_actor = request(
            endpoint,
            "POST",
            "/api/v1/auth/register",
            {
                "email": f"review-queue-{uuid4().hex}@example.test",
                "password": "queue-test-password-123",
                "name": "切题验收",
            },
        )
        queue_ids = []
        for index, text in enumerate(["求解：x+2=5", "计算：7+5"]):
            question = request(
                endpoint,
                "POST",
                "/api/v1/questions/manual",
                {
                    "question_text": text,
                    "subject": "数学",
                    "grade": "初一",
                    "student_answer": "待订正",
                },
                token=queue_actor["access_token"],
            )
            if index == 1:
                insert(
                    "problem_analyses",
                    question_id=question["id"],
                    final_answer="12",
                    subject="数学",
                )
            queue_ids.append(
                insert(
                    "review_plans",
                    user_id=queue_actor["id"],
                    question_id=question["id"],
                    due_at=f"2026-01-0{index + 1} 00:00:00",
                    interval_days=1,
                    status="pending",
                    reason="到期后独立回忆",
                )
            )
        env["QA_REVIEW_QUEUE_TOKEN"] = queue_actor["access_token"]
        env["QA_REVIEW_QUEUE_FIRST"] = queue_ids[0]
        env["QA_REVIEW_QUEUE_SECOND"] = queue_ids[1]
    print(
        "Cangjie reviews passed: today's list, hidden answer, restored/replayed receipts, source versions, superseded attempts, grading, intervals, history and owner isolation"
    )
