"""System state and administrator read contracts, compared with the original MySQL queries."""

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def system_admin(endpoint, env, query, token, other):
    insert = fixture_insert(env, query)
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    admin = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": "cj-admin-" + uuid4().hex + "@example.test",
            "password": "admin-test-password",
            "name": "管理验证",
        },
    )
    query(env, f"UPDATE users SET role='admin' WHERE id='{admin['id']}'")
    admin_token = admin["access_token"]
    question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "管理员会话验证", "student_answer": "5"},
        token=token,
    )
    sid = insert(
        "tutor_sessions",
        user_id=owner,
        question_id=question["id"],
        stage="teach_back",
        state={"secret": "do-not-expose"},
    )
    insert(
        "diagnoses",
        question_id=question["id"],
        error_type="calculation",
        root_misconception="计算条件",
    )
    insert(
        "tutor_turns",
        session_id=sid,
        role="assistant",
        content="先检查条件。",
        stage="teach_back",
        metadata_json={
            "branch": "guided_question",
            "raw_prompt": "do-not-expose",
            "safe": {"secret": "do-not-expose", "value": 2},
        },
    )
    run = insert(
        "agent_runs",
        session_id=sid,
        agent_name="mindtrace_tutor",
        status="completed",
        result={
            "branch": "guided_question",
            "next_goal": "检查条件",
            "observation": {
                "api_key": "do-not-expose",
                "api_Key": "do-not-expose",
                "visible": True,
            },
            "plan": {"credential": "do-not-expose", "step": "对照条件"},
            "verification": [{"chain_of_thought": "do-not-expose", "ok": True}],
        },
    )
    insert(
        "agent_tool_calls",
        agent_run_id=run,
        tool_name="knowledge_search",
        input_json={
            "authorization": "do-not-expose",
            "nested": [{"password": "do-not-expose", "value": "ok"}],
        },
        output_json={"value": "known", "reasoning_content": "do-not-expose"},
    )
    state = request(endpoint, "GET", "/api/v1/system/providers")
    voice = request(endpoint, "GET", "/api/v1/system/voice")
    health = request(endpoint, "GET", "/api/v1/system/health")
    assert health["status"] == "healthy" and health["database"] == "mysql"
    assert health["ai"] == state["last_status"] and health["image_recognition"] == bool(
        state["vision_entries"]
    )
    assert state["logical_model"] == "Qwen" and "api_key" not in state
    assert (
        voice["stt_model"] == "faster-whisper-small"
        and voice["tts_model"] == "edge-tts"
    )
    for path in [
        "/api/v1/admin/workbench",
        "/api/v1/admin/students/" + owner,
        "/api/v1/admin/sessions/" + sid,
    ]:
        request(endpoint, "GET", path, expected=401)
        request(endpoint, "GET", path, token=token, expected=403)
        request(endpoint, "GET", path, token=other, expected=403)
    request(
        endpoint,
        "GET",
        "/api/v1/admin/students/missing",
        token=admin_token,
        expected=404,
    )
    request(
        endpoint,
        "GET",
        "/api/v1/admin/sessions/missing",
        token=admin_token,
        expected=404,
    )

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app.services.admin_workbench import (
        get_admin_session,
        get_admin_student,
        get_admin_workbench,
    )
    from sqlalchemy import URL
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    async def reference():
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
            async with AsyncSession(engine) as db:
                return (
                    await get_admin_student(db, owner),
                    await get_admin_session(db, sid),
                    await get_admin_workbench(db, state, voice),
                )
        finally:
            await engine.dispose()

    expected_student, expected_session, expected_workbench = asyncio.run(reference())
    actual_student = request(
        endpoint, "GET", "/api/v1/admin/students/" + owner, token=admin_token
    )
    actual_session = request(
        endpoint, "GET", "/api/v1/admin/sessions/" + sid, token=admin_token
    )
    actual_workbench = request(
        endpoint, "GET", "/api/v1/admin/workbench", token=admin_token
    )

    def canonical(value):
        if isinstance(value, dict):
            return {k: canonical(v) for k, v in value.items() if k != "generated_at"}
        if isinstance(value, list):
            return sorted(
                [canonical(v) for v in value],
                key=lambda item: json.dumps(item, sort_keys=True),
            )
        return value

    assert canonical(actual_student) == canonical(expected_student), (
        actual_student,
        expected_student,
    )
    assert canonical(actual_session) == canonical(expected_session), (
        actual_session,
        expected_session,
    )
    assert canonical(actual_workbench) == canonical(expected_workbench), (
        actual_workbench,
        expected_workbench,
    )
    assert "do-not-expose" not in json.dumps(actual_session)
    assert actual_session["trace"][0]["agent"] == "教学决策智能体"
    assert actual_session["trace"][0]["actions"][0]["tool"] == "知识检索"
    print(
        "Cangjie system/admin passed: real state, admin scope, original MySQL response parity, traces and sensitive-field filtering"
    )
