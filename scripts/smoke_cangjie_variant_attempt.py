"""Independent variant answers: transitions, remediation, final learning and isolation."""

import json

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def variant_attempts(endpoint, env, query, token, other, state):
    insert = fixture_insert(env, query)
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]

    def create(transfer="near", expected="x=5"):
        question = request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {"question_text": "解方程：3*x+4=19", "question_type": "综合题"},
            token=token,
        )
        # A stored fill-blank recognition uses deterministic symbolic grading.
        query(
            env,
            f"UPDATE questions SET question_type='填空题' WHERE id='{question['id']}'",
        )
        insert(
            "problem_analyses",
            question_id=question["id"],
            final_answer="x=5",
            subject="数学",
            knowledge_points=["一元一次方程"],
        )
        sid = insert(
            "tutor_sessions",
            question_id=question["id"],
            user_id=owner,
            stage=transfer + "_transfer",
            state={
                "teach_back": True,
                "near_transfer": True if transfer == "far" else None,
            },
        )
        vid = insert(
            "variant_questions",
            question_id=question["id"],
            session_id=sid,
            transfer_type=transfer,
            question_text="解方程：3*x+4=19",
            answer=expected,
            reference_solution=["3x=15", "x=5"],
            explanation="先移项再除以系数",
        )
        query(
            env,
            f"UPDATE tutor_sessions SET state=JSON_SET(state,'$.{transfer}_variant_id','{vid}') WHERE id='{sid}'",
        )
        return sid, vid, question["id"]

    def call(vid, answer, expected=200, account=token):
        return request(
            endpoint,
            "POST",
            "/api/v1/variants/" + vid + "/attempt",
            {"answer": answer, "elapsed_seconds": 9, "hint_level": 1},
            token=account,
            expected=expected,
        )

    sid, vid, _qid = create()
    call(vid, "5", expected=401, account=None)
    call(vid, "5", expected=404, account=other)
    call("missing", "5", expected=404)
    first = call(vid, "x=100")
    assert first["correct"] is False and first["stage"] == "near_transfer"
    assert (
        first["attempt"]["elapsed_seconds"] == 9 and first["attempt"]["hint_level"] == 1
    )
    second = call(vid, "x=100")
    assert second["stage"] == "near_transfer"
    saved = json.loads(query(env, f"SELECT state FROM tutor_sessions WHERE id='{sid}'"))
    assert saved["near_attempts"] == 2 and saved["near_confirmation"][
        "correct_answers"
    ] == ["expected"]
    _far_sid, far_vid, far_qid = create("far")
    finished = call(far_vid, "x=5")
    assert finished["correct"] is True and finished["stage"] == "finished"
    assert finished["mastery"] and finished["misconception"]
    assert (
        query(
            env, f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{far_qid}'"
        ).strip()
        == "2"
    )
    call(far_vid, "x=5", expected=409)
    _failed_sid, failed_vid, failed_qid = create("far")
    assert call(failed_vid, "x=100")["stage"] == "far_transfer"
    assert call(failed_vid, "x=100")["stage"] == "finished"
    assert (
        query(
            env,
            f"SELECT interval_days FROM review_plans WHERE question_id='{failed_qid}'",
        ).strip()
        == "1"
    )
    uncertain_sid, uncertain_vid, _ = create(expected="需要完整证明但暂无标准结论")
    uncertain = call(uncertain_vid, "可能如此")
    assert uncertain["attempt"] is None and uncertain["correct"] is None
    assert uncertain["branch"] == "near_transfer_review_required"
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM variant_attempts WHERE variant_id='{uncertain_vid}'",
        ).strip()
        == "0"
    )
    assert (
        query(
            env, f"SELECT COUNT(*) FROM tutor_turns WHERE session_id='{uncertain_sid}'"
        ).strip()
        == "2"
    )
    state["teaching"] = True
    state["variant"] = True
    state["variant_result"] = {
        "question_text": "解方程：3x+4=19",
        "answer": "x=5",
        "reference_solution": ["3x=15", "x=5"],
        "explanation": "先移项再求解。",
    }
    try:
        passed_sid, passed_vid, _ = create()
        passed = call(passed_vid, "x=5")
        assert passed["stage"] == "far_transfer" and passed["correct"] is True
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM variant_questions WHERE session_id='{passed_sid}' AND transfer_type='far'",
            ).strip()
            == "1"
        )
    finally:
        state["teaching"] = False
        state["variant"] = False
    query(
        env,
        f"UPDATE tutor_sessions SET state=JSON_SET(state,'$.question_changed',JSON_EXTRACT('true','$')) WHERE id='{sid}'",
    )
    call(vid, "5", expected=409)
    print(
        "Cangjie independent variant attempts passed: grading, remediation, transfer completion, uncertain results, owner and stage checks"
    )
