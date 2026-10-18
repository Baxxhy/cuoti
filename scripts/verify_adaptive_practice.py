#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from qdrant_client import QdrantClient
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings
from app.db import SessionLocal
from app.models import DatasetQuestion, DatasetSource, QuestionKnowledgeLink
from app.services.practice_retrieval import (
    hybrid_ids,
    load_candidates,
    rerank_candidates,
)

INTENTS = {
    "数学": ("高一", "二次函数参数讨论，分类讨论时遗漏边界条件，检查临界值和等号", "参数范围题"),
    "物理": ("高一", "受力分析，先确定研究对象，检查重力支持力摩擦力", "综合题"),
    "化学": ("高一", "离子方程式，可拆物质判断，难溶物不能拆成离子", "综合题"),
    "英语": ("高一", "定语从句，关系代词选择和先行词判断", "选择题"),
}

RELEVANCE_TERMS = {
    "数学": ("二次函数", "参数", "取值范围"),
    "物理": ("受力", "摩擦", "斜面"),
    "化学": ("离子方程式", "离子反应", "可拆"),
}


async def retrieve_samples(db, subject: str, mode: str, limit: int = 5) -> list[dict]:
    grade, query, original_type = INTENTS[subject]
    fused, dense_ranks, sparse_ranks = await hybrid_ids(query, subject, grade, "高中")
    candidates = await load_candidates(db, fused, dense_ranks, sparse_ranks)
    ranked = await rerank_candidates(query, query, original_type, mode, candidates)
    rows = []
    for item in ranked[:limit]:
        rows.append({
            "question_id": item.question.id,
            "source_dataset": item.source_dataset,
            "subject": item.question.subject,
            "grade": item.question.grade,
            "question_type": item.question.question_type,
            "stem": item.question.question_text[:240],
            "has_official_answer": item.question.has_answer,
            "auto_grade": item.question.usable_for_auto_grade,
            "knowledge_points": [point["name"] for point in item.knowledge_points],
            "dense_rank": item.dense_rank,
            "sparse_rank": item.sparse_rank,
            "fusion_rank": item.fusion_rank,
            "reranker_score": round(item.reranker_score, 5),
            "structure_similarity": round(item.structure_similarity, 5),
            "mode_score": round(item.mode_score, 5),
        })
    return rows


async def build_report() -> dict:
    async with SessionLocal() as db:
        total = await db.scalar(select(func.count()).select_from(DatasetQuestion)) or 0
        usable = await db.scalar(select(func.count()).select_from(DatasetQuestion).where(
            DatasetQuestion.usable_for_practice.is_(True))) or 0
        auto_grade = await db.scalar(select(func.count()).select_from(DatasetQuestion).where(
            DatasetQuestion.usable_for_auto_grade.is_(True))) or 0
        has_image = await db.scalar(select(func.count()).select_from(DatasetQuestion).where(
            func.json_length(DatasetQuestion.image_paths) > 0)) or 0
        isolated = await db.scalar(select(func.count()).select_from(DatasetQuestion).where(
            DatasetQuestion.has_answer.is_(False))) or 0
        mapped = await db.scalar(select(func.count(func.distinct(
            QuestionKnowledgeLink.dataset_question_id)))) or 0
        subject_rows = (await db.execute(select(DatasetQuestion.subject, func.count()).group_by(
            DatasetQuestion.subject))).all()
        grade_rows = (await db.execute(select(DatasetQuestion.grade, func.count()).group_by(
            DatasetQuestion.grade))).all()
        source_rows = (await db.execute(
            select(DatasetSource.key, func.count(DatasetQuestion.id))
            .join(DatasetQuestion, DatasetQuestion.dataset_source_id == DatasetSource.id)
            .group_by(DatasetSource.key)
        )).all()

        samples = {
            "reinforce": await retrieve_samples(db, "数学", "reinforce", 5),
            "variation": await retrieve_samples(db, "数学", "variation", 5),
        }
        subject_checks = {}
        for subject in ("数学", "物理", "化学"):
            rows = await retrieve_samples(db, subject, "reinforce", 1)
            direct_relevance = bool(rows) and any(
                term in rows[0]["stem"] for term in RELEVANCE_TERMS[subject]
            )
            subject_checks[subject] = {
                "status": (
                    "passed" if rows and rows[0]["subject"] == subject
                    and rows[0]["auto_grade"] and direct_relevance
                    else "limited_coverage" if rows and rows[0]["subject"] == subject
                    and rows[0]["auto_grade"] else "failed"
                ),
                "direct_target_relevance": direct_relevance,
                "sample": rows[0] if rows else None,
            }
            if rows and not direct_relevance:
                subject_checks[subject]["reason"] = (
                    f"现有三套数据能返回{subject}可判分题，但没有命中该指定细分知识点的直接题面证据。"
                )
        english_count = dict(subject_rows).get("英语", 0)
        subject_checks["英语"] = {
            "status": "not_testable",
            "reason": "CMM-Math、M3KE、CMMU 当前导入数据中没有英语题；按要求未新增数据、未伪造答案。",
            "dataset_count": english_count,
        }

    qdrant_count = QdrantClient(url=settings.qdrant_url).count(
        settings.qdrant_collection, exact=True).count
    assertions = {
        "mysql_total_is_20839": total == 20839,
        "qdrant_matches_usable": qdrant_count == usable,
        "all_questions_mapped": mapped == total,
        "math_never_returns_english": all(row["subject"] == "数学" for rows in samples.values() for row in rows),
        "all_samples_have_official_answers": all(
            row["has_official_answer"] and row["auto_grade"] for rows in samples.values() for row in rows),
        "high_school_query_has_no_primary_school": all(
            "小学" not in row["grade"] for rows in samples.values() for row in rows),
        "modes_have_different_first_choice": (
            samples["reinforce"][0]["question_id"] != samples["variation"][0]["question_id"]
        ),
        "modes_are_not_top1_top2_aliases": len({
            row["question_id"] for row in samples["reinforce"]
        } ^ {
            row["question_id"] for row in samples["variation"]
        }) >= 2,
    }
    return {
        "generated_at": __import__("datetime").datetime.now().astimezone().isoformat(),
        "models": {
            "embedding": settings.retrieval_embedding_model,
            "dimension": settings.retrieval_embedding_dimension,
            "sparse": "BGE-M3 lexical weights",
            "reranker": settings.retrieval_reranker_model,
            "fusion": "Qdrant RRF",
        },
        "counts": {
            "total": total, "usable_for_practice": usable, "usable_for_auto_grade": auto_grade,
            "has_image": has_image, "no_answer_isolated": isolated,
            "mapped_questions": mapped, "mapping_coverage": round(mapped / total, 6) if total else 0,
            "qdrant_indexed": qdrant_count,
        },
        "by_subject": dict(sorted(subject_rows)),
        "by_grade": dict(sorted(grade_rows)),
        "by_source": dict(sorted(source_rows)),
        "subject_checks": subject_checks,
        "samples": samples,
        "assertions": assertions,
        "coverage_complete": all(item["status"] == "passed" for item in subject_checks.values()),
        "passed": all(assertions.values()) and all(
            item["status"] != "failed" for item in subject_checks.values()),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="验证真实题库自适应检索并生成报告")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/adaptive_practice_verification.json")
    args = parser.parse_args()
    report = await build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "passed": report["passed"],
                      "counts": report["counts"], "assertions": report["assertions"]},
                     ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
