"""Durable learning agent: actual HTTP, native workers, isolated MySQL, local Qwen fixture."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert
from smoke_cangjie_self_checks import self_checks
from smoke_cangjie_task_images import task_images
from smoke_cangjie_task_visuals import task_visuals


def task_request(endpoint, path, token, payload=None, *, status=200):
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    body = json.dumps(payload).encode() if payload is not None else None
    try:
        response = urlopen(
            Request(
                endpoint + path,
                data=body,
                headers=headers,
                method="POST" if payload is not None else "GET",
            ),
            timeout=10,
        )
    except HTTPError as error:
        response = error
    with response:
        assert response.status == status, (path, response.status)
        value = json.load(response)
    return value.get("data", value)


def wait_task(endpoint, id, token):
    deadline = time.monotonic() + 15
    while True:
        value = task_request(endpoint, "/api/v1/learning-tasks/" + id, token)
        if value["status"] not in {"queued", "running"}:
            return value
        assert time.monotonic() < deadline, "learning worker did not reach a checkpoint"
        time.sleep(0.05)


def action(endpoint, task, token, kind="answer", text="", request_id=None):
    body = {
        "kind": kind,
        "text": text,
        "version": task["version"],
        "step_id": task["step_id"],
        "input_fingerprint": task["input_fingerprint"],
        "request_id": request_id or str(uuid4()),
    }
    value = task_request(
        endpoint,
        "/api/v1/learning-tasks/" + task["id"] + "/actions",
        token,
        body,
        status=202,
    )
    return wait_task(endpoint, value["id"], token), body


def learning_tasks(endpoint, env, query, token, other, state, started, release):
    insert = fixture_insert(env, query)
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    state["learning_task"] = True
    state["mode"] = "good"

    def create_question(constant=11, question_text=None):
        q = request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {
                "question_text": question_text or f"解方程：2x+3={constant}",
                "student_answer": "x=7",
                "student_steps": [f"2x={constant}+3", "x=7"],
                "subject": "数学",
                "grade": "初一",
            },
            token=token,
        )
        a = insert(
            "problem_analyses",
            question_id=q["id"],
            subject="数学",
            final_answer=f"x={(constant - 3) // 2}",
            knowledge_points=["任务专用等式"],
        )
        insert(
            "reference_steps", analysis_id=a, step_index=0, text=f"2x={constant - 3}"
        )
        insert(
            "reference_steps",
            analysis_id=a,
            step_index=1,
            text=f"x={(constant - 3) // 2}",
        )
        return q

    def create(q, key=None):
        before = time.monotonic()
        value = task_request(
            endpoint,
            "/api/v1/learning-tasks",
            token,
            {"question_id": q["id"], "request_id": key or str(uuid4())},
            status=202,
        )
        assert time.monotonic() - before < 2, (
            "creation must not wait for model/tool execution"
        )
        return value

    try:
        correct = request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {
                "subject": "数学",
                "question_text": "解方程：2x+3=11",
                "student_answer": "x=4",
                "student_steps": ["2x=8", "x=4"],
            },
            token=token,
        )
        insert(
            "problem_analyses",
            question_id=correct["id"],
            subject="数学",
            final_answer="x=4",
        )
        insert(
            "diagnoses",
            question_id=correct["id"],
            error_type="exact",
            first_error_step=None,
            root_misconception="",
        )
        correct_task = wait_task(endpoint, create(correct)["id"], token)
        assert correct_task["student_view"]["title"] == "独立完成这道题"
        assert not correct_task["learning_applied"]
        task_request(
            endpoint,
            "/api/v1/learning-tasks/" + correct_task["id"] + "/cancel",
            token,
            {},
        )
        from smoke_cangjie_learning_memory import learning_memory
        from smoke_cangjie_task_budget import task_budget
        from smoke_cangjie_task_contract import task_contract
        from smoke_cangjie_task_sources import task_sources

        if env.get("CANGJIE_VERIFY_BROWSER") == "1" and not env.get(
            "CANGJIE_VERIFY_FOCUS"
        ):
            entry_question = create_question(35)
            diagnosis_id = insert(
                "diagnoses",
                question_id=entry_question["id"],
                first_error_step=0,
                first_error_text="2x=35+3",
                error_type="invalid_transformation",
                root_misconception="去掉左边的加3时，等式两边应同时减3。",
                recommended_strategy="先在两边同时减3。",
            )
            insert(
                "diagnosis_evidence",
                diagnosis_id=diagnosis_id,
                kind="counterfactual_validation",
                content="入口核验使用已有诊断，不额外生成解释。",
                metadata_json={"status": "inconclusive", "root_cause_confirmed": False},
            )
            entry_task = wait_task(endpoint, create(entry_question)["id"], token)
            env["QA_ENTRY_QUESTION_ID"] = entry_question["id"]
            env["QA_ENTRY_TASK_ID"] = entry_task["id"]
            env["QA_ENTRY_TOKEN"] = token
            env["QA_ENTRY_CLEAR_QUESTION_ID"] = correct["id"]

        if not env.get("CANGJIE_VERIFY_FOCUS") and state.get("inequality_question"):
            inequality = state["inequality_question"]
            checkpoint = wait_task(endpoint, create(inequality)["id"], token)
            assert checkpoint["student_view"]["title"] == "独立完成这道题"
            completed, _ = action(endpoint, checkpoint, token, text="[2,3]")
            assert (
                completed["status"] == "completed" and not completed["learning_applied"]
            )
            history = task_request(
                endpoint,
                "/api/v1/learning-tasks/" + checkpoint["id"] + "/history",
                token,
            )
            assert any(
                row["verdict"] == "confirmed_correct" and row["phase"] == "independent"
                for row in history["items"]
            )
            original = request(
                endpoint, "GET", "/api/v1/questions/" + inequality["id"], token=token
            )
            assert original["student_answer"] == "x≤2或x≥3"
            assert original["student_steps"][0]["text"] == "(x-2)(x-3)≤0"
            if env.get("CANGJIE_VERIFY_BROWSER") == "1":
                preview = wait_task(endpoint, create(inequality)["id"], token)
                env["QA_INEQUALITY_QUESTION_ID"] = inequality["id"]
                env["QA_INEQUALITY_TASK_ID"] = preview["id"]
                env["QA_INEQUALITY_TOKEN"] = token

        if env.get("CANGJIE_VERIFY_FOCUS") == "task-contract":
            return task_contract(
                endpoint, env, query, token, state, create_question, create
            )
        if env.get("CANGJIE_VERIFY_FOCUS") == "task-budget":
            return task_budget(
                endpoint, env, query, token, state, create_question, create
            )
        if env.get("CANGJIE_VERIFY_FOCUS") == "task-memory":
            result = learning_memory(
                endpoint,
                env,
                query,
                token,
                other,
                state,
                create_question,
                create,
                started,
                release,
            )
            from smoke_cangjie_practice import practice

            state["learning_task"] = False
            practice(endpoint, env, query, token, other, state)
            return result
        if env.get("CANGJIE_VERIFY_FOCUS") == "task-sources":
            return task_sources(
                endpoint, env, query, token, other, state, create_question, create
            )
        if env.get("CANGJIE_VERIFY_FOCUS") == "task-visuals":
            return task_visuals(
                endpoint, env, query, token, other, state, create_question, create
            )
        if env.get("CANGJIE_VERIFY_FOCUS") == "task-figures":
            from smoke_cangjie_task_figures import task_figures

            task_figures(endpoint, env, query, token, other, state, create)
            return None
        if env.get("CANGJIE_VERIFY_FOCUS") == "task-images":
            return task_images(
                endpoint,
                env,
                query,
                token,
                other,
                state,
                create_question,
                create,
                started,
                release,
            )["id"]
        task_contract(endpoint, env, query, token, state, create_question, create)
        task_budget(endpoint, env, query, token, state, create_question, create)
        task_sources(endpoint, env, query, token, other, state, create_question, create)
        learning_memory(
            endpoint,
            env,
            query,
            token,
            other,
            state,
            create_question,
            create,
            started,
            release,
        )
        q = create_question()
        key = str(uuid4())
        before = query(
            env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'"
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            created = list(pool.map(lambda _: create(q, key), range(3)))
        assert len({t["id"] for t in created}) == 1
        task = wait_task(endpoint, created[0]["id"], token)
        assert task["status"] == "waiting_student"
        assert all(
            k not in task
            for k in ["checkpoint", "pending_action", "lease_token", "traces"]
        )
        assert "expected" not in json.dumps(task)
        request(
            endpoint,
            "GET",
            "/api/v1/learning-tasks/" + task["id"],
            token=other,
            expected=404,
        )
        request(endpoint, "GET", "/api/v1/learning-tasks/" + task["id"], expected=401)
        task_request(
            endpoint,
            "/api/v1/learning-tasks",
            token,
            {"question_id": q["id"], "request_id": key, "user_id": owner},
            status=422,
        )
        wrong, old_body = action(endpoint, task, token, text="2x=14")
        trace_rows = query(
            env,
            f"SELECT tool_name,validation FROM learning_task_steps WHERE task_id='{task['id']}' AND request_id='{old_body['request_id']}' ORDER BY step_no",
        )
        assert (
            "knowledge_search\trejected" in trace_rows
            and "step_alignment\tverified" in trace_rows
        )
        assert wrong["status"] == "waiting_student" and not wrong["learning_applied"]
        # Same semantic request, different JSON key order: no second observation/write.
        replay = task_request(
            endpoint,
            "/api/v1/learning-tasks/" + task["id"] + "/actions",
            token,
            dict(reversed(list(old_body.items()))),
            status=202,
        )
        assert replay["version"] == wrong["version"]
        task_request(
            endpoint,
            "/api/v1/learning-tasks/" + task["id"] + "/actions",
            token,
            old_body | {"text": "changed"},
            status=409,
        )
        task_request(
            endpoint,
            "/api/v1/learning-tasks/" + task["id"] + "/actions",
            token,
            old_body | {"request_id": str(uuid4())},
            status=409,
        )
        corrected, _ = action(endpoint, wrong, token, text="11-3")
        assert corrected["student_view"]["title"] == "独立完成这道题"
        assert (
            query(
                env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'"
            )
            == before
        )
        contrasted, _ = action(endpoint, corrected, token, text="x=4")
        assert contrasted["student_view"]["title"] == "换个条件，再试一次"
        assert "x=7" not in json.dumps(contrasted, ensure_ascii=False)
        done, body = action(endpoint, contrasted, token, text="x=7")
        assert done["status"] == "completed" and done["learning_applied"]
        evidence = query(
            env,
            f"SELECT COUNT(*) FROM cognitive_updates WHERE JSON_UNQUOTE(JSON_EXTRACT(evidence,'$.learning_task_id'))='{task['id']}'",
        )
        assert evidence == "2"
        task_request(
            endpoint,
            "/api/v1/learning-tasks/" + task["id"] + "/actions",
            token,
            body,
            status=202,
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM cognitive_updates WHERE JSON_UNQUOTE(JSON_EXTRACT(evidence,'$.learning_task_id'))='{task['id']}'",
            )
            == evidence
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM review_plans WHERE question_id='{q['id']}' AND status='pending'",
            )
            == "1"
        )
        # Original work is retained separately from correction attempts.
        original = request(endpoint, "GET", "/api/v1/questions/" + q["id"], token=token)
        assert (
            original["student_answer"] == "x=7"
            and original["student_steps"][0]["text"] == "2x=11+3"
        )
        # Repeating the same already-solved contrast cannot create new independent evidence.
        repeated = wait_task(endpoint, create(q)["id"], token)
        repeated, _ = action(endpoint, repeated, token, text="2x=8")
        repeated, _ = action(endpoint, repeated, token, text="x=4")
        repeated, _ = action(endpoint, repeated, token, text="x=7")
        assert repeated["status"] == "completed" and not repeated["learning_applied"]
        # A duplicate notebook entry is still the same already-seen contrast.
        duplicate_q = create_question()
        duplicate = wait_task(endpoint, create(duplicate_q)["id"], token)
        duplicate, _ = action(endpoint, duplicate, token, text="2x=8")
        duplicate, _ = action(endpoint, duplicate, token, text="x=4")
        duplicate, _ = action(endpoint, duplicate, token, text="x=7")
        assert duplicate["status"] == "completed" and not duplicate["learning_applied"]
        # Equal contrasts in different notebook entries cannot race to score twice.
        simultaneous = []
        for _ in range(2):
            candidate = wait_task(endpoint, create(create_question(17))["id"], token)
            candidate, _ = action(endpoint, candidate, token, text="2x=14")
            candidate, _ = action(endpoint, candidate, token, text="x=7")
            simultaneous.append(candidate)
        with ThreadPoolExecutor(max_workers=2) as pool:
            finished = list(
                pool.map(
                    lambda candidate: action(endpoint, candidate, token, text="x=10")[
                        0
                    ],
                    simultaneous,
                )
            )
        assert sum(bool(item["learning_applied"]) for item in finished) == 1
        task_ids = ",".join("'" + item["id"] + "'" for item in simultaneous)
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM cognitive_updates WHERE JSON_UNQUOTE(JSON_EXTRACT(evidence,'$.learning_task_id')) IN ({task_ids})",
            )
            == "2"
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM learning_task_exposures WHERE task_id IN ({task_ids})",
            )
            == "1"
        )
        # An explicit answer reveal on a fresh source independently taints that contrast.
        assisted_q = create_question(13)
        second = wait_task(endpoint, create(assisted_q)["id"], token)
        second, _ = action(endpoint, second, token, text="2x=10")
        second, _ = action(endpoint, second, token, text="x=5")
        second, _ = action(endpoint, second, token, kind="reveal")
        assert "x=8" in second["student_view"]["feedback"]
        second, _ = action(endpoint, second, token, text="x=8")
        assert second["status"] == "completed" and not second["learning_applied"]
        # In-flight model output cannot write after cancellation.
        third = wait_task(endpoint, create(q)["id"], token)
        state["mode"] = "block"
        started.clear()
        release.clear()
        body = {
            "kind": "hint",
            "version": third["version"],
            "step_id": third["step_id"],
            "input_fingerprint": third["input_fingerprint"],
            "request_id": str(uuid4()),
        }
        task_request(
            endpoint,
            "/api/v1/learning-tasks/" + third["id"] + "/actions",
            token,
            body,
            status=202,
        )
        assert started.wait(5)
        cancelled = task_request(
            endpoint, "/api/v1/learning-tasks/" + third["id"] + "/cancel", token, {}
        )
        assert cancelled["status"] == "cancelled"
        release.set()
        state["mode"] = "good"
        time.sleep(0.3)
        assert wait_task(endpoint, third["id"], token)["status"] == "cancelled"
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM learning_task_actions WHERE task_id='{third['id']}' AND status='applied'",
            )
            == "0"
        )
        self_checks(endpoint, env, query, token, other, done, q, third)
        task_visuals(endpoint, env, query, token, other, state, create_question, create)
        photo_recovery = task_images(
            endpoint,
            env,
            query,
            token,
            other,
            state,
            create_question,
            create,
            started,
            release,
        )
        from smoke_cangjie_task_figures import task_figures

        task_figures(endpoint, env, query, token, other, state, create)
        # Content changes invalidate active checkpoints and reject old evidence.
        changed = create_question()
        stale = wait_task(endpoint, create(changed)["id"], token)
        request(
            endpoint,
            "PATCH",
            "/api/v1/questions/" + changed["id"],
            {"question_text": "解方程：2x+3=15"},
            token=token,
        )
        assert wait_task(endpoint, stale["id"], token)["status"] == "stale"
        # Trigger a real transaction failure after computation; no partial audit/cognition.
        broken = create_question()
        rollback = wait_task(endpoint, create(broken)["id"], token)
        query(
            env,
            f"ALTER TABLE learning_task_steps ADD CONSTRAINT task_rollback_probe CHECK (task_id <> '{rollback['id']}' OR tool_name <> 'grade_answer')",
        )
        try:
            rollback, _ = action(endpoint, rollback, token, text="2x=8")
            rollback, _ = action(endpoint, rollback, token, text="x=4")
            assert rollback["status"] == "failed"
            assert (
                query(
                    env,
                    f"SELECT COUNT(*) FROM learning_task_steps WHERE task_id='{rollback['id']}' AND tool_name='grade_answer'",
                )
                == "0"
            )
        finally:
            query(env, "ALTER TABLE learning_task_steps DROP CHECK task_rollback_probe")
        rollback, _ = action(endpoint, rollback, token, kind="resume")
        assert rollback["status"] == "waiting_student"
        # Persist a claimed checkpoint for the parent runner's actual process restart.
        recovery = photo_recovery
        query(
            env,
            f"UPDATE learning_tasks SET status='running',active_request='restart_probe',lease_token='{uuid4()}',lease_until=UTC_TIMESTAMP()+INTERVAL 1 HOUR WHERE id='{recovery['id']}'",
        )
        print(
            "Cangjie learning tasks passed: async checkpoints, dynamic replan, symbolic scope, actions/idempotency, cancellation, stale inputs, evidence gate, rollback and private views"
        )
        return recovery["id"]
    finally:
        state["learning_task"] = False
        state["mode"] = "good"
        release.set()
