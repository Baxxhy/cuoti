"""Immutable task source, original step IDs, legacy recovery and private views."""

import json
from uuid import uuid4

from smoke_cangjie_accounts import request


def task_sources(endpoint, env, query, token, other, state, create_question, create):
    from smoke_cangjie_learning_tasks import action, task_request, wait_task

    question = create_question(51)
    key = str(uuid4())
    task = wait_task(endpoint, create(question, key)["id"], token)
    task_id = task["id"]
    assert task["status"] == "waiting_student", query(
        env, f"SELECT status,exit_reason FROM learning_tasks WHERE id='{task_id}'"
    )

    def snapshot(id):
        return json.loads(
            query(env, f"SELECT source FROM learning_task_sources WHERE task_id='{id}'")
        )

    original = snapshot(task_id)
    assert original["question"]["question_text"] == "解方程：2x+3=51"
    assert original["work"]["id"] and len(original["steps"]) == 2
    assert (
        query(
            env, f"SELECT origin FROM learning_task_sources WHERE task_id='{task_id}'"
        )
        == "created"
    )
    assert create(question, key)["id"] == task_id
    assert (
        query(
            env, f"SELECT COUNT(*) FROM learning_task_sources WHERE task_id='{task_id}'"
        )
        == "1"
    )
    assert "source_snapshot" not in task and "expected" not in str(task)
    task, _ = action(endpoint, task, token, text="2x=48")
    history_path = f"/api/v1/learning-tasks/{task_id}/history"
    history = request(endpoint, "GET", history_path, token=token)
    evidence = history["items"][0]["source"]
    assert evidence == {
        "snapshot_id": task_id,
        "student_work_id": original["work"]["id"],
        "student_step_id": original["steps"][0]["id"],
        "step_index": 0,
        "student_step_text": "2x=51+3",
    }
    tool_source = json.loads(
        query(
            env,
            f"SELECT JSON_EXTRACT(trace,'$.evidence.source') FROM learning_task_steps WHERE task_id='{task_id}' AND validation='verified' AND JSON_EXTRACT(trace,'$.evidence.source') IS NOT NULL LIMIT 1",
        )
    )
    assert tool_source == evidence
    public = history["source_question"]
    assert set(public) == {
        "snapshot_id",
        "origin",
        "captured_at",
        "subject",
        "grade",
        "question_text",
        "options",
    }
    assert "final_answer" not in json.dumps(
        history
    ) and "reference_steps" not in json.dumps(history)
    request(endpoint, "GET", history_path, token=other, expected=404)
    task, _ = action(endpoint, task, token, kind="hint")
    assert snapshot(task_id) == original
    request(
        endpoint,
        "PATCH",
        f"/api/v1/questions/{question['id']}",
        {"question_text": "修改后的新题目"},
        token=token,
    )
    stale = request(endpoint, "GET", f"/api/v1/learning-tasks/{task_id}", token=token)
    assert stale["status"] == "stale"
    assert snapshot(task_id) == original
    history = request(endpoint, "GET", history_path, token=token)
    assert (
        history["source_question"]["question_text"]
        == original["question"]["question_text"]
    )
    assert (
        next(item for item in history["items"] if item["kind"] == "answer")["source"]
        == evidence
    )

    # Simulate a pre-009 active record. Only a matching live source can be captured.
    legacy = wait_task(endpoint, create(create_question(53))["id"], token)
    query(env, f"DELETE FROM learning_task_sources WHERE task_id='{legacy['id']}'")
    legacy, _ = action(endpoint, legacy, token, kind="hint")
    assert (
        query(
            env,
            f"SELECT origin FROM learning_task_sources WHERE task_id='{legacy['id']}'",
        )
        == "legacy_revalidated"
    )
    old = create_question(55)
    legacy_stale = wait_task(endpoint, create(old)["id"], token)
    query(
        env, f"DELETE FROM learning_task_sources WHERE task_id='{legacy_stale['id']}'"
    )
    request(
        endpoint,
        "PATCH",
        f"/api/v1/questions/{old['id']}",
        {"question_text": "新版本不能冒充历史"},
        token=token,
    )
    stale = request(
        endpoint, "GET", f"/api/v1/learning-tasks/{legacy_stale['id']}", token=token
    )
    assert stale["status"] == "stale"
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM learning_task_sources WHERE task_id='{legacy_stale['id']}'",
        )
        == "0"
    )
    assert (
        request(
            endpoint,
            "GET",
            f"/api/v1/learning-tasks/{legacy_stale['id']}/history",
            token=token,
        )["source_question"]
        is None
    )

    # Reject the new snapshot insert and prove that its task/request roll back too.
    rollback = create_question(57)
    query(
        env,
        f"ALTER TABLE learning_task_sources ADD CONSTRAINT source_rollback CHECK (JSON_UNQUOTE(JSON_EXTRACT(source,'$.question.id'))<>'{rollback['id']}')",
    )
    failed_key = str(uuid4())
    try:
        task_request(
            endpoint,
            "/api/v1/learning-tasks",
            token,
            {"question_id": rollback["id"], "request_id": failed_key},
            status=503,
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM learning_tasks WHERE question_id='{rollback['id']}'",
            )
            == "0"
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM learning_task_requests WHERE request_id='{failed_key}'",
            )
            == "0"
        )
    finally:
        query(env, "ALTER TABLE learning_task_sources DROP CHECK source_rollback")
    recovered = wait_task(endpoint, create(rollback, failed_key)["id"], token)
    assert snapshot(recovered["id"])["question"]["id"] == rollback["id"]
    corrupt = wait_task(endpoint, create(create_question(59))["id"], token)
    query(
        env,
        f"UPDATE learning_task_sources SET source=JSON_SET(source,'$.steps[0].text','changed outside application') WHERE task_id='{corrupt['id']}'",
    )
    failed, body = action(endpoint, corrupt, token, kind="hint")
    assert (
        failed["status"] == "failed" and not failed["student_view"]["secondary_actions"]
    )
    assert (
        query(env, f"SELECT exit_reason FROM learning_tasks WHERE id='{failed['id']}'")
        == "source_field_10"
    )
    assert (
        query(
            env,
            f"SELECT status FROM learning_task_actions WHERE task_id='{failed['id']}' AND request_id='{body['request_id']}'",
        )
        == "failed"
    )
    print(
        "Cangjie task sources passed: immutable records, original step IDs, private history, stale source retention, honest legacy capture and atomic creation rollback"
    )
