#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import exists, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal
from app.models import (
    DatasetQuestion,
    KnowledgePoint,
    QuestionKnowledgeLink,
    utcnow,
    uuid4,
)
from app.services.question_mapping import map_question


async def run(batch_size: int, rebuild: bool) -> tuple[int, int]:
    mapped = links = 0
    async with SessionLocal() as db:
        if rebuild:
            await db.execute(QuestionKnowledgeLink.__table__.delete())
            await db.commit()
        cards_by_subject: dict[str, list[KnowledgePoint]] = {}
        for card in await db.scalars(select(KnowledgePoint)):
            cards_by_subject.setdefault(card.subject, []).append(card)
        last_id = ""
        while True:
            statement = select(DatasetQuestion).where(DatasetQuestion.id > last_id)
            if not rebuild:
                statement = statement.where(~exists().where(
                    QuestionKnowledgeLink.dataset_question_id == DatasetQuestion.id,
                    QuestionKnowledgeLink.role == "primary",
                ))
            questions = list(await db.scalars(statement.order_by(DatasetQuestion.id).limit(batch_size)))
            if not questions:
                break
            values = []
            now = utcnow()
            for question in questions:
                matches = map_question(question, cards_by_subject.get(question.subject, []))
                mapped += int(bool(matches))
                for match in matches:
                    values.append({
                        "id": uuid4(), "dataset_question_id": question.id,
                        "knowledge_point_id": match.knowledge_id, "role": match.role,
                        "confidence": match.confidence, "mapping_method": match.method,
                        "created_at": now, "updated_at": now,
                    })
            if values:
                statement = mysql_insert(QuestionKnowledgeLink.__table__).values(values)
                await db.execute(statement.on_duplicate_key_update(
                    role=statement.inserted.role, confidence=statement.inserted.confidence,
                    mapping_method=statement.inserted.mapping_method, updated_at=statement.inserted.updated_at,
                ))
                links += len(values)
            last_id = questions[-1].id
            await db.commit()
            print(f"checkpoint={last_id} mapped={mapped} links={links}")
    return mapped, links


async def main() -> None:
    parser = argparse.ArgumentParser(description="离线映射公开题库到统一知识卡")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    mapped, links = await run(args.batch_size, args.rebuild)
    print(f"mapped={mapped} links={links}")


if __name__ == "__main__":
    asyncio.run(main())
