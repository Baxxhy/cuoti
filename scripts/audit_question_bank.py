#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal
from app.models import DatasetQuestion, DatasetSource
from app.services.question_quality import quality_flags


async def audit(batch_size: int) -> dict:
    counters = {
        "subject": Counter(), "grade": Counter(), "question_type": Counter(), "source_dataset": Counter(),
        "quality_status": Counter(), "no_answer_by_source_split": Counter(),
    }
    totals = Counter()
    async with SessionLocal() as db:
        sources = {item.id: item.key for item in await db.scalars(select(DatasetSource))}
        last_id = ""
        while True:
            rows = list(await db.scalars(
                select(DatasetQuestion).where(DatasetQuestion.id > last_id)
                .order_by(DatasetQuestion.id).limit(batch_size)
            ))
            if not rows:
                break
            for question in rows:
                flags = quality_flags(question, ROOT)
                await db.execute(update(DatasetQuestion).where(DatasetQuestion.id == question.id).values(
                    **{key: flags[key] for key in (
                        "has_answer", "has_solution", "answer_verified", "quality_status",
                        "usable_for_practice", "usable_for_auto_grade",
                    )}
                ))
                totals["total"] += 1
                totals["has_answer"] += int(flags["has_answer"])
                totals["has_solution"] += int(flags["has_solution"])
                totals["has_image"] += int(bool(question.image_paths))
                totals["image_missing"] += flags["image_missing"]
                totals["answer_verified"] += int(flags["answer_verified"])
                totals["usable_for_practice"] += int(flags["usable_for_practice"])
                totals["usable_for_auto_grade"] += int(flags["usable_for_auto_grade"])
                totals["no_answer_isolated"] += int(flags["quality_status"] == "no_answer")
                counters["subject"][question.subject] += 1
                counters["grade"][question.grade] += 1
                counters["question_type"][question.question_type] += 1
                counters["source_dataset"][sources[question.dataset_source_id]] += 1
                counters["quality_status"][flags["quality_status"]] += 1
                if flags["quality_status"] == "no_answer":
                    counters["no_answer_by_source_split"][
                        f"{sources[question.dataset_source_id]}:{question.split or 'unspecified'}"
                    ] += 1
            last_id = rows[-1].id
            await db.commit()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **dict(totals),
        **{key: dict(value.most_common()) for key, value in counters.items()},
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="审计公开题库质量并更新练习可用状态")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/question_bank_quality_audit.json")
    args = parser.parse_args()
    report = await audit(args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
