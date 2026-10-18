"""Run bounded, real-MySQL tutor sessions against a running local backend."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

import httpx
from app.auth import create_access_token
from app.config import settings
from app.db import SessionLocal
from app.models import TutorSession, VariantQuestion

CORRECT_MICRO_ANSWERS = {
    "understanding-1": "4",
    "understanding-2": "y",
    "understanding-3": "5",
}


async def variant_answer(session_id: str, transfer: str) -> str:
    async with SessionLocal() as db:
        session = await db.get(TutorSession, session_id)
        variant_id = (session.state or {}).get(f"{transfer}_variant_id")
        variant = await db.get(VariantQuestion, variant_id)
        if variant is None:
            raise RuntimeError(f"{transfer} variant is missing")
        return variant.answer


async def post(client: httpx.AsyncClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(path, json=payload)
    response.raise_for_status()
    return response.json()["data"]


async def answer_current(client: httpx.AsyncClient, session: dict[str, Any], answer: Any, unknown: bool = False) -> dict[str, Any]:
    return await post(client, f"/tutor/sessions/{session['id']}/activity/answer", {
        "activity_id": session["activity"]["id"], "answer": answer, "unknown": unknown,
    })


async def complete_understanding(client: httpx.AsyncClient, session: dict[str, Any], mode: str) -> dict[str, Any]:
    made_first_error = False
    while session["stage"] == "understanding" and session.get("activity"):
        activity_id = session["activity"]["id"]
        if activity_id.endswith("-confirmation"):
            session = await answer_current(client, session, "yes")
            continue
        if mode == "unknown":
            session = await answer_current(client, session, "__unknown__", True)
            continue
        if mode == "wrong_then_right" and not made_first_error:
            made_first_error = True
            session = await answer_current(client, session, "1")
            continue
        session = await answer_current(client, session, CORRECT_MICRO_ANSWERS[activity_id])
    if not session["state"].get("understanding_passed"):
        raise RuntimeError("understanding did not pass")
    return await post(client, f"/tutor/sessions/{session['id']}/advance", {"target_stage": "teach_back"})


async def refresh(client: httpx.AsyncClient, session_id: str) -> dict[str, Any]:
    response = await client.get(f"/tutor/sessions/{session_id}")
    response.raise_for_status()
    return response.json()["data"]


async def finish_from_current(client: httpx.AsyncClient, session: dict[str, Any], scenario: str) -> dict[str, Any]:
    session_id = session["id"]
    if session["stage"] == "teach_back":
        if scenario == "teach_back_twice":
            session = await answer_current(client, session, "看图")
            session = await answer_current(client, session, "还是看图")
        else:
            session = await answer_current(
                client, session,
                "我会先看正方体相对面的判断，因为相间或Z字两端折叠后相对，所以再列关系。",
            )
    if session["stage"] == "near_transfer":
        if scenario == "near_twice":
            session = await answer_current(client, session, "不正确")
            session = await answer_current(client, session, "仍然不正确")
            if session.get("activity") and "near-remediation" in session["activity"]["id"]:
                session = await answer_current(client, session, "expected")
        else:
            expected = await variant_answer(session_id, "near")
            session = await answer_current(client, session, expected)
    if session["stage"] == "far_transfer":
        expected = await variant_answer(session_id, "far")
        session = await answer_current(client, session, expected)
    return session


async def run(base_url: str, user_id: str, question_id: str) -> None:
    token = create_access_token(user_id, settings.auth_secret)
    headers = {"Authorization": f"Bearer {token}"}
    scenarios = [
        ("all_correct", "correct"),
        ("first_wrong_then_right", "wrong_then_right"),
        ("choose_unknown", "unknown"),
        ("teach_back_twice_incomplete", "correct"),
        ("near_transfer_twice_wrong", "correct"),
    ]
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=180) as client:
        for name, understanding_mode in scenarios:
            session = await post(client, "/tutor/sessions", {"question_id": question_id})
            session_id = session["id"]
            await complete_understanding(client, session, understanding_mode)
            session = await refresh(client, session_id)
            special = "teach_back_twice" if name == "teach_back_twice_incomplete" else "near_twice" if name == "near_transfer_twice_wrong" else name
            session = await finish_from_current(client, session, special)
            if session["stage"] != "finished":
                raise RuntimeError(f"{name} stopped at {session['stage']}")
            print({
                "scenario": name, "session_id": session_id, "stage": session["stage"],
                "assisted": session["assisted"],
                "transfer_insufficient": bool(session["state"].get("transfer_insufficient")),
            })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--question-id", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.base_url, args.user_id, args.question_id))


if __name__ == "__main__":
    main()
