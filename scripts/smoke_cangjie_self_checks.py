"""Student-confirmed notes/history/journey: real native HTTP and isolated MySQL."""

import json

from smoke_cangjie_accounts import request


def self_checks(endpoint, env, query, token, other, task, question, unfinished):
    path = f"/api/v1/learning-tasks/{task['id']}/self-check"
    history_path = f"/api/v1/learning-tasks/{task['id']}/history"
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    count = query(
        env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'"
    )
    request(endpoint, "GET", path, expected=401)
    request(endpoint, "GET", path, token=other, expected=404)
    request(endpoint, "GET", history_path, token=other, expected=404)
    request(endpoint, "POST", history_path, {}, token=token, expected=405)
    value = request(endpoint, "GET", path, token=token)
    assert value == {
        "version": 0,
        "source_current": True,
        "can_save": True,
        "note": None,
    }
    body = {
        "text": "移项后先检查符号，再代回原式验证。",
        "version": 0,
        "confirmed": True,
        "input_fingerprint": task["input_fingerprint"],
    }
    request(
        endpoint, "PATCH", path, body | {"confirmed": False}, token=token, expected=422
    )
    request(
        endpoint, "PATCH", path, body | {"confirmed": "true"}, token=token, expected=422
    )
    request(
        endpoint, "PATCH", path, body | {"text": "字" * 301}, token=token, expected=422
    )
    request(
        endpoint, "PATCH", path, body | {"text": "  \n "}, token=token, expected=422
    )
    request(
        endpoint, "PATCH", path, body | {"mastered": True}, token=token, expected=422
    )
    request(endpoint, "PATCH", path, body | {"version": 4}, token=token, expected=409)
    request(
        endpoint,
        "PATCH",
        path,
        body | {"input_fingerprint": "old"},
        token=token,
        expected=409,
    )
    request(endpoint, "PATCH", path, body, token=other, expected=404)
    request(
        endpoint,
        "PATCH",
        f"/api/v1/learning-tasks/{unfinished['id']}/self-check",
        body,
        token=token,
        expected=409,
    )
    first = request(endpoint, "PATCH", path, body, token=token)
    assert first["version"] == 1 and first["note"]["kind"] == "student_self_report"
    assert request(endpoint, "PATCH", path, body, token=token) == first
    assert request(endpoint, "GET", path, token=token) == first
    # Audit failure rolls back the note revision as well as the audit itself.
    query(
        env,
        f"ALTER TABLE agent_tool_calls ADD CONSTRAINT self_check_rollback CHECK (tool_name<>'save_self_check' OR JSON_UNQUOTE(JSON_EXTRACT(input_json,'$.task_id'))<>'{task['id']}' OR CAST(JSON_UNQUOTE(JSON_EXTRACT(input_json,'$.version')) AS UNSIGNED)<2)",
    )
    try:
        request(
            endpoint,
            "PATCH",
            path,
            body | {"text": "修改不应部分保存", "version": 1},
            token=token,
            expected=503,
        )
        assert request(endpoint, "GET", path, token=token) == first
    finally:
        query(env, "ALTER TABLE agent_tool_calls DROP CHECK self_check_rollback")
    edited_body = body | {"text": "移项后检查符号，除系数后再代回。", "version": 1}
    edited = request(endpoint, "PATCH", path, edited_body, token=token)
    assert edited["version"] == 2 and edited["note"]["text"] == edited_body["text"]
    request(
        endpoint,
        "PATCH",
        path,
        body | {"text": "旧窗口覆盖"},
        token=token,
        expected=409,
    )
    request(endpoint, "DELETE", path, {"version": 1}, token=token, expected=409)
    deleted = request(endpoint, "DELETE", path, {"version": 2}, token=token)
    assert deleted["note"] is None and deleted["version"] == 3
    assert request(endpoint, "DELETE", path, {"version": 2}, token=token) == deleted
    restored = request(endpoint, "PATCH", path, body | {"version": 3}, token=token)
    assert restored["version"] == 4
    assert (
        query(env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'")
        == count
    )
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM agent_tool_calls WHERE tool_name='save_self_check' AND JSON_UNQUOTE(JSON_EXTRACT(input_json,'$.task_id'))='{task['id']}'",
        )
        == "4"
    )
    history = request(endpoint, "GET", history_path, token=token)
    assert len(history["items"]) >= 3
    allowed = {
        "id",
        "kind",
        "status",
        "created_at",
        "text",
        "feedback",
        "phase",
        "verdict",
        "assisted",
        "handwriting_image_url",
        "visualization",
        "source",
    }
    assert all(set(item) == allowed for item in history["items"])
    assert any(
        item["phase"] == "repair" and item["text"] == "11-3"
        for item in history["items"]
    )
    assert "lease_token" not in json.dumps(history) and "checkpoint" not in json.dumps(
        history
    )
    journey_path = f"/api/v1/questions/{question['id']}/journey"
    journey = request(endpoint, "GET", journey_path, token=token)
    assert (
        journey["learning_tasks"]["repair_verified"]
        and journey["learning_tasks"]["original_independent"]
        and journey["learning_tasks"]["near_transfer"]
    )
    # A single contrast is not the old full near+far transfer/teach-back stage.
    assert (
        not journey["stages"][2]["completed"] and not journey["stages"][3]["completed"]
    )
    assert journey["self_checks"][0]["text"] == body["text"]
    assert journey["self_checks"][0]["source_current"]
    assert any(event["id"] == "task:" + task["id"] for event in journey["events"])
    request(
        endpoint,
        "PATCH",
        f"/api/v1/questions/{question['id']}",
        {"question_text": "解方程：2x+3=21"},
        token=token,
    )
    stale = request(endpoint, "GET", path, token=token)
    assert (
        not stale["source_current"]
        and not stale["can_save"]
        and stale["note"]["text"] == body["text"]
    )
    request(endpoint, "PATCH", path, body | {"version": 4}, token=token, expected=409)
    outdated = request(endpoint, "GET", journey_path, token=token)
    assert (
        not outdated["learning_tasks"]["repair_verified"]
        and not outdated["learning_tasks"]["near_transfer"]
    )
    assert not outdated["self_checks"][0]["source_current"]
    assert (
        request(endpoint, "DELETE", path, {"version": 4}, token=token)["note"] is None
    )
    print(
        "Cangjie self-checks passed: confirmation, CRUD, retries, ownership, versions, audit rollback, no mastery writes, private history and stale journey projection"
    )
