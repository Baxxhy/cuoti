#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import func, select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend")); sys.path.insert(0, str(ROOT / "scripts"))

from app.db import SessionLocal
from app.models import (
    AgentRun,
    AgentToolCall,
    Base,
    Diagnosis,
    DiagnosisEvidence,
    PaperItem,
    QuestionAsset,
    QuestionBlock,
    ReviewRecord,
    StudentStep,
    StudentWork,
    TutorTurn,
    VariantAttempt,
    VisualizationInteraction,
    VisualizationSpec,
)
from functional_flow import run_functional_case

CORE_TABLES = [name for name in Base.metadata.tables]


async def database_evidence(flow: dict[str, object]) -> dict[str, object]:
    async with SessionLocal() as db:
        counts = {table: int(await db.scalar(text(f"SELECT COUNT(*) FROM `{table}`")) or 0)
                  for table in CORE_TABLES}
        missing_writes = [name for name, count in counts.items() if count == 0]
        assert not missing_writes, missing_writes
        question_id, session_id = str(flow["question_id"]), str(flow["session_id"])
        work_ids = list(await db.scalars(select(StudentWork.id).where(StudentWork.question_id == question_id)))
        diagnosis_ids = list(await db.scalars(select(Diagnosis.id).where(Diagnosis.question_id == question_id)))
        spec_ids = list(await db.scalars(select(VisualizationSpec.id).where(VisualizationSpec.session_id == session_id)))
        scoped = {
            "assets": int(await db.scalar(select(func.count()).select_from(QuestionAsset).where(QuestionAsset.question_id == question_id)) or 0),
            "blocks": int(await db.scalar(select(func.count()).select_from(QuestionBlock).where(QuestionBlock.question_id == question_id)) or 0),
            "student_steps": int(await db.scalar(select(func.count()).select_from(StudentStep).where(StudentStep.work_id.in_(work_ids))) or 0),
            "diagnosis_evidence": int(await db.scalar(select(func.count()).select_from(DiagnosisEvidence).where(DiagnosisEvidence.diagnosis_id.in_(diagnosis_ids))) or 0),
            "tutor_turns": int(await db.scalar(select(func.count()).select_from(TutorTurn).where(TutorTurn.session_id == session_id)) or 0),
            "agent_tools": int(await db.scalar(select(func.count()).select_from(AgentToolCall).join(AgentRun, AgentRun.id == AgentToolCall.agent_run_id).where(AgentRun.session_id == session_id)) or 0),
            "variant_attempts": int(await db.scalar(select(func.count()).select_from(VariantAttempt).where(VariantAttempt.id.in_(flow["attempt_ids"]))) or 0),
            "review_records": int(await db.scalar(select(func.count()).select_from(ReviewRecord).where(ReviewRecord.id == flow["review_record_id"])) or 0),
            "paper_items": int(await db.scalar(select(func.count()).select_from(PaperItem).where(PaperItem.paper_id == flow["paper_id"])) or 0),
            "visualization_interactions": int(await db.scalar(select(func.count()).select_from(VisualizationInteraction).where(VisualizationInteraction.visualization_id.in_(spec_ids))) or 0),
        }
        assert scoped["assets"] >= 4 and scoped["blocks"] > 0 and all(
            scoped[key] > 0 for key in scoped if key not in {"assets", "blocks"})
        orphan_queries = {
            "question_assets": "SELECT COUNT(*) FROM question_assets c LEFT JOIN questions p ON p.id=c.question_id WHERE p.id IS NULL",
            "student_steps": "SELECT COUNT(*) FROM student_steps c LEFT JOIN student_works p ON p.id=c.work_id WHERE p.id IS NULL",
            "diagnosis_evidence": "SELECT COUNT(*) FROM diagnosis_evidence c LEFT JOIN diagnoses p ON p.id=c.diagnosis_id WHERE p.id IS NULL",
            "tutor_turns": "SELECT COUNT(*) FROM tutor_turns c LEFT JOIN tutor_sessions p ON p.id=c.session_id WHERE p.id IS NULL",
            "agent_tool_calls": "SELECT COUNT(*) FROM agent_tool_calls c LEFT JOIN agent_runs p ON p.id=c.agent_run_id WHERE p.id IS NULL",
            "paper_items": "SELECT COUNT(*) FROM paper_items c LEFT JOIN papers p ON p.id=c.paper_id WHERE p.id IS NULL",
            "variant_attempts": "SELECT COUNT(*) FROM variant_attempts c LEFT JOIN variant_questions p ON p.id=c.variant_id WHERE p.id IS NULL",
        }
        orphans = {name: int(await db.scalar(text(query)) or 0) for name, query in orphan_queries.items()}
        assert not any(orphans.values()), orphans
        return {"table_count": len(counts), "counts": counts, "missing_writes": missing_writes,
                "scoped_flow": scoped, "orphans": orphans}


def main() -> int:
    image_manifest = json.loads((ROOT / "data/functional_validation/images.json").read_text(encoding="utf-8"))
    case = json.loads((ROOT / "data/functional_validation/e2e_cases.json").read_text(encoding="utf-8"))[0]
    image = next(item for item in image_manifest if item["case_id"] == case["image_case_id"])
    client = httpx.Client(timeout=360)
    flow = run_functional_case(client, case, image, f"db-check-{int(time.time())}@minddimension.local")
    evidence = asyncio.run(database_evidence(flow))
    report = {"passed": True, "flow": flow, "database": evidence}
    target = ROOT / "reports/verification/database_usage.json"; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "table_count": evidence["table_count"],
                      "missing_writes": evidence["missing_writes"], "scoped_flow": evidence["scoped_flow"],
                      "orphan_total": sum(evidence["orphans"].values())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
