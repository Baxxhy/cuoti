#!/usr/bin/env python3
"""验收已启动的本地 BGE/Qdrant 推荐链；不下载模型、不调用远程 AI。"""
from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings
from app.db import SessionLocal, engine
from app.models import DatasetQuestion, DatasetSource, PracticeRecommendation

BASE = os.environ.get("ZHIWEI_API_URL", (
    os.environ.get("ZHIWEI_BACKEND_URL", f"http://127.0.0.1:{os.environ.get('ZHIWEI_BACKEND_PORT', '8000')}")
    + "/api/v1"
)).rstrip("/")
PUBLIC_FIELDS = {
    "question_id", "subject", "grade", "stem", "images", "options", "question_type",
    "knowledge_points", "recommendation", "mode", "debug",
}
PRIVATE_FIELDS = {
    "answer", "answers", "correct", "is_correct", "correct_answer", "correct_option", "correct_options",
    "expected_answer", "standard_answer", "official_answer", "reference_answer", "final_answer",
    "answer_text", "solution", "solutions", "analysis", "explanation", "explanations", "rubric",
}


class CheckFailure(RuntimeError):
    """Messages are fixed check names, never response bodies or credentials."""


def require(condition: Any, check: str) -> None:
    if not condition:
        raise CheckFailure(check)


def data(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    require(isinstance(payload, dict) and payload.get("success") is True, "api_success")
    result = payload.get("data")
    require(isinstance(result, dict), "api_data_object")
    return result


def check_public_payload(value: Any) -> None:
    if isinstance(value, dict):
        require(not (set(map(str.lower, value)) & PRIVATE_FIELDS), "no_answer_or_solution_fields")
        for item in value.values():
            check_public_payload(item)
    elif isinstance(value, list):
        for item in value:
            check_public_payload(item)


async def verify_saved_question(result: dict[str, Any], user_id: str, mistake_id: str) -> None:
    # Select public fields only; the verifier never reads official answers or solutions.
    async with SessionLocal() as db:
        saved = (await db.execute(select(
            DatasetQuestion.question_text, DatasetQuestion.subject, DatasetQuestion.grade,
            DatasetQuestion.usable_for_practice,
        ).join(DatasetSource, DatasetSource.id == DatasetQuestion.dataset_source_id).where(
            DatasetQuestion.id == result["question_id"],
        ))).one_or_none()
        require(saved is not None, "real_dataset_question")
        require(saved.question_text == result["stem"], "dataset_stem_matches")
        require(saved.subject == result["subject"] == "数学", "dataset_subject_matches")
        require(saved.grade == result["grade"], "dataset_grade_matches")
        require(saved.usable_for_practice is True, "dataset_usable_for_practice")
        trace = (await db.scalars(select(PracticeRecommendation.retrieval_trace).where(
            PracticeRecommendation.user_id == user_id,
            PracticeRecommendation.mistake_id == mistake_id,
            PracticeRecommendation.dataset_question_id == result["question_id"],
            PracticeRecommendation.mode == "reinforce",
        ))).one_or_none()
        require(trace == result["debug"], "saved_retrieval_trace_matches")


async def run(record: dict[str, Any]) -> None:
    async with httpx.AsyncClient(base_url=BASE, timeout=360) as client:
        record["stage"] = "service_preflight"
        health_response = await client.get(f"{settings.retrieval_inference_url.rstrip('/')}/health", timeout=15)
        health_response.raise_for_status()
        health = health_response.json()
        require(health.get("status") == "healthy", "bge_healthy")
        # A cold inference service can download missing weights when first called.
        # Require loaded models so this explicit smoke run cannot trigger that path.
        require(health.get("embedding_loaded") is True and health.get("reranker_loaded") is True,
                "bge_models_must_already_be_loaded_no_download")
        index_response = await client.get(
            f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}", timeout=15,
        )
        index_response.raise_for_status()
        require(index_response.json().get("result", {}).get("points_count", 0) > 0, "qdrant_index_has_points")
        record["bge_models_loaded"] = True
        record["qdrant_index_ready"] = True

        record["stage"] = "create_independent_student"
        user = data(await client.post("/auth/register", json={
            "email": f"retrieval-smoke-{uuid.uuid4().hex}@minddimension.local",
            "password": uuid.uuid4().hex, "name": "真实题库验收学生", "grade": "高一",
        }))
        client.headers["Authorization"] = f"Bearer {user['access_token']}"
        record["stage"] = "create_manual_question"
        question = data(await client.post("/questions/manual", json={
            "question_text": "已知二次函数 f(x)=x^2-4x+3，求函数最小值及取得最小值时的 x。",
            "student_answer": "最小值为3", "subject": "数学", "grade": "高一",
            "student_steps": ["x=0时f(x)=3，所以最小值为3"],
        }))
        mistake_id = str(uuid.UUID(question["id"]))
        record["source_question_id"] = mistake_id
        record["stage"] = "practice_recommend"
        print("retrieval=started (existing local models and index; no remote AI)", flush=True)
        started = time.monotonic()
        try:
            response = await client.post("/practice/recommend", json={
                "mistake_id": mistake_id, "mode": "reinforce", "debug": True, "force_new": True,
            })
        finally:
            record["elapsed_seconds"] = round(time.monotonic() - started, 2)
        record["http_status"] = response.status_code
        result = data(response)

        record["stage"] = "check_public_recommendation"
        require(set(result) <= PUBLIC_FIELDS, "only_public_recommendation_fields")
        check_public_payload(result)
        candidate_id = str(uuid.UUID(result["question_id"]))
        require(candidate_id != mistake_id, "candidate_differs_from_source")
        require(isinstance(result.get("stem"), str) and result["stem"].strip(), "nonempty_question_stem")
        require(result.get("mode") == "reinforce", "requested_practice_mode")
        trace = result.get("debug")
        require(isinstance(trace, dict), "retrieval_trace_present")
        ranks = [trace.get(key) for key in ("dense_rank", "sparse_rank")]
        require(all(rank is None or type(rank) is int and rank > 0 for rank in ranks)
                and any(rank is not None for rank in ranks), "hybrid_retrieval_ranks")
        require(type(trace.get("fusion_rank")) is int and trace["fusion_rank"] > 0, "fusion_rank")
        for key in ("reranker_score", "mode_score", "structure_similarity"):
            score = trace.get(key)
            require(type(score) in (int, float) and math.isfinite(score), "finite_retrieval_scores")
        record["stage"] = "verify_mysql_evidence"
        await verify_saved_question(result, user["id"], mistake_id)
        record.update({
            "status": "passed", "stage": "complete", "candidate_ids": [candidate_id],
            "stem_characters": len(result["stem"]), "mysql_question_and_trace_verified": True,
            "answer_fields_absent": True,
            "retrieval_trace": {key: trace[key] for key in (
                "dense_rank", "sparse_rank", "fusion_rank", "reranker_score", "mode_score", "structure_similarity",
            )},
        })


async def main() -> int:
    record: dict[str, Any] = {"status": "failed", "stage": "startup", "remote_ai_calls": 0}
    try:
        await run(record)
    except (CheckFailure, httpx.HTTPError, SQLAlchemyError, OSError, KeyError, TypeError, ValueError) as exc:
        # Exception text / HTTP bodies can contain server details. Report only safe check names.
        record["failure"] = str(exc) if isinstance(exc, CheckFailure) else type(exc).__name__
        if isinstance(exc, httpx.HTTPStatusError):
            record["http_status"] = exc.response.status_code
    finally:
        await engine.dispose()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report = ROOT / "reports" / f"retrieval-smoke-{stamp}-{uuid.uuid4().hex[:8]}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)
    print(f"report={report.relative_to(ROOT)}", flush=True)
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
