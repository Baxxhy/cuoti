"""Teach-back evaluation, completion idempotence, Python parity and atomic writes."""

import ast
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def tutor_completion(endpoint, env, query, token, other, state):
    insert = fixture_insert(env, query)
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]

    def scalar(sql):
        return query(env, sql).strip()

    def session(stage="teach_back", flags=None):
        question = request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {
                "question_text": "解方程：2*x+3=11",
                "knowledge_points": ["一次方程"],
                "question_type": "综合题",
                "student_steps": ["2x=8"],
            },
            token=token,
        )
        analysis = insert(
            "problem_analyses",
            question_id=question["id"],
            subject="数学",
            final_answer="x=4",
            knowledge_points=["一次方程"],
        )
        insert("reference_steps", analysis_id=analysis, step_index=0, text="2x=8")
        sid = insert(
            "tutor_sessions",
            user_id=owner,
            question_id=question["id"],
            stage=stage,
            state={
                "understanding_passed": True,
                "understanding_plan": [{"correct_answers": ["private-key"]}],
                **(flags or {}),
            },
        )
        return sid, question["id"]

    def call(sid, action, body=None, expected=200, account=token):
        return request(
            endpoint,
            "POST",
            f"/api/v1/tutor/sessions/{sid}/{action}",
            body,
            token=account,
            expected=expected,
        )

    def read(sid):
        return request(endpoint, "GET", f"/api/v1/tutor/sessions/{sid}", token=token)

    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project / "backend"))
    from app import models
    from app.services.cognition import cognition_target, update_cognition
    from app.services.pedagogy import evaluate_teach_back
    from app.services.timestamps import iso_timestamp
    from app.services.tutor_state import canonical_tutor_stage
    from fastapi import HTTPException
    from sqlalchemy import URL, select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    names = {
        "finish_tutor",
        "complete_tutor_learning",
        "public_tutor_session",
        "row_dict",
        "record_agent_tool",
    }
    functions = []
    for node in ast.parse((project / "backend/app/main.py").read_text()).body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in names
        ):
            node.decorator_list = []
            # Preserve pure defaults such as run_result=None; remove injected defaults.
            if node.name == "finish_tutor":
                node.args.defaults = []
            node.returns = None
            for arg in (*node.args.args, *node.args.kwonlyargs):
                arg.annotation = None
            functions.append(node)
    assert len(functions) == len(names)
    namespace = {
        **vars(models),
        "select": select,
        "datetime": datetime,
        "timezone": timezone,
        "timedelta": timedelta,
        "HTTPException": HTTPException,
        "iso_timestamp": iso_timestamp,
        "cognition_target": cognition_target,
        "update_cognition": update_cognition,
        "canonical_tutor_stage": canonical_tutor_stage,
        "envelope": lambda value: value,
    }
    exec(  # noqa: S102 -- selected original functions, isolated test DB and outer rollback
        compile(
            ast.Module(body=functions, type_ignores=[]),
            "<reference-tutor-completion>",
            "exec",
        ),
        namespace,
    )

    async def reference(sid):
        engine = create_async_engine(
            URL.create(
                "mysql+asyncmy",
                username=env["CANGJIE_DB_USER"],
                password=env["CANGJIE_DB_PASSWORD"],
                host=env["CANGJIE_DB_HOST"],
                port=int(env["CANGJIE_DB_PORT"]),
                database=env["CANGJIE_DB_NAME"],
            )
        )
        try:
            async with engine.connect() as connection:
                outer = await connection.begin()
                try:
                    async with AsyncSession(
                        bind=connection,
                        join_transaction_mode="create_savepoint",
                        expire_on_commit=False,
                    ) as db:
                        return await namespace["finish_tutor"](
                            session_id=sid,
                            payload={},
                            user=SimpleNamespace(id=owner),
                            db=db,
                        )
                finally:
                    await outer.rollback()
        finally:
            await engine.dispose()

    def stable(value):
        if isinstance(value, dict):
            return {
                k: stable(v)
                for k, v in value.items()
                if k
                not in {"id", "created_at", "updated_at", "last_evidence_at", "due_at"}
            }
        if isinstance(value, list):
            return [stable(v) for v in value]
        return value

    def compared_finish(sid):
        expected = asyncio.run(reference(sid))
        actual = call(sid, "finish", {})
        assert stable(actual) == stable(expected), (actual, expected)
        if actual["review"]:
            assert (
                abs(
                    (
                        datetime.fromisoformat(actual["review"]["due_at"])
                        - datetime.fromisoformat(expected["review"]["due_at"])
                    ).total_seconds()
                )
                < 15
            )
        return actual

    sid, _qid = session()
    for action in ("teach-back", "finish"):
        call(sid, action, {}, expected=401, account=None)
        call(sid, action, {}, expected=404, account=other)
        call("missing", action, {}, expected=404)
        request(
            endpoint,
            "GET",
            f"/api/v1/tutor/sessions/{sid}/{action}",
            token=token,
            expected=405,
        )
    call(sid, "finish", {}, expected=409)
    call(sid, "teach-back", {"explanation": []}, expected=422)
    explanation = "还不会"
    expected = evaluate_teach_back(
        explanation, "数学", "综合题", ["一次方程"], ["2x=8"]
    )
    before = state["calls"]
    failed = call(sid, "teach-back", {"explanation": explanation})
    assert (
        not failed["passed"]
        and not failed["assisted"]
        and failed["feedback"] == expected["feedback"]
    )
    assert failed["stage"] == "teach_back" and state["calls"] == before
    saved = json.loads(scalar(f"SELECT state FROM tutor_sessions WHERE id='{sid}'"))
    assert saved["teach_back_attempts"] == 1 and saved["teach_back_passed"] is False
    assert scalar(f"SELECT COUNT(*) FROM tutor_turns WHERE session_id='{sid}'") == "2"
    state["variant"] = True
    state["teaching"] = True
    state["variant_result"] = {
        "question_text": "解方程：3x+4=19",
        "answer": "x=5",
        "reference_solution": ["3x=15", "x=5"],
        "explanation": "先移项，再求解。",
    }
    state["mode"] = "good"
    try:
        assisted = call(sid, "teach-back", {"explanation": explanation})
        assert (
            not assisted["passed"]
            and assisted["assisted"]
            and assisted["stage"] == "near_transfer"
        )
        assert read(sid)["activity"]["variant_id"]
        call(sid, "teach-back", {"explanation": explanation}, expected=409)
        good, good_qid = session()
        text = "根据一次方程的等式性质，先移项再求解，所以最后要检查结果。"
        assessed = evaluate_teach_back(text, "数学", "综合题", ["一次方程"], ["2x=8"])
        passed = call(good, "teach-back", {"explanation": text})
        assert (
            passed["passed"]
            and not passed["assisted"]
            and passed["feedback"] == assessed["feedback"]
        )
        assert passed["stage"] == "near_transfer"
        assert (
            scalar(f"SELECT COUNT(*) FROM variant_questions WHERE session_id='{good}'")
            == "1"
        )
        assert (
            scalar(
                f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{good_qid}'"
            )
            == "0"
        )
        assert "private-key" not in json.dumps(read(good))
        for flags, interval in [
            ({"teach_back": True, "near_transfer": True, "far_transfer": True}, 15),
            (
                {
                    "teach_back": False,
                    "near_transfer": True,
                    "far_transfer": True,
                    "assisted": True,
                },
                3,
            ),
            (
                {
                    "teach_back": True,
                    "near_transfer": True,
                    "far_transfer": False,
                    "assisted": True,
                    "transfer_insufficient": True,
                },
                1,
            ),
        ]:
            finished, question_id = session("finished", flags)
            result = compared_finish(finished)
            assert (
                result["session"]["status"] == "completed"
                and result["review"]["interval_days"] == interval
            )
            assert "understanding_plan" not in result["session"]["state"]
            assert result["session"]["state"]["mastery_proven"] == (interval != 1)
            assert (
                scalar(
                    f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{question_id}'"
                )
                == "2"
            )
            repeated = compared_finish(finished)
            assert (
                repeated["mastery"] is None
                and repeated["review"]["id"] == result["review"]["id"]
            )
            assert (
                scalar(
                    f"SELECT COUNT(*) FROM review_plans WHERE question_id='{question_id}'"
                )
                == "1"
            )
            assert (
                scalar(
                    f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{question_id}'"
                )
                == "2"
            )
        # Failing the final tool record must undo all preceding writes, including generation.
        rollback_teach, _teach_qid = session()
        rollback_finish, finish_qid = session(
            "finished",
            {"teach_back": True, "near_transfer": True, "far_transfer": True},
        )
        existing_tools = scalar(
            "SELECT id FROM agent_tool_calls WHERE tool_name='update_cognition'"
        ).splitlines()
        existing_ids = ",".join("'" + value + "'" for value in existing_tools) or "''"
        query(
            env,
            f"ALTER TABLE agent_tool_calls ADD CONSTRAINT cj_completion_rollback CHECK (COALESCE(JSON_UNQUOTE(JSON_EXTRACT(input_json,'$.explanation')),'') NOT LIKE '%completion-rollback-probe%' AND (tool_name <> 'update_cognition' OR id IN ({existing_ids})))",
        )
        try:
            call(
                rollback_teach,
                "teach-back",
                {"explanation": text + " completion-rollback-probe"},
                expected=503,
            )
            assert (
                scalar(
                    f"SELECT COUNT(*) FROM tutor_turns WHERE session_id='{rollback_teach}'"
                )
                == "0"
            )
            assert (
                scalar(
                    f"SELECT COUNT(*) FROM variant_questions WHERE session_id='{rollback_teach}'"
                )
                == "0"
            )
            assert (
                scalar(
                    f"SELECT COUNT(*) FROM agent_runs WHERE session_id='{rollback_teach}'"
                )
                == "0"
            )
            assert "teach_back_attempts" not in json.loads(
                scalar(f"SELECT state FROM tutor_sessions WHERE id='{rollback_teach}'")
            )
            call(rollback_finish, "finish", {}, expected=503)
            assert (
                scalar(
                    f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{finish_qid}'"
                )
                == "0"
            )
            assert (
                scalar(
                    f"SELECT COUNT(*) FROM review_plans WHERE question_id='{finish_qid}'"
                )
                == "0"
            )
            assert (
                scalar(
                    f"SELECT status FROM tutor_sessions WHERE id='{rollback_finish}'"
                )
                == "active"
            )
        finally:
            query(env, "ALTER TABLE agent_tool_calls DROP CHECK cj_completion_rollback")
        # Changes to the source invalidate unfinished sessions.
        changed, _changed_qid = session()
        query(
            env,
            f"UPDATE tutor_sessions SET state=JSON_SET(state,'$.question_changed',JSON_EXTRACT('true','$')) WHERE id='{changed}'",
        )
        call(changed, "teach-back", {"explanation": text}, expected=409)
        archived, archived_qid = session("finished", {"far_transfer": True})
        query(env, f"UPDATE questions SET status='archived' WHERE id='{archived_qid}'")
        call(archived, "finish", {}, expected=409)
    finally:
        state["variant"] = False
        state["teaching"] = False
        state["mode"] = "good"
    print(
        "Cangjie teaching completion passed: original Python teach-back evaluation, transitions, finish parity, idempotence, private state, permissions and atomic rollback"
    )
