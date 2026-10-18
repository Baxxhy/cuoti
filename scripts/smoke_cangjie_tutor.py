"""Native teaching session creation, private state and atomicity checks."""

import json
from concurrent.futures import ThreadPoolExecutor

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert
from smoke_cangjie_handwriting import handwriting


def tutor_start(endpoint, env, query, token, other, state, started, release):
    insert = fixture_insert(env, query)
    route = "/api/v1/tutor/sessions"

    def create(compressed=False, analyzed=True):
        q = request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {
                "question_text": "解方程：2*x+3=11",
                "question_type": "综合题",
                "student_answer": "5",
                "student_steps": [] if compressed else ["2*x=10", "x=5"],
            },
            token=token,
        )
        if analyzed:
            a = insert(
                "problem_analyses",
                question_id=q["id"],
                subject="数学",
                final_answer="x=4",
                knowledge_points=["方程求解"],
            )
            insert("reference_steps", analysis_id=a, step_index=0, text="2*x=8")
        return q

    def start(q, expected=200, account=token):
        return request(
            endpoint,
            "POST",
            route,
            {"question_id": q["id"]},
            token=account,
            expected=expected,
        )

    def count(q):
        return query(
            env, f"SELECT COUNT(*) FROM tutor_sessions WHERE question_id='{q['id']}'"
        )

    q = create(analyzed=False)
    start(q, 401, None)
    start(q, 404, other)
    start(q, 409)
    request(endpoint, "GET", route, token=token, expected=405)
    request(endpoint, "POST", route, {"question_id": []}, token=token, expected=422)
    q = create()
    before = state["calls"]
    full = start(q)
    assert state["calls"] == before  # Full-plan opening does not need a model.
    assert full["question"]["id"] == q["id"]
    assert full["stage"] == "understanding" and full["stage_status"] == "active"
    assert full["teaching_policy"]["mode"] == "full"
    assert full["activity"]["id"] == "understanding-1"
    assert full["activity"]["attempt"] == 1
    assert "correct_answers" not in full["activity"] and "hint" not in full["activity"]
    assert "understanding_plan" not in full["state"]
    assert full["answer_reveal"]["correct_answer"] == "x=4"
    assert full["visualization_available"] is True
    assert full["turn_count"] == 0 and len(full["turns"]) == 1
    assert full["turns"][0]["role"] == "assistant"
    persisted = json.loads(
        query(env, f"SELECT state FROM tutor_sessions WHERE id='{full['id']}'")
    )
    assert persisted["understanding_plan"][0]["correct_answers"] == ["key"]
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM agent_tool_calls c JOIN agent_runs r ON r.id=c.agent_run_id WHERE r.session_id='{full['id']}' AND c.tool_name='diagnosis_lookup'",
        )
        == "1"
    )
    session_path = route + "/" + full["id"]
    request(endpoint, "GET", session_path, expected=401)
    request(endpoint, "GET", session_path, token=other, expected=404)
    request(endpoint, "POST", session_path, {}, token=token, expected=405)
    restored = request(endpoint, "GET", session_path, token=token)
    assert restored == full
    advance_path = session_path + "/advance"
    rewind_path = session_path + "/rewind"
    request(
        endpoint, "POST", advance_path, {"target_stage": "teach_back"}, expected=401
    )
    request(
        endpoint,
        "POST",
        advance_path,
        {"target_stage": "teach_back"},
        token=other,
        expected=404,
    )
    request(endpoint, "POST", rewind_path, token=other, expected=404)
    request(
        endpoint,
        "POST",
        advance_path,
        {"target_stage": "far_transfer"},
        token=token,
        expected=422,
    )
    request(
        endpoint,
        "POST",
        advance_path,
        {"target_stage": "teach_back"},
        token=token,
        expected=409,
    )
    request(endpoint, "POST", rewind_path, token=token, expected=409)
    query(
        env,
        f"UPDATE tutor_sessions SET state=JSON_SET(state,'$.understanding_passed',CAST('true' AS JSON)) WHERE id='{full['id']}'",
    )
    advanced = request(
        endpoint, "POST", advance_path, {"target_stage": "teach_back"}, token=token
    )
    assert advanced["stage"] == "teach_back" and advanced["message"]
    restored = request(endpoint, "GET", session_path, token=token)
    assert restored["activity"]["type"] == "teach_back"
    assert len(restored["turns"]) == 2
    assert any(
        turn["metadata_json"].get("explicit_transition") for turn in restored["turns"]
    )
    back = request(endpoint, "POST", rewind_path, token=token)
    assert (
        back["stage"] == "understanding"
        and back["state"]["understanding_passed"] is True
    )
    assert back["state"]["teach_back"] is None
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM agent_tool_calls c JOIN agent_runs r ON r.id=c.agent_run_id WHERE r.session_id='{full['id']}' AND c.tool_name IN ('transition_tutor_stage','rewind_tutor_stage')",
        )
        == "2"
    )
    # Restore persisted progress, including a legacy stage alias and old empty state.
    query(
        env,
        f"UPDATE tutor_sessions SET stage='teach_back_retry' WHERE id='{full['id']}'",
    )
    restored = request(endpoint, "GET", session_path, token=token)
    assert restored["stage"] == "teach_back"
    assert restored["activity"]["type"] == "teach_back"
    assert restored["activity"]["keywords"] == ["方程求解"]
    query(
        env,
        f"UPDATE tutor_sessions SET stage='understanding', state=JSON_SET(state,'$.understanding_passed',CAST('true' AS JSON)) WHERE id='{full['id']}'",
    )
    restored = request(endpoint, "GET", session_path, token=token)
    assert restored["stage_status"] == "passed" and restored["activity"] is None
    query(env, f"UPDATE tutor_sessions SET stage='finished' WHERE id='{full['id']}'")
    restored = request(endpoint, "GET", session_path, token=token)
    assert restored["stage_status"] == "completed" and restored["activity"] is None
    query(
        env,
        f"UPDATE tutor_sessions SET stage='understanding',state=JSON_OBJECT() WHERE id='{full['id']}'",
    )
    restored = request(endpoint, "GET", session_path, token=token)
    assert restored["activity"]["id"] == "understanding-1"
    assert restored["state"]["understanding_passed"] is False
    assert "understanding_plan" not in restored["state"]
    # Each explicit start creates an independent session, as in the original.
    assert start(q)["id"] != full["id"] and count(q) == "2"
    q = create()
    query(
        env,
        f"ALTER TABLE agent_tool_calls ADD CONSTRAINT cj_tutor_fail CHECK (JSON_UNQUOTE(JSON_EXTRACT(input_json, '$.question_id')) <> '{q['id']}')",
    )
    try:
        start(q, 503)
        assert count(q) == "0"
    finally:
        query(env, "ALTER TABLE agent_tool_calls DROP CHECK cj_tutor_fail")
    state["teaching"] = True
    state["mode"] = "good"
    state["teaching_result"] = {
        "topic": "方程求解",
        "correct_answer": "wrong",
        "key_explanation": "先移项再求解。",
        "option_explanations": [],
        "check": {
            "id": "targeted-check",
            "type": "short_answer",
            "title": "检查",
            "question": "x+1=3 的解是什么？",
            "correct_answers": ["2"],
        },
    }
    try:
        q = create(compressed=True)
        brief = start(q)
        assert brief["teaching_policy"]["mode"] == "compressed"
        assert brief["activity"]["id"] == "answer-reveal"
        assert brief["answer_reveal"]["correct_answer"] == "x=4"
        assert "teaching_brief" not in brief["state"]
        assert "targeted-check" not in json.dumps(brief)
        assert count(q) == "1"
        query(
            env,
            f"UPDATE tutor_sessions SET stage='near_transfer', state=JSON_SET(state,'$.near_attempts',2) WHERE id='{brief['id']}'",
        )
        back = request(
            endpoint, "POST", route + "/" + brief["id"] + "/rewind", token=token
        )
        assert back["stage"] == "understanding"
        assert back["activity"]["id"] == "answer-reveal"
        assert back["state"]["understanding_passed"] is False
        assert back["state"]["answer_reveal_acknowledged"] is False
        brief = request(endpoint, "GET", route + "/" + brief["id"], token=token)
        brief_path = route + "/" + brief["id"]
        assert request(endpoint, "GET", brief_path, token=token) == brief
        query(
            env,
            f"UPDATE tutor_sessions SET state=JSON_SET(state,'$.answer_reveal_acknowledged',CAST('true' AS JSON),'$.targeted_check_pending',CAST('true' AS JSON),'$.activity_attempts',JSON_OBJECT('targeted-check',1)) WHERE id='{brief['id']}'",
        )
        restored = request(endpoint, "GET", brief_path, token=token)
        assert restored["activity"]["id"] == "targeted-check"
        assert restored["activity"]["attempt"] == 2
        assert "correct_answers" not in restored["activity"]
        choice = request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {
                "question_text": "哪个数没有倒数？",
                "question_type": "单选题",
                "student_answer": "选择 A",
                "options": [{"label": "A", "text": "1"}, {"label": "B", "text": "0"}],
            },
            token=token,
        )
        insert(
            "problem_analyses",
            question_id=choice["id"],
            subject="数学",
            final_answer="B",
            knowledge_points=["倒数"],
        )
        choice_session = start(choice)
        assert choice_session["answer_reveal"]["student_answer"] == "A"
        assert choice_session["answer_reveal"]["correct_answer"] == "B"
        # An unanswered question must still create a valid opening.
        unanswered = create(compressed=True)
        query(
            env,
            f"UPDATE questions SET student_answer=NULL WHERE id='{unanswered['id']}'",
        )
        assert start(unanswered)["answer_reveal"]["student_answer"] == "未作答"
        state["mode"] = "fail"
        assert (
            start(create(compressed=True))["answer_reveal"]["correct_answer"] == "x=4"
        )
        # While the model is running, a new answer invalidates its input snapshot.
        for action in ("answer", "archive"):
            q = create(compressed=True)
            started.clear()
            release.clear()
            state["mode"] = "block"
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(start, q, 409 if action == "answer" else 404)
                assert started.wait(10)
                path = "/api/v1/questions/" + q["id"]
                if action == "answer":
                    request(
                        endpoint,
                        "POST",
                        path + "/student-work",
                        {"answer": "8"},
                        token=token,
                    )
                else:
                    request(endpoint, "DELETE", path, token=token)
                release.set()
                future.result(timeout=15)
            assert count(q) == "0"
        q = create()
        request(endpoint, "DELETE", "/api/v1/questions/" + q["id"], token=token)
        start(q, 404)
        state["mode"] = "good"
        state["variant"] = True
        state["variant_result"] = {
            "question_text": "解方程：3x+4=19",
            "answer": "x=5",
            "reference_solution": ["3x=15", "x=5"],
            "explanation": "继续练习一元一次方程。",
        }
        q = create()
        query(
            env,
            f"UPDATE problem_analyses SET knowledge_points=JSON_ARRAY('一元一次方程') WHERE question_id='{q['id']}'",
        )
        lesson = start(q)
        lesson_path = route + "/" + lesson["id"]
        variant_path = lesson_path + "/variant"
        request(endpoint, "POST", variant_path, {}, expected=401)
        request(endpoint, "POST", variant_path, {}, token=other, expected=404)
        request(endpoint, "POST", variant_path, {}, token=token, expected=409)
        request(
            endpoint,
            "POST",
            variant_path,
            {"transfer_type": "bad"},
            token=token,
            expected=422,
        )
        query(
            env,
            f"UPDATE tutor_sessions SET stage='near_transfer' WHERE id='{lesson['id']}'",
        )
        variant = request(endpoint, "POST", variant_path, {}, token=token)
        assert variant["verified"] is True and variant["transfer_type"] == "near"
        assert "answer" not in variant and "reference_solution" not in variant
        assert (
            query(
                env, f"SELECT answer FROM variant_questions WHERE id='{variant['id']}'"
            )
            == "x=5"
        )
        calls = state["calls"]
        assert (
            request(endpoint, "POST", variant_path, {}, token=token)["id"]
            == variant["id"]
        )
        activity = request(endpoint, "GET", lesson_path, token=token)["activity"]
        assert (
            activity["variant_id"] == variant["id"]
            and activity["question"] == variant["question_text"]
        )
        assert "answer" not in activity
        assert state["calls"] == calls
        # Reading a later stage creates its missing exercise and persists it.
        query(
            env,
            f"UPDATE tutor_sessions SET stage='far_transfer' WHERE id='{lesson['id']}'",
        )
        state["mode"] = "fail"
        activity = request(endpoint, "GET", lesson_path, token=token)["activity"]
        assert "练习本" in activity["question"]
        far = request(
            endpoint, "POST", variant_path, {"transfer_type": "far"}, token=token
        )
        assert far["id"] == activity["variant_id"] and far["verified"] is True
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM variant_questions WHERE session_id='{lesson['id']}'",
            )
            == "2"
        )
        back = request(endpoint, "POST", lesson_path + "/rewind", token=token)
        assert (
            back["stage"] == "near_transfer"
            and back["activity"]["variant_id"] == variant["id"]
        )
        back = request(endpoint, "POST", lesson_path + "/rewind", token=token)
        assert (
            back["stage"] == "teach_back" and back["activity"]["type"] == "teach_back"
        )
        # A real student flow: two understanding answers, advance, teach-back, exercise.
        state["mode"] = "good"
        state["variant"] = True
        flow_question = create()
        query(
            env,
            f"UPDATE problem_analyses SET knowledge_points=JSON_ARRAY('一元一次方程') WHERE question_id='{flow_question['id']}'",
        )
        flow = start(flow_question)
        flow_path = route + "/" + flow["id"]
        answer_path = flow_path + "/activity/answer"
        request(
            endpoint,
            "POST",
            answer_path,
            {"activity_id": "understanding-1", "answer": "key"},
            expected=401,
        )
        request(
            endpoint,
            "POST",
            answer_path,
            {"activity_id": "understanding-1", "answer": "key"},
            token=other,
            expected=404,
        )
        request(
            endpoint,
            "POST",
            answer_path,
            {"activity_id": "old", "answer": "key"},
            token=token,
            expected=409,
        )
        flow = request(
            endpoint,
            "POST",
            answer_path,
            {"activity_id": "understanding-1", "answer": "key"},
            token=token,
        )
        assert flow["activity"]["id"] == "understanding-2"
        flow = request(
            endpoint,
            "POST",
            answer_path,
            {"activity_id": "understanding-2", "answer": "reference"},
            token=token,
        )
        assert (
            flow["state"]["understanding_passed"] is True and flow["activity"] is None
        )
        request(
            endpoint,
            "POST",
            flow_path + "/advance",
            {"target_stage": "teach_back"},
            token=token,
        )
        flow = request(
            endpoint,
            "POST",
            answer_path,
            {
                "activity_id": "teach-back",
                "answer": "因为一元一次方程可以对等式两边做相同运算，所以先移项再除以系数。",
            },
            token=token,
        )
        assert (
            flow["stage"] == "near_transfer"
            and flow["state"]["teach_back_passed"] is True
        )
        assert flow["activity"]["variant_id"] and flow["turn_count"] == 3
        assert len(flow["turns"]) == 8
        assert any(
            turn["content"] == "一元一次方程" for turn in flow["turns"]
        )  # Selected value renders its label.
        assert "correct_answers" not in flow["activity"]
        assert [t["role"] for t in flow["turns"]] == [
            "assistant",
            "user",
            "assistant",
            "user",
            "assistant",
            "assistant",
            "user",
            "assistant",
        ]
        handwritten = handwriting(endpoint, env, token, other, flow, state)
        for expected_stage in ["far_transfer", "finished"]:
            activity = flow["activity"]
            expected_answer = query(
                env,
                f"SELECT answer FROM variant_questions WHERE id='{activity['variant_id']}'",
            ).strip()
            flow = request(
                endpoint,
                "POST",
                flow_path + "/activity/answer",
                {
                    "activity_id": activity["id"],
                    "answer": expected_answer,
                    "elapsed_seconds": 12,
                    **handwritten,
                },
                token=token,
            )
            assert flow["stage"] == expected_stage, flow
        assert (
            flow["turns"][-2]["metadata_json"]["handwriting_recognition"]
            == handwritten["handwriting_recognition"]
        )
        assert (
            "signature=" in flow["turns"][-2]["metadata_json"]["handwriting_image_url"]
        )
        assert flow["status"] == "completed" and flow["activity"] is None
        assert flow["mastery_score"] > 0 and flow["completion_summary"]
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM variant_attempts a JOIN variant_questions v ON v.id=a.variant_id WHERE v.session_id='{flow['id']}' AND a.elapsed_seconds=12",
            ).strip()
            == "2"
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{flow_question['id']}'",
            ).strip()
            == "2"
        )
        assert (
            query(
                env,
                f"SELECT interval_days FROM review_plans WHERE question_id='{flow_question['id']}'",
            ).strip()
            == "15"
        )
        request(
            endpoint,
            "POST",
            flow_path + "/activity/answer",
            {"activity_id": "finished", "answer": "5"},
            token=token,
            expected=409,
        )
        helped = start(create())
        helped_path = route + "/" + helped["id"] + "/activity/answer"
        helped = request(
            endpoint,
            "POST",
            helped_path,
            {"activity_id": "understanding-1", "answer": "answer"},
            token=token,
        )
        assert helped["activity"]["attempt"] == 2 and helped["activity"]["feedback"]
        helped = request(
            endpoint,
            "POST",
            helped_path,
            {"activity_id": "understanding-1", "answer": "__unknown__"},
            token=token,
        )
        assert (
            helped["activity"]["id"] == "understanding-1-confirmation"
            and helped["assisted"]
        )
        helped = request(
            endpoint,
            "POST",
            helped_path,
            {"activity_id": "understanding-1-confirmation", "answer": "yes"},
            token=token,
        )
        assert helped["activity"]["id"] == "understanding-2"
        state["variant"] = False
        compact = start(create(compressed=True))
        compact_path = route + "/" + compact["id"] + "/activity/answer"
        compact = request(
            endpoint,
            "POST",
            compact_path,
            {"activity_id": "answer-reveal", "answer": "need_help"},
            token=token,
        )
        assert compact["activity"]["id"] == "targeted-check"
        state["variant"] = True
        compact = request(
            endpoint,
            "POST",
            compact_path,
            {"activity_id": "targeted-check", "answer": "2"},
            token=token,
        )
        assert (
            compact["stage"] == "near_transfer"
            and compact["state"]["understanding_passed"] is True
        )
        assert compact["activity"]["variant_id"]
        activity = compact["activity"]
        compact = request(
            endpoint,
            "POST",
            compact_path,
            {"activity_id": activity["id"], "answer": "不会写"},
            token=token,
        )
        assert compact["activity"]["attempt"] == 1 and compact["assisted"]
        assert compact["turns"][-1]["content"].startswith("可以按这个顺序写")
        expected_answer = query(
            env,
            f"SELECT answer FROM variant_questions WHERE id='{activity['variant_id']}'",
        ).strip()
        compact = request(
            endpoint,
            "POST",
            compact_path,
            {
                "activity_id": activity["id"],
                "answer": expected_answer,
                "elapsed_seconds": 12,
            },
            token=token,
        )
        assert compact["stage"] == "finished" and compact["status"] == "completed"
        assert (
            query(
                env,
                f"SELECT interval_days FROM review_plans WHERE question_id='{compact['question_id']}'",
            ).strip()
            == "3"
        )
        state["variant"] = False
    finally:
        release.set()
        state["mode"] = "good"
        state["teaching"] = False
        state["variant"] = False
    print(
        "Cangjie tutor start passed: full/compressed modes, private keys, atomic writes, ownership and stale inputs"
    )
