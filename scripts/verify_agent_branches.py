#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal
from app.models import AgentRun, AgentToolCall, CognitiveUpdate, ReviewPlan, TutorTurn

BASE = "http://127.0.0.1:8000/api/v1"


def data(response: httpx.Response):
    response.raise_for_status()
    body = response.json()
    assert body["success"], body
    return body["data"]


def run_cases() -> tuple[list[dict[str, object]], list[str]]:
    client = httpx.Client(timeout=240)
    user = data(client.post(BASE + "/auth/login", json={"email": "e2e@minddimension.local", "password": "123456"}))
    headers = {"Authorization": f"Bearer {user['access_token']}"}
    questions = data(client.get(BASE + "/questions", headers=headers))
    question_id = next(item["id"] for item in questions if item["status"] in {"diagnosed", "ocr_draft", "analyzed"})
    results: list[dict[str, object]] = []
    session_ids: list[str] = []

    def start():
        session = data(client.post(BASE + "/tutor/sessions", headers=headers, json={"question_id": question_id}))
        session_ids.append(session["id"])
        return session

    for name, message, expected in (
        ("completely_unknown", "我完全不会，也不知道从哪里开始", "completely_unknown"),
        ("partial_correct", "我知道应该减3，但下一步呢", "partial_correct"),
        ("new_error", "我又觉得单位可能是新错误", "new_error"),
        ("answer_requested", "直接告诉我答案是什么", "answer_requested"),
        ("correct_but_unclear", "x=4", "correct_but_unclear"),
    ):
        session = start()
        output = data(client.post(BASE + f"/tutor/sessions/{session['id']}/turns", headers=headers, json={"message": message}))
        assert output["branch"] == expected, output
        if expected != "answer_requested":
            assert "答案是 x=4" not in output["message"]
        results.append({"case": name, "branch": output["branch"], "stage": output["stage"], "passed": True})

    session = start()
    first = data(client.post(BASE + f"/tutor/sessions/{session['id']}/turns", headers=headers, json={"message": "2x=11+3"}))
    repeated = data(client.post(BASE + f"/tutor/sessions/{session['id']}/turns", headers=headers, json={"message": "2x=11+3"}))
    assert first["branch"] == "guided_question" and repeated["branch"] == "repeated_error"
    results.append({"case": "repeated_error", "branch": repeated["branch"], "stage": repeated["stage"], "passed": True})

    for passed in (False, True):
        session = start()
        explanation = "移过去就变号" if not passed else "因为等式两边要同时做相同操作，两边减3后表现为移项变号。"
        output = data(client.post(BASE + f"/tutor/sessions/{session['id']}/teach-back", headers=headers, json={"explanation": explanation}))
        expected = "teach_back_pass" if passed else "teach_back_fail"
        assert output["branch"] == expected and output["passed"] is passed
        results.append({"case": expected, "branch": output["branch"], "stage": output["stage"], "passed": True})

    for transfer, correct in (("near", False), ("near", True), ("far", False), ("far", True)):
        session = start()
        data(client.post(BASE + f"/tutor/sessions/{session['id']}/teach-back", headers=headers, json={"explanation": "因为等式两边要同时减去同一个数，所以移项表现为变号。"}))
        variant = data(client.post(BASE + f"/tutor/sessions/{session['id']}/variant", headers=headers, json={"transfer_type": transfer}))
        answer = variant["answer"] if correct else "完全错误的答案"
        output = data(client.post(BASE + f"/variants/{variant['id']}/attempt", headers=headers, json={"answer": answer, "elapsed_seconds": 25, "hint_level": 1}))
        expected = f"{transfer}_transfer_{'pass' if correct else 'fail'}"
        assert output["branch"] == expected and output["correct"] is correct
        results.append({"case": expected, "branch": output["branch"], "stage": output["stage"], "passed": True})
    return results, session_ids


async def database_evidence(session_ids: list[str]) -> dict[str, int]:
    async with SessionLocal() as db:
        turns = await db.scalar(select(func.count()).select_from(TutorTurn).where(TutorTurn.session_id.in_(session_ids)))
        runs = await db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.session_id.in_(session_ids)))
        tools = await db.scalar(select(func.count()).select_from(AgentToolCall).join(AgentRun, AgentRun.id == AgentToolCall.agent_run_id).where(AgentRun.session_id.in_(session_ids)))
        updates = await db.scalar(select(func.count()).select_from(CognitiveUpdate))
        reviews = await db.scalar(select(func.count()).select_from(ReviewPlan))
    assert (turns or 0) >= 24
    assert (runs or 0) >= 12 and (tools or 0) >= 12
    assert (updates or 0) >= 8
    return {"tutor_turns": turns or 0, "agent_runs": runs or 0, "agent_tool_calls": tools or 0, "cognitive_updates": updates or 0, "review_plans": reviews or 0}


def main() -> int:
    results, sessions = run_cases()
    evidence = asyncio.run(database_evidence(sessions))
    report = {"passed": True, "case_count": len(results), "cases": results, "database": evidence}
    target = ROOT / "reports/verification/agent_branches.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "case_count": len(results), **evidence}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
