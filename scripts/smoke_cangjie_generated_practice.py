"""Native generated practice: source protection, recovery, retries and learning isolation."""

import re
from uuid import uuid4

from smoke_cangjie_accounts import request


def generated_practice(endpoint, env, query):
    actor = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"generated-smoke-{uuid4().hex}@example.test",
            "password": "Practice-test-123",
            "name": "生成练习验收",
            "grade": "高三",
        },
    )
    token, owner = actor["access_token"], actor["id"]
    q = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "subject": "数学",
            "grade": "高三",
            "question_text": "解方程：13x+7=98",
            "student_answer": "x=9",
        },
        token=token,
    )
    base = {"mistake_id": q["id"], "mode": "reinforce"}
    first = request(endpoint, "POST", "/api/v1/practice/recommend", base, token=token)
    assert first.get("generated") and first["stem"] and "answer" not in first
    restored = request(
        endpoint, "POST", "/api/v1/practice/recommend", base, token=token
    )
    assert first["question_id"] == restored["question_id"]
    numbers = re.search(r"(\d+)x\+(\d+)=(-?\d+)", first["stem"])
    a, b, c = map(int, numbers.groups())
    answer = f"x={(c - b) // a}"
    payload = {**base, "question_id": first["question_id"], "student_answer": ""}
    undecided = request(
        endpoint, "POST", "/api/v1/practice/attempt", payload, token=token
    )
    assert not undecided["can_update_learning"]
    payload["student_answer"] = answer
    graded = request(endpoint, "POST", "/api/v1/practice/attempt", payload, token=token)
    assert graded["correct"] and graded["mastery"] is None and graded["learning_note"]
    replay = request(endpoint, "POST", "/api/v1/practice/attempt", payload, token=token)
    assert replay == graded
    assert (
        query(env, f"SELECT COUNT(*) FROM variant_attempts WHERE user_id='{owner}'")
        == "1"
    )
    assert (
        query(env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'")
        == "0"
    )
    restored = request(
        endpoint, "POST", "/api/v1/practice/recommend", base, token=token
    )
    assert (
        restored["previous_result"] == graded and restored["previous_answer"] == answer
    )
    fresh = request(
        endpoint,
        "POST",
        "/api/v1/practice/recommend",
        {**base, "force_new": True},
        token=token,
    )
    assert (
        fresh["question_id"] != first["question_id"] and fresh["stem"] != first["stem"]
    )
    n = re.search(r"(\d+)x\+(\d+)=(-?\d+)", fresh["stem"])
    a, b, c = map(int, n.groups())
    passed = request(
        endpoint,
        "POST",
        "/api/v1/practice/attempt",
        {
            **base,
            "question_id": fresh["question_id"],
            "student_answer": f"x={(c - b) // a}",
        },
        token=token,
    )
    assert passed["correct"] and passed["mastery"] is not None
    before = query(
        env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'"
    )
    query(
        env,
        f"UPDATE questions SET question_text='解方程：13x+7=111' WHERE id='{q['id']}'",
    )
    request(
        endpoint, "POST", "/api/v1/practice/attempt", payload, token=token, expected=409
    )
    assert (
        query(env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'")
        == before
    )
    print(
        "Generated practice passed: offline checked exercise, persistence, exposure guard, lost receipt recovery, no duplicate attempts, next question and stale source rejection"
    )
