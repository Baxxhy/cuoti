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
from app.models import AgentRun, AgentToolCall, KnowledgePoint, KnowledgeRelation
from app.services.pedagogy import CORE_SUBJECTS, MIDDLE_SCHOOL_GRADES

BASE = "http://127.0.0.1:8000/api/v1"


def unpack(response: httpx.Response):
    response.raise_for_status()
    body = response.json()
    assert body["success"], body
    return body["data"]


async def database_evidence(session_id: str) -> dict[str, object]:
    async with SessionLocal() as db:
        subjects = dict((await db.execute(
            select(KnowledgePoint.subject, func.count()).group_by(KnowledgePoint.subject)
        )).all())
        relation_count = int(await db.scalar(select(func.count()).select_from(KnowledgeRelation)) or 0)
        tool = (await db.scalars(
            select(AgentToolCall).join(AgentRun, AgentRun.id == AgentToolCall.agent_run_id)
            .where(AgentRun.session_id == session_id, AgentToolCall.tool_name == "knowledge_search")
            .order_by(AgentToolCall.created_at.desc())
        )).first()
        assert set(subjects) == set(CORE_SUBJECTS), subjects
        assert all(subjects[subject] >= 18 for subject in CORE_SUBJECTS), subjects
        assert relation_count >= 62, relation_count
        assert tool is not None
        codes = tool.output_json.get("knowledge_card_codes", [])
        assert codes and tool.input_json.get("query")
        matched = int(await db.scalar(select(func.count()).select_from(KnowledgePoint).where(KnowledgePoint.code.in_(codes))) or 0)
        assert matched == len(codes)
        return {"subjects": subjects, "relations": relation_count, "agent_codes": codes,
                "agent_query_recorded": True, "matched_cards": matched}


def main() -> int:
    client = httpx.Client(timeout=60)
    user = unpack(client.post(BASE + "/auth/login", json={"email": "e2e@minddimension.local", "password": "123456"}))
    headers = {"Authorization": f"Bearer {user['access_token']}"}
    cards_by_subject = {subject: unpack(client.get(BASE + "/knowledge/cards", params={"subject": subject}, headers=headers)) for subject in CORE_SUBJECTS}
    assert all(cards_by_subject.values())
    for subject in CORE_SUBJECTS:
        for grade in MIDDLE_SCHOOL_GRADES:
            grade_cards = unpack(client.get(BASE + "/knowledge/cards", params={"subject": subject, "grade": grade}, headers=headers))
            assert len(grade_cards) >= 3, (subject, grade, len(grade_cards))
    required = {"grade", "chapter", "definition", "formulas", "prerequisites", "common_misconceptions",
                "teaching_prompts", "worked_example", "visualization_types", "related_knowledge"}
    assert all(required <= set(card["content"]) for cards in cards_by_subject.values() for card in cards)
    search = unpack(client.get(BASE + "/knowledge/cards", params={"q": "一元一次方程", "subject": "数学"}, headers=headers))
    assert any(card["code"] == "math.linear_equation" for card in search)
    detail = unpack(client.get(BASE + "/knowledge/cards/math.linear_equation", headers=headers))
    assert detail["prerequisites"] and detail["next_knowledge"]

    questions = unpack(client.get(BASE + "/questions", headers=headers))
    question = next(item for item in questions if item["status"] in {"diagnosed", "ocr_draft", "analyzed"})
    session = unpack(client.post(BASE + "/tutor/sessions", headers=headers, json={"question_id": question["id"]}))
    turn = unpack(client.post(BASE + f"/tutor/sessions/{session['id']}/turns", headers=headers,
                              json={"message": "我完全不会，也不知道需要哪些前置知识"}))
    assert "知识卡" in turn["message"]
    graph = unpack(client.get(BASE + "/analytics/cognition-graph", params={"days": 365}, headers=headers))
    assert graph["nodes"] and graph["links"], graph
    database = asyncio.run(database_evidence(session["id"]))
    report = {
        "passed": True,
        "card_counts": {subject: len(cards) for subject, cards in cards_by_subject.items()},
        "required_fields": sorted(required), "search_hit": "math.linear_equation",
        "prerequisite_count": len(detail["prerequisites"]), "next_count": len(detail["next_knowledge"]),
        "graph": {"nodes": len(graph["nodes"]), "links": len(graph["links"]), "evidence": graph["evidence_count"]},
        "database": database,
    }
    target = ROOT / "reports/verification/knowledge_base.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
