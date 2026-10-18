"""Actual chat rounds: original agent rules, native knowledge access and persisted evidence."""

import io
import json
from pathlib import Path

from PIL import Image, ImageDraw
from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def tutor_dialogue(endpoint, env, query, token, other, state):
    insert = fixture_insert(env, query)
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    foreign = request(endpoint, "GET", "/api/v1/auth/me", token=other)["id"]
    question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "question_text": "解方程：2*x+3=11",
            "question_type": "综合题",
            "student_answer": "5",
            "student_steps": ["2x=10", "x=5"],
        },
        token=token,
    )
    qid = question["id"]
    query(
        env,
        f"UPDATE questions SET knowledge_points=JSON_ARRAY('对话专用条件') WHERE id='{qid}'",
    )
    analysis = insert(
        "problem_analyses",
        question_id=qid,
        subject="数学",
        final_answer="x=4",
        knowledge_points=["对话专用条件"],
    )
    insert("reference_steps", analysis_id=analysis, step_index=0, text="2x=8")
    insert("reference_steps", analysis_id=analysis, step_index=1, text="x=4")
    sid = insert(
        "tutor_sessions",
        user_id=owner,
        question_id=qid,
        stage="teach_back",
        state={
            "understanding_passed": True,
            "mastery_proven": False,
            "teach_back": None,
        },
    )
    memory_now = query(env, "SELECT UTC_TIMESTAMP()")
    insert(
        "mastery_states",
        updated_at=memory_now,
        user_id=owner,
        subject="数学",
        knowledge_point="对话专用条件",
        mastery_score=0.4,
        forgetting_risk=0.99,
    )
    insert(
        "misconception_states",
        updated_at=memory_now,
        user_id=owner,
        subject="数学",
        code="chat-condition",
        label="检查等式条件",
        probability=0.99,
        status="active",
    )
    insert(
        "misconception_states",
        user_id=foreign,
        subject="数学",
        code="chat-foreign",
        label="foreign memory must not appear",
        probability=1.0,
        status="active",
    )
    card = insert(
        "knowledge_points",
        code="000-CHAT",
        name="对话专用条件",
        subject="数学",
        content={"definition": "先明确条件，再选择规则。"},
    )
    path = "/api/v1/tutor/sessions/" + sid
    route = path + "/turns"
    request(endpoint, "POST", route, {"message": "提示"}, expected=401)
    request(endpoint, "POST", route, {"message": "提示"}, token=other, expected=404)
    request(endpoint, "POST", route, {"message": " "}, token=token, expected=422)
    request(endpoint, "POST", route, {"message": []}, token=token, expected=422)
    request(
        endpoint,
        "POST",
        "/api/v1/tutor/sessions/missing/turns",
        {"message": "提示"},
        token=token,
        expected=404,
    )
    state["dialogue"] = True
    state["dialogue_reply"] = {
        "reply": "先观察等式两边的条件，再解释这一步为什么成立。"
    }

    def chat(message, tool, expected=200):
        state["dialogue_plan"] = {
            "goal": "帮助理解等式条件",
            "steps": ["核对已有条件", "执行一个教学动作"],
            "tool_name": tool,
            "tool_input": {},
            "expected_evidence": ["evidence"],
            "decision_summary": "结合当前表达选择教学动作",
            "memory_source_ids": [],
            "confidence": 0.9,
        }
        return request(
            endpoint,
            "POST",
            route,
            {"message": message},
            token=token,
            expected=expected,
        )

    try:
        first = chat("我不会", "knowledge_search")
        assert (
            first["stage"] == "teach_back" and first["tool_name"] == "knowledge_search"
        )
        assert (
            first["planner_status"] == "model"
            and first["decision_verified"] == "verified"
        )
        assert (
            "知识卡 · 对话专用条件" in first["message"]
            and first["mastery_proven"] is False
        )
        hint = chat("请给提示", "step_alignment")
        assert hint["hint_level"] == 2 and "第2步" in hint["message"]
        repeated = chat("请给提示", "visualization")
        assert (
            repeated["branch"] == "repeated_error" and "互动图示" in repeated["message"]
        )
        renewed = chat("我又觉得有新错误", "rediagnose")
        assert renewed["branch"] == "new_error" and "检查等式条件" in renewed["message"]
        checked = chat("x=4", "answer_check")
        assert (
            checked["decision_verified"] == "verified"
            and "结论能够核对上" in checked["message"]
        )
        revealed = chat("只要答案", "answer_reveal")
        assert "x=4" in revealed["message"] and revealed["stage"] == "teach_back"
        guarded = chat("请给一个提示", "answer_reveal")
        assert (
            guarded["planner_status"] == "fallback"
            and guarded["tool_name"] == "step_alignment"
        )
        assert "x=4" not in guarded["message"]
        # Supply an actual original crop; the model transport checks the red pixels.
        picture = Image.new("RGB", (100, 80), "white")
        ImageDraw.Draw(picture).rectangle((20, 10, 40, 30), fill="red")
        output = io.BytesIO()
        picture.save(output, "PNG")
        image_path = f"uploads/{qid}/dialogue-original.png"
        target = Path(env["CANGJIE_MEDIA_ROOT"]) / image_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(output.getvalue())
        insert("question_assets", question_id=qid, kind="crop", path=image_path)
        state["image_size"] = (100, 80)
        visual = chat("帮我核对当前条件", "step_alignment")
        assert state["dialogue_images"] == 1 and "先观察等式" in visual["message"]
        assert visual["stage"] == "teach_back" and visual["mastery_proven"] is False
        restored = request(endpoint, "GET", path, token=token)
        assert restored["turn_count"] == 8 and len(restored["turns"]) == 16
        assert restored["state"]["understanding_passed"] is True
        assert [t["role"] for t in restored["turns"]] == ["user", "assistant"] * 8
        assert (
            query(
                env, f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{qid}'"
            ).strip()
            == "0"
        )
        runs = json.loads(
            query(
                env,
                f"SELECT JSON_ARRAYAGG(result) FROM agent_runs WHERE session_id='{sid}'",
            )
        )
        assert len(runs) == 8 and all(
            r["plan"] and r["verification"]["checks"] for r in runs
        )
        assert any("mastery:" in str(r["plan"]["memory_source_ids"]) for r in runs)
        assert "foreign memory must not appear" not in str(runs)
        state_before = query(env, f"SELECT state FROM tutor_sessions WHERE id='{sid}'")
        query(
            env,
            "ALTER TABLE agent_tool_calls ADD CONSTRAINT cj_dialogue_rollback CHECK (COALESCE(JSON_UNQUOTE(JSON_EXTRACT(input_json,'$.student_message')),'') <> 'dialogue-rollback-probe')",
        )
        try:
            chat("dialogue-rollback-probe", "step_alignment", expected=503)
            assert (
                query(
                    env, f"SELECT COUNT(*) FROM tutor_turns WHERE session_id='{sid}'"
                ).strip()
                == "16"
            )
            assert (
                query(env, f"SELECT state FROM tutor_sessions WHERE id='{sid}'")
                == state_before
            )
            assert (
                query(
                    env, f"SELECT turn_count FROM tutor_sessions WHERE id='{sid}'"
                ).strip()
                == "8"
            )
        finally:
            query(env, "ALTER TABLE agent_tool_calls DROP CHECK cj_dialogue_rollback")
        query(env, f"UPDATE tutor_sessions SET stage='finished' WHERE id='{sid}'")
        chat("再给提示", "step_alignment", expected=409)
        query(
            env,
            f"UPDATE tutor_sessions SET stage='teach_back',state=JSON_SET(state,'$.question_changed',JSON_EXTRACT('true','$')) WHERE id='{sid}'",
        )
        chat("再给提示", "step_alignment", expected=409)
    finally:
        state["dialogue"] = False
        # Keep this fixture's generic card out of later diagnosis mapping.
        query(env, f"DELETE FROM knowledge_points WHERE id='{card}'")
    print(
        "Cangjie tutor dialogue passed: original branches/tools, long-term memory, real knowledge lookup, images, stage guards, no chat mastery, ownership and atomic writes"
    )
