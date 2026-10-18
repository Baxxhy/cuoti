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
from app.models import (
    AgentRun,
    AgentToolCall,
    VisualizationInteraction,
    VisualizationSpec,
)
from app.schemas import VisualizationPayload
from app.services.visualizations import VISUALIZATION_SPECS

BASE = "http://127.0.0.1:8000/api/v1"


def unpack(response: httpx.Response):
    response.raise_for_status()
    body = response.json()
    assert body["success"], body
    return body["data"]


async def database_evidence(session_id: str) -> dict[str, int]:
    async with SessionLocal() as db:
        specs = int(await db.scalar(select(func.count()).select_from(VisualizationSpec).where(
            VisualizationSpec.session_id == session_id)) or 0)
        interactions = int(await db.scalar(select(func.count()).select_from(VisualizationInteraction).join(
            VisualizationSpec, VisualizationSpec.id == VisualizationInteraction.visualization_id
        ).where(VisualizationSpec.session_id == session_id)) or 0)
        tool_calls = int(await db.scalar(select(func.count()).select_from(AgentToolCall).join(
            AgentRun, AgentRun.id == AgentToolCall.agent_run_id
        ).where(AgentRun.session_id == session_id, AgentToolCall.tool_name == "observe_visualization")) or 0)
        return {"specs": specs, "interactions": interactions, "agent_tool_calls": tool_calls}


def main() -> int:
    expected = set(VISUALIZATION_SPECS)
    assert len(expected) == 16
    validated = {name: VisualizationPayload.model_validate(value).model_dump() for name, value in VISUALIZATION_SPECS.items()}
    client = httpx.Client(timeout=60)
    user = unpack(client.post(BASE + "/auth/login", json={"email": "e2e@minddimension.local", "password": "123456"}))
    headers = {"Authorization": f"Bearer {user['access_token']}"}
    catalog = unpack(client.get(BASE + "/visualizations/types", headers=headers))
    assert {item["type"] for item in catalog} == expected
    questions = unpack(client.get(BASE + "/questions", headers=headers))
    session = unpack(client.post(BASE + "/tutor/sessions", headers=headers, json={"question_id": questions[0]["id"]}))
    ids = []
    for kind, spec in validated.items():
        values = {value["name"]: value["value"] for value in spec["interactive_variables"]}
        item = unpack(client.post(BASE + f"/tutor/sessions/{session['id']}/visualization", headers=headers,
                                  json={"type": kind, "values": values, "observation": spec["expected_observation"]}))
        ids.append(item["id"])
        stored = unpack(client.get(BASE + f"/visualizations/{item['id']}", headers=headers))
        assert stored["type"] == kind and len(stored["interactions"]) == 1
        assert stored["spec"]["schema_version"] == "1.0"
    database = asyncio.run(database_evidence(session["id"]))
    assert database == {"specs": 16, "interactions": 16, "agent_tool_calls": 16}, database
    report = {"passed": True, "type_count": 16, "types": sorted(expected), "schema_validated": 16,
              "created_ids": len(ids), "database": database, "frontend_policy": "Zod whitelist + Canvas; no model code execution"}
    target = ROOT / "reports/verification/visualizations.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
