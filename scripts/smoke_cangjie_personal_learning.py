"""Personal learning checks against disposable native HTTP/MySQL, without model calls."""

import json
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def personal_learning(endpoint, env, query):
    assert env["CANGJIE_DB_NAME"].startswith("zhiwei_cangjie_test_")
    insert = fixture_insert(env, query)
    actor = request(endpoint, "POST", "/api/v1/auth/register", {
        "email": f"personal-{uuid4().hex}@example.test", "password": "Personal-123456",
        "name": "长期学习验收", "grade": "初一",
    })
    other = request(endpoint, "POST", "/api/v1/auth/register", {
        "email": f"personal-other-{uuid4().hex}@example.test", "password": "Personal-123456",
        "name": "另一位学生",
    })
    token, foreign = actor["access_token"], other["access_token"]
    code = "personal." + uuid4().hex
    card_id = insert("knowledge_points", code=code, subject="数学", name="长期学习等式性质", content={
        "grade": "初一", "chapter": "长期学习验收章节", "definition": "等式两边同时加上或减去同一个数，等式仍成立。",
        "formulas": ["a=b \\Rightarrow a+c=b+c"],
    })
    first = None
    for index in range(22):
        question_id = insert("questions", user_id=actor["id"], subject="数学", grade="初一", title="长期检索",
            question_text=f"长期检索{index}：2x+1=2", confirmed=True, status="ready", knowledge_points=["长期学习等式性质"])
        plan_id = insert("review_plans", user_id=actor["id"], question_id=question_id, interval_days=1,
            due_at="2099-01-01 00:00:00" if index == 21 else "2020-01-01 00:00:00", reason="移项符号待巩固", status="pending")
        if first is None:
            first = (question_id, plan_id)
            insert("user_question_knowledge_links", user_id=actor["id"], question_id=question_id,
                knowledge_point_id=card_id, role="primary", confidence=1, mapping_method="fixture", evidence_text="受控验收")
    insert("mastery_states", user_id=actor["id"], subject="数学", knowledge_point="长期学习等式性质", mastery_score=0.4, confidence=0.8, evidence_count=2)
    for path in ["/reviews/search", "/knowledge/framework", "/reviews/filters", f"/knowledge/cards/{code}/lessons"]:
        request(endpoint, "GET", "/api/v1" + path, expected=401)
    find = lambda value="": request(endpoint, "GET", "/api/v1/reviews/search" + value, token=token)
    assert find("?q=" + quote("长期检索"))["total"] == 22
    assert len(find()["items"]) == 20
    assert len(find("?page=2")["items"]) == 2
    assert find("?scope=today")["total"] == 21
    assert find("?scope=completed")["total"] == 0
    assert find("?subject=" + quote("英语"))["total"] == 0
    assert find("?q=" + quote("' OR 1=1 --"))["total"] == 0
    assert find("?q=" + quote("移项符号"))["total"] == 22
    assert find("?q=" + quote("长期学习等式性质"))["total"] == 22
    assert all("student_answer" not in row and "expected_answer" not in row for row in find()["items"])
    assert request(endpoint, "GET", "/api/v1/reviews/search", token=foreign)["total"] == 0
    for suffix in ["?scope=unknown", "?page=0", "?page=no"]:
        request(endpoint, "GET", "/api/v1/reviews/search" + suffix, token=token, expected=422)
    framework = request(endpoint, "GET", "/api/v1/knowledge/framework", token=token)
    node = next(row for row in framework["nodes"] if row["code"] == code)
    assert node["question_count"] == 1 and node["mastery"]["evidence_count"] == 2
    other_node = next(row for row in request(endpoint, "GET", "/api/v1/knowledge/framework", token=foreign)["nodes"] if row["code"] == code)
    assert other_node["question_count"] == 0 and other_node["mastery"] is None
    payload = {"name": "方程专项", "q": "长期检索", "subject": "数学", "scope": "pending"}
    ranges = request(endpoint, "POST", "/api/v1/reviews/filters", payload, token)
    assert ranges[0]["q"] == payload["q"]
    filter_id = ranges[0]["id"]
    repeated = request(endpoint, "POST", "/api/v1/reviews/filters", payload, token)
    assert len(repeated) == 1 and repeated[0]["id"] == filter_id
    assert request(endpoint, "GET", "/api/v1/reviews/filters", token=foreign) == []
    request(endpoint, "DELETE", "/api/v1/reviews/filters/" + filter_id, token=foreign, expected=404)
    request(endpoint, "DELETE", "/api/v1/reviews/filters/" + filter_id, token=token)
    assert request(endpoint, "GET", "/api/v1/reviews/filters", token=token) == []
    request(endpoint, "POST", "/api/v1/reviews/filters", {**payload, "scope": "all"}, token, expected=422)
    path = f"/api/v1/knowledge/cards/{code}/lessons"
    mastery_sql = "SELECT mastery_score,confidence,evidence_count,COALESCE(last_evidence_at,'') FROM mastery_states WHERE user_id='" + actor["id"] + "' ORDER BY id"
    cognitive_sql = "SELECT COUNT(*) FROM cognitive_updates WHERE user_id='" + actor["id"] + "'"
    learning_before = (query(env, mastery_sql), query(env, cognitive_sql))
    assert request(endpoint, "GET", path, token=token) == []
    request(endpoint, "POST", path, {"prompt": "解释等式的性质", "request_id": "offline-test"}, token, expected=503)
    assert request(endpoint, "GET", path, token=token) == []
    assert len(query(env, "SELECT id FROM mastery_states WHERE user_id='" + actor["id"] + "'").splitlines()) == 1
    control = Path(env["CANGJIE_TEST_BUDGET_STATE"])
    previous_control = control.read_text()
    rule = {"operation": "knowledge_lesson", "knowledge_code": code, "key": "knowledge-lesson", "fixture_knowledge_lesson": True, "expected_knowledge_history": 0}
    control.write_text(json.dumps({"rules": [rule]}))
    try:
        body = {"prompt": "为什么移项变号？", "request_id": "validated-model-fixture"}
        generated = request(endpoint, "POST", path, body, token)
        replayed = request(endpoint, "POST", path, body, token)
        assert generated["id"] == replayed["id"]
        assert generated["result"]["can_update_learning"] is False
        current_history = request(endpoint, "GET", path, token=token)
        assert len(current_history) == 1 and current_history[0]["source_current"] is True
        # A re-import touching only metadata must preserve the student's history and replay.
        query(env, "UPDATE knowledge_points SET updated_at=TIMESTAMPADD(DAY,1,updated_at) WHERE id='" + card_id + "'")
        assert request(endpoint, "GET", path, token=token)[0]["source_current"] is True, "metadata-only update invalidated an unchanged lesson"
        assert request(endpoint, "POST", path, body, token)["id"] == generated["id"]
        rule["expected_knowledge_history"] = 1
        control.write_text(json.dumps({"rules": [rule]}))
        followup = request(endpoint, "POST", path, {"prompt": "把刚才的移项讲简单些", "request_id": "validated-followup"}, token)
        assert followup["id"] != generated["id"]
        assert all(row["source_current"] for row in request(endpoint, "GET", path, token=token))
        assert request(endpoint, "POST", path, body, token)["id"] == generated["id"]
        events = [json.loads(line) for line in Path(env["CANGJIE_TEST_BUDGET_EVENTS"]).read_text().splitlines()]
        assert sum(event.get("kind") == "accepted" and event.get("key") == "knowledge-lesson" for event in events) == 2
        request(endpoint, "POST", path, {**body, "prompt": "不同问题"}, token, expected=409)
        query(env, "UPDATE knowledge_points SET content=JSON_SET(content,'$.definition','等式两边同时加同一个数仍相等；此条已更新。') WHERE id='" + card_id + "'")
        assert request(endpoint, "GET", path, token=token)[0]["source_current"] is False
        request(endpoint, "POST", path, body, token, expected=409)
        rule["expected_knowledge_history"] = 0
        control.write_text(json.dumps({"rules": [rule]}))
        refreshed = request(endpoint, "POST", path, {**body, "request_id": "fresh-source-request"}, token)
        history_after_change = request(endpoint, "GET", path, token=token)
        assert next(row for row in history_after_change if row["id"] == refreshed["id"])["source_current"] is True
        assert all(not row["source_current"] for row in history_after_change if row["id"] in {generated["id"], followup["id"]})
        assert len(query(env, "SELECT id FROM mastery_states WHERE user_id='" + actor["id"] + "'").splitlines()) == 1
        assert (query(env, mastery_sql), query(env, cognitive_sql)) == learning_before
    finally:
        control.write_text(previous_control)
    # Recorded response validates native history, isolation and stale-source marking.
    lesson = json.dumps({"explanation": "受控历史讲解", "key_points": ["两边同时运算"], "check_question": "为什么要同时运算？", "sources": [{"name": "等式的性质"}]}, ensure_ascii=False)
    query(env, "INSERT INTO knowledge_lessons (id,user_id,knowledge_code,request_id,input_fingerprint,prompt,result,created_at) VALUES ('" + str(uuid4()) + "','" + actor["id"] + "','" + code + "','fixture-history','old','历史提问',CONVERT(0x" + lesson.encode().hex() + " USING utf8mb4),UTC_TIMESTAMP(6))")
    history = request(endpoint, "GET", path, token=token)
    assert history[0]["source_current"] is False
    assert request(endpoint, "GET", path, token=foreign) == []
    print("Personal learning passed: search/pagination/filters/framework/isolation; controlled model output through Pydantic, native persistence/replay/source invalidation; no live model called")
    return {"QA_PERSONAL_TOKEN": token, "QA_PERSONAL_QUESTION": first[0], "QA_PERSONAL_PLAN": first[1], "QA_PERSONAL_CODE": code}
