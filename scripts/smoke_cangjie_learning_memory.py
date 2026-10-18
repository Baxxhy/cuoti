"""Actual native memory reads, source/TTL gates and in-flight invalidation."""

import json
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def learning_memory(
    endpoint, env, query, token, other, state, create_question, create, started, release
):
    from smoke_cangjie_learning_tasks import action, task_request, wait_task

    insert = fixture_insert(env, query)
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    foreign = request(endpoint, "GET", "/api/v1/auth/me", token=other)["id"]

    def now():
        return query(env, "SELECT UTC_TIMESTAMP()")

    state["task_memory_probe"] = True
    state["task_memory_kind"] = "self_check"
    try:
        source = create_question(61)
        completed = wait_task(endpoint, create(source)["id"], token)
        completed, _ = action(endpoint, completed, token, text="2x=58")
        completed, _ = action(endpoint, completed, token, text="x=29")
        completed, _ = action(endpoint, completed, token, text="x=32")
        assert completed["status"] == "completed" and completed["learning_applied"]
        update = json.loads(
            query(
                env,
                f"SELECT JSON_OBJECT('id',id,'evidence',evidence,'entity_key',entity_key,'new_value',new_value) FROM cognitive_updates WHERE question_id='{source['id']}' AND entity_type='mastery' ORDER BY created_at DESC LIMIT 1",
            )
        )
        assert (
            update["evidence"]["memory_source"]["rule_version"] == "learning-memory-v1"
        )
        event_ref = "cognitive:" + update["id"]
        note_path = f"/api/v1/learning-tasks/{completed['id']}/self-check"
        note = request(
            endpoint,
            "PATCH",
            note_path,
            {
                "text": "我会先检查符号，再代回验证。",
                "confirmed": True,
                "version": 0,
                "input_fingerprint": completed["input_fingerprint"],
            },
            token=token,
        )
        note_ref = "self_check:" + note["note"]["id"]
        expired = insert(
            "mastery_states",
            user_id=owner,
            subject="数学",
            knowledge_point="过期估计",
            mastery_score=0.99,
        )
        future = insert(
            "mastery_states",
            user_id=owner,
            subject="数学",
            knowledge_point="未来时间不可信",
            mastery_score=1,
        )
        query(
            env,
            f"UPDATE mastery_states SET updated_at=UTC_TIMESTAMP()+INTERVAL 1 DAY WHERE id='{future}'",
        )
        cross_subject = insert(
            "misconception_states",
            user_id=owner,
            subject="英语",
            code="memory-English",
            label="其他学科不混用",
            updated_at=now(),
        )
        foreign_id = insert(
            "misconception_states",
            user_id=foreign,
            subject="数学",
            code="memory-foreign",
            label="其他学生不混用",
            updated_at=now(),
        )
        legacy = insert(
            "cognitive_updates",
            user_id=owner,
            question_id=source["id"],
            entity_type="mastery",
            entity_key="旧来源不冒充验证",
            evidence={"near_transfer": True},
            updated_at=now(),
        )

        # Real reviewed wrong answer remains wrong even when difficulty is 'easy'.
        plan = insert(
            "review_plans",
            user_id=owner,
            question_id=source["id"],
            due_at=now(),
            status="pending",
            created_at=now(),
            updated_at=now(),
        )
        attempt = request(
            endpoint,
            "POST",
            f"/api/v1/reviews/{plan}/attempt",
            {"answer": "x=999"},
            token=token,
        )
        assert attempt["correct"] is False and attempt["can_update_learning"]
        request(
            endpoint,
            "POST",
            f"/api/v1/reviews/{plan}/grade",
            {"attempt_id": attempt["attempt_id"], "grade": "easy"},
            token=token,
        )
        review_ref = "review_record:" + attempt["attempt_id"]
        target = wait_task(endpoint, create(source)["id"], token)

        def probe(current):
            current, _ = action(endpoint, current, token, kind="hint")
            assert current["status"] == "waiting_student"
            entries = state["task_memory_context"]["memory_snapshot"]["entries"]
            return current, {entry["ref"]: entry for entry in entries}

        target, entries = probe(target)
        assert (
            note_ref in entries
            and entries[note_ref]["classification"] == "student_self_report"
        )
        assert (
            event_ref in entries
            and entries[event_ref]["classification"] == "verified_event"
        )
        assert entries[review_ref]["outcome"] == "incorrect"
        forbidden = {
            "mastery:" + expired,
            "mastery:" + future,
            "misconception:" + cross_subject,
            "misconception:" + foreign_id,
            "cognitive:" + legacy,
        }
        assert not forbidden.intersection(entries) and len(entries) <= 18
        manifest = json.loads(
            query(
                env,
                f"SELECT JSON_EXTRACT(result,'$.memory_manifest') FROM agent_runs WHERE agent_name='learning_task' AND JSON_UNQUOTE(JSON_EXTRACT(result,'$.task_id'))='{target['id']}' ORDER BY created_at DESC,id DESC LIMIT 1",
            )
        )
        assert any(
            item["ref"] == note_ref and item["version"] == entries[note_ref]["version"]
            for item in manifest
        )
        assert all("summary" not in item for item in manifest)
        selected = query(
            env,
            f"SELECT trace FROM learning_task_steps WHERE task_id='{target['id']}' AND tool_name='knowledge_search' ORDER BY created_at DESC LIMIT 1",
        )
        assert note_ref in json.loads(selected)["memory_refs"]
        assert "memory_snapshot" not in target and "memory_manifest" not in json.dumps(
            target
        )

        state["mode"] = "fail"
        target, _ = action(endpoint, target, token, kind="hint")
        state["mode"] = "good"
        trace = json.loads(
            query(
                env,
                f"SELECT trace FROM learning_task_steps WHERE task_id='{target['id']}' ORDER BY created_at DESC,id DESC LIMIT 1",
            )
        )
        assert trace["tool_name"] == "step_alignment" and trace["memory_refs"] == [
            review_ref
        ]
        # The clock policy removes old facts without rewriting grades or scores.
        query(
            env,
            f"UPDATE review_records SET updated_at=UTC_TIMESTAMP()-INTERVAL 91 DAY WHERE id='{attempt['attempt_id']}'",
        )
        query(
            env,
            f"UPDATE learning_self_checks SET updated_at=UTC_TIMESTAMP()-INTERVAL 91 DAY WHERE id='{note['note']['id']}'",
        )
        target, entries = probe(target)
        assert review_ref not in entries and note_ref not in entries
        note = request(
            endpoint,
            "PATCH",
            note_path,
            {
                "text": "先核对符号，算完再代回。",
                "confirmed": True,
                "version": note["version"],
                "input_fingerprint": completed["input_fingerprint"],
            },
            token=token,
        )
        target, entries = probe(target)
        assert note_ref in entries
        old_version = entries[note_ref]["version"]

        # A real self-check edit while Qwen is in flight invalidates the old plan.
        count = query(
            env,
            f"SELECT COUNT(*) FROM agent_runs WHERE agent_name='learning_task' AND JSON_UNQUOTE(JSON_EXTRACT(result,'$.task_id'))='{target['id']}'",
        )
        state["mode"] = "block"
        started.clear()
        release.clear()
        task_request(
            endpoint,
            f"/api/v1/learning-tasks/{target['id']}/actions",
            token,
            {
                "kind": "hint",
                "text": "",
                "version": target["version"],
                "step_id": target["step_id"],
                "input_fingerprint": target["input_fingerprint"],
                "request_id": str(uuid4()),
            },
            status=202,
        )
        assert started.wait(5)
        note = request(
            endpoint,
            "PATCH",
            note_path,
            {
                "text": "我会检查符号并核对每一步等价关系。",
                "confirmed": True,
                "version": note["version"],
                "input_fingerprint": completed["input_fingerprint"],
            },
            token=token,
        )
        state["mode"] = "good"
        release.set()
        target = wait_task(endpoint, target["id"], token)
        assert target["status"] == "failed"
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM agent_runs WHERE agent_name='learning_task' AND JSON_UNQUOTE(JSON_EXTRACT(result,'$.task_id'))='{target['id']}'",
            )
            == count
        )
        target, _ = action(endpoint, target, token, kind="resume")
        target, entries = probe(target)
        assert entries[note_ref]["version"] != old_version
        request(
            endpoint, "DELETE", note_path, {"version": note["version"]}, token=token
        )
        target, entries = probe(target)
        assert note_ref not in entries

        # Revoke a seeded review source; business revoke/regrade paths are covered
        # separately by review_mutations. Here the reader uses the actual SQL state.
        cls = insert(
            "teacher_classes", teacher_id=foreign, name="记忆撤销测试", grade="初一"
        )
        review_task = insert(
            "teacher_review_tasks",
            class_id=cls,
            student_id=owner,
            question_id=source["id"],
            source_id=str(uuid4()),
            status="confirmed_correct",
            learning_applied=True,
        )
        review = insert(
            "teacher_review_results",
            task_id=review_task,
            teacher_id=foreign,
            conclusion="confirmed_correct",
            reason="来源校验测试",
            allow_learning_update=True,
        )
        teacher_evidence = {
            **update["evidence"],
            "strategy": "teacher_review",
            "teacher_review_id": review,
        }
        teacher_update = insert(
            "cognitive_updates",
            user_id=owner,
            question_id=source["id"],
            entity_type="mastery",
            entity_key=update["entity_key"],
            evidence=teacher_evidence,
            updated_at=now(),
            created_at=now(),
        )
        target, entries = probe(target)
        teacher_ref = "cognitive:" + teacher_update
        assert (
            teacher_ref in entries and entries[teacher_ref]["independence"] == "unknown"
        )
        query(
            env,
            f"UPDATE teacher_review_results SET revoked_at=UTC_TIMESTAMP() WHERE id='{review}'",
        )
        target, entries = probe(target)
        assert teacher_ref not in entries
        state["task_memory_foreign"] = True
        target, _ = action(endpoint, target, token, kind="hint")
        state["task_memory_foreign"] = False
        traces = query(
            env,
            f"SELECT trace FROM learning_task_steps WHERE task_id='{target['id']}' ORDER BY created_at DESC LIMIT 2",
        )
        assert "invalid_plan_or_source" in traces and "self_check:foreign" not in traces

        # Edited source no longer supplies facts, notes or its aggregate estimates.
        pending_plan = insert(
            "review_plans",
            user_id=owner,
            question_id=source["id"],
            due_at=now(),
            status="pending",
            created_at=now(),
            updated_at=now(),
        )
        pending_attempt = request(
            endpoint,
            "POST",
            f"/api/v1/reviews/{pending_plan}/attempt",
            {"answer": "x=29"},
            token=token,
        )
        reference_id = query(
            env,
            f"SELECT r.id FROM reference_steps r JOIN problem_analyses a ON a.id=r.analysis_id WHERE a.question_id='{source['id']}' ORDER BY r.step_index LIMIT 1",
        )
        query(
            env,
            f"UPDATE reference_steps SET text=CONCAT(text,' ') WHERE id='{reference_id}'",
        )
        request(
            endpoint,
            "POST",
            f"/api/v1/reviews/{pending_plan}/grade",
            {"attempt_id": pending_attempt["attempt_id"], "grade": "good"},
            token=token,
            expected=409,
        )
        assert (
            query(env, f"SELECT status FROM review_plans WHERE id='{pending_plan}'")
            == "pending"
        )
        query(env, f"UPDATE reference_steps SET text='2x=58' WHERE id='{reference_id}'")
        request(
            endpoint,
            "PATCH",
            f"/api/v1/questions/{source['id']}",
            {"question_text": "原题已修改，旧判定不能继续使用"},
            token=token,
        )
        observer = wait_task(endpoint, create(create_question(65))["id"], token)
        observer, entries = probe(observer)
        assert event_ref not in entries and teacher_ref not in entries
        stamps = update["evidence"]["memory_source"]
        assert "mastery:" + stamps["mastery_id"] not in entries
        assert "misconception:" + stamps["misconception_id"] not in entries
        print(
            "Cangjie learning memory passed: typed facts/estimates/self-reports, user/subject/TTL gates, real source versions, wrong review vs easy rating, edit/delete/revoke invalidation, in-flight rollback, rule history choice and reference audit"
        )
    finally:
        state["mode"] = "good"
        release.set()
        for key in [
            "task_memory_probe",
            "task_memory_kind",
            "task_memory_foreign",
            "task_memory_context",
        ]:
            state.pop(key, None)


def practice_memory(endpoint, env, query, token, state, mistake_id, dataset_id, insert):
    """Read the event created by the real practice route before its later fixtures mutate."""
    from smoke_cangjie_learning_tasks import action, task_request, wait_task

    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    update_id = query(
        env,
        f"SELECT id FROM cognitive_updates WHERE user_id='{owner}' AND question_id='{mistake_id}' AND entity_type='mastery' ORDER BY created_at DESC,id DESC LIMIT 1",
    )
    assert update_id
    current = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"subject": "练习验证学科", "question_text": "记忆读取观察题", "grade": "初一"},
        token=token,
    )
    insert(
        "problem_analyses",
        question_id=current["id"],
        subject="练习验证学科",
        final_answer="只验证来源读取",
    )
    saved = {
        key: state.get(key)
        for key in ["learning_task", "task_memory_probe", "task_memory_kind"]
    }
    state.update(
        learning_task=True, task_memory_probe=True, task_memory_kind="cognitive"
    )
    try:
        task = wait_task(
            endpoint,
            task_request(
                endpoint,
                "/api/v1/learning-tasks",
                token,
                {"question_id": current["id"], "request_id": str(uuid4())},
                status=202,
            )["id"],
            token,
        )
        task, _ = action(endpoint, task, token, kind="hint")
        refs = state["task_memory_context"]["memory_refs"]
        assert "cognitive:" + update_id in refs
        attempt_id = query(
            env,
            f"SELECT id FROM dataset_practice_attempts WHERE user_id='{owner}' AND mistake_id='{mistake_id}' AND dataset_question_id='{dataset_id}' ORDER BY created_at DESC,id DESC LIMIT 1",
        )
        saved_details = query(
            env,
            f"SELECT grading_details FROM dataset_practice_attempts WHERE id='{attempt_id}'",
        )
        query(
            env,
            f"UPDATE dataset_practice_attempts SET grading_details=JSON_REMOVE(grading_details,'$.alignment_proof') WHERE id='{attempt_id}'",
        )
        try:
            task, _ = action(endpoint, task, token, kind="hint")
            assert (
                "cognitive:" + update_id
                not in state["task_memory_context"]["memory_refs"]
            )
        finally:
            query(
                env,
                f"UPDATE dataset_practice_attempts SET grading_details=CONVERT(0x{saved_details.encode().hex()} USING utf8mb4) WHERE id='{attempt_id}'",
            )
        task, _ = action(endpoint, task, token, kind="hint")
        assert "cognitive:" + update_id in state["task_memory_context"]["memory_refs"]
        query(
            env,
            f"UPDATE dataset_questions SET question_text=CONCAT(question_text,' ') WHERE id='{dataset_id}'",
        )
        try:
            task, _ = action(endpoint, task, token, kind="hint")
            assert (
                "cognitive:" + update_id
                not in state["task_memory_context"]["memory_refs"]
            )
        finally:
            query(
                env,
                f"UPDATE dataset_questions SET question_text='求解 3x=15' WHERE id='{dataset_id}'",
            )
        task, _ = action(endpoint, task, token, kind="hint")
        assert "cognitive:" + update_id in state["task_memory_context"]["memory_refs"]
        print(
            "Cangjie practice memory passed: actual attempt provenance, dataset version invalidation and restored identical source"
        )
    finally:
        for key, value in saved.items():
            if value is None:
                state.pop(key, None)
            else:
                state[key] = value
