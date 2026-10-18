"""Task diagrams: actual native ownership/CAS, values, audit and learning gates."""

from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def task_visuals(endpoint, env, query, token, other, state, create_question, create):
    from smoke_cangjie_learning_tasks import action, task_request, wait_task

    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    before = query(
        env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'"
    )
    task = wait_task(endpoint, create(create_question(41))["id"], token)

    def body(
        current,
        kind="observe_visualization",
        values=None,
        text="两边同减，关系不变",
        key=None,
    ):
        value = {
            "kind": kind,
            "text": text,
            "version": current["version"],
            "step_id": current["step_id"],
            "input_fingerprint": current["input_fingerprint"],
            "request_id": key or str(uuid4()),
        }
        if values is not None:
            value["visual_values"] = values
        return value

    def post(current, value, expected=202, account=token):
        return task_request(
            endpoint,
            f"/api/v1/learning-tasks/{current['id']}/actions",
            account,
            value,
            status=expected,
        )

    post(task, body(task, values={"delta": 0}), expected=409)
    post(task, body(task, kind="visualize"), expected=404, account=other)
    opened, _ = action(endpoint, task, token, kind="visualize")
    graph = opened["student_view"]["visualization"]
    assert graph["spec"]["parameters"]["right"] == 41
    assert graph["source_phase"] == "repair" and graph["values"] == {"delta": 0}
    assert not opened["learning_applied"]
    for invalid in (
        {"delta": 1.5},
        {"delta": 999},
        {"delta": True},
        {"code": "alert(1)"},
        {},
    ):
        post(opened, body(opened, values=invalid), expected=422)
    post(opened, body(opened, values={"delta": 0}, text=" " * 3), expected=422)
    post(opened, body(opened, values={"delta": 0}, text="字" * 1201), expected=422)
    saved_body = body(opened, values={"delta": 3}, text="我已经会了")
    saved = wait_task(endpoint, post(opened, saved_body)["id"], token)
    assert saved["student_view"]["visualization"]["observation"] == "我已经会了"
    assert saved["student_view"]["title"] == "先订正这一步"
    assert (
        query(env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'")
        == before
    )
    assert post(saved, saved_body)["version"] == saved["version"]
    post(saved, saved_body | {"visual_values": {"delta": 2}}, expected=409)
    closed, _ = action(endpoint, saved, token, kind="close_visualization")
    assert not closed["student_view"].get("visualization")
    reopened, _ = action(endpoint, closed, token, kind="visualize")
    assert reopened["student_view"]["visualization"]["values"] == {"delta": 3}
    reopened, _ = action(endpoint, reopened, token, kind="close_visualization")
    repaired, _ = action(endpoint, reopened, token, text="2x=38")
    contrast, _ = action(endpoint, repaired, token, text="x=19")
    contrast, _ = action(endpoint, contrast, token, kind="visualize")
    assert "- 3" in contrast["student_view"]["visualization"]["source_equation_tex"]
    contrast, _ = action(endpoint, contrast, token, kind="close_visualization")
    completed, _ = action(endpoint, contrast, token, text="x=22")
    assert completed["status"] == "completed" and not completed["learning_applied"]
    history = request(
        endpoint, "GET", f"/api/v1/learning-tasks/{task['id']}/history", token=token
    )
    assert any(item["visualization"] and item["assisted"] for item in history["items"])
    assert "expected_observation" not in str(history)

    insert = fixture_insert(env, query)
    function = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"subject": "数学", "grade": "初二", "question_text": "函数：y=2x+1"},
        token=token,
    )
    insert(
        "problem_analyses",
        question_id=function["id"],
        subject="数学",
        final_answer="给定的一次函数",
    )
    function_task = wait_task(endpoint, create(function)["id"], token)
    function_task, _ = action(endpoint, function_task, token, kind="visualize")
    assert (
        function_task["student_view"]["visualization"]["spec"]["type"]
        == "linear_function"
    )
    parameters = body(function_task, values={"k": 1, "b": 2})
    function_task = wait_task(endpoint, post(function_task, parameters)["id"], token)
    assert (
        post(function_task, parameters | {"visual_values": {"b": 2, "k": 1}})["version"]
        == function_task["version"]
    )
    probe = str(uuid4())
    query(
        env,
        f"ALTER TABLE learning_task_steps ADD CONSTRAINT visual_rollback CHECK (task_id<>'{function_task['id']}' OR request_id<>'{probe}')",
    )
    try:
        failed = wait_task(
            endpoint,
            post(
                function_task, body(function_task, values={"k": 2, "b": 3}, key=probe)
            )["id"],
            token,
        )
        assert failed["status"] == "failed"
        assert query(
            env,
            f"SELECT JSON_EXTRACT(checkpoint,'$.visualization.values.k') FROM learning_tasks WHERE id='{failed['id']}'",
        ) in {"1", "1.0"}
    finally:
        query(env, "ALTER TABLE learning_task_steps DROP CHECK visual_rollback")
    function_task, _ = action(endpoint, failed, token, kind="resume")
    request(
        endpoint,
        "PATCH",
        f"/api/v1/questions/{function['id']}",
        {"question_text": "函数：y=3x+1"},
        token=token,
    )
    stale = post(function_task, body(function_task, values={"k": 1, "b": 2}))
    assert stale["status"] == "stale" and not stale["student_view"].get("visualization")
    assert (
        query(env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'")
        == before
    )
    state["task_visual_plan"] = True
    try:
        planned = wait_task(endpoint, create(create_question(47))["id"], token)
        planned, _ = action(endpoint, planned, token, text="2x=50")
        assert planned["student_view"]["visualization"]
        assert (
            query(
                env,
                f"SELECT JSON_UNQUOTE(JSON_EXTRACT(trace,'$.planner_source')) FROM learning_task_steps WHERE task_id='{planned['id']}' AND tool_name='visualization'",
            )
            == "model"
        )
        unsupported = request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {
                "subject": "语文",
                "grade": "初一",
                "question_text": "这段文字表达怎样的情感",
            },
            token=token,
        )
        insert(
            "problem_analyses",
            question_id=unsupported["id"],
            subject="语文",
            final_answer="友情",
        )
        unsupported = wait_task(endpoint, create(unsupported)["id"], token)
        unsupported, _ = action(endpoint, unsupported, token, kind="hint")
        assert not unsupported["student_view"].get("visualization")
        assert (
            query(
                env,
                f"SELECT validation FROM learning_task_steps WHERE task_id='{unsupported['id']}' AND tool_name='visualization'",
            )
            == "rejected"
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM learning_task_steps WHERE task_id='{unsupported['id']}' AND tool_name='step_alignment'",
            )
            == "1"
        )
    finally:
        state.pop("task_visual_plan", None)
    recovery = wait_task(endpoint, create(create_question(43))["id"], token)
    recovery, _ = action(endpoint, recovery, token, kind="visualize")
    recovery = wait_task(
        endpoint,
        post(
            recovery, body(recovery, values={"delta": 2}, text="重启后继续看同一图示")
        )["id"],
        token,
    )
    state["visual_recovery_id"] = recovery["id"]
    print(
        "Cangjie task visuals passed: source binding, numeric controls, self-report/no mastery, assistance, replay/key order, CAS/ownership, atomic rollback and stale rejection"
    )
    return recovery["id"]
