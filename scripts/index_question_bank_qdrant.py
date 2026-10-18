#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from qdrant_client import QdrantClient, models
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings
from app.db import SessionLocal
from app.models import (
    DatasetQuestion,
    DatasetSource,
    KnowledgePoint,
    QuestionKnowledgeLink,
)
from app.services.practice_retrieval import (
    bge_runtime,
    normalized_grade,
    retrieval_text,
)


def ensure_collection(client: QdrantClient, recreate: bool) -> None:
    if recreate and client.collection_exists(settings.qdrant_collection):
        client.delete_collection(settings.qdrant_collection)
    if client.collection_exists(settings.qdrant_collection):
        return
    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config={
            "dense": models.VectorParams(
                size=settings.retrieval_embedding_dimension, distance=models.Distance.COSINE, on_disk=True,
            ),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(index=models.SparseIndexParams(on_disk=True)),
        },
    )
    for field, schema in (
        ("question_id", models.PayloadSchemaType.KEYWORD), ("subject", models.PayloadSchemaType.KEYWORD),
        ("grade", models.PayloadSchemaType.KEYWORD), ("grade_band", models.PayloadSchemaType.KEYWORD),
        ("knowledge_ids", models.PayloadSchemaType.KEYWORD),
        ("question_type", models.PayloadSchemaType.KEYWORD),
        ("quality_status", models.PayloadSchemaType.KEYWORD),
        ("usable_for_practice", models.PayloadSchemaType.BOOL),
    ):
        client.create_payload_index(settings.qdrant_collection, field, schema, wait=True)


async def index(batch_size: int, recreate: bool, limit: int | None) -> tuple[int, int]:
    client = QdrantClient(url=settings.qdrant_url, timeout=120)
    ensure_collection(client, recreate)
    indexed = skipped = 0
    async with SessionLocal() as db:
        sources = {item.id: item.key for item in await db.scalars(select(DatasetSource))}
        last_id = ""
        while limit is None or indexed < limit:
            page_size = min(batch_size, limit - indexed) if limit is not None else batch_size
            questions = list(await db.scalars(
                select(DatasetQuestion).where(
                    DatasetQuestion.id > last_id, DatasetQuestion.usable_for_practice.is_(True),
                ).order_by(DatasetQuestion.id).limit(page_size)
            ))
            if not questions:
                break
            last_id = questions[-1].id
            existing = {str(item.id) for item in client.retrieve(
                settings.qdrant_collection, [item.id for item in questions], with_payload=False,
            )}
            pending = [item for item in questions if item.id not in existing]
            skipped += len(questions) - len(pending)
            if not pending:
                print(f"checkpoint={last_id} indexed={indexed} skipped={skipped}")
                continue
            ids = [item.id for item in pending]
            rows = (await db.execute(
                select(QuestionKnowledgeLink.dataset_question_id, QuestionKnowledgeLink.role,
                       KnowledgePoint.id, KnowledgePoint.name)
                .join(KnowledgePoint, KnowledgePoint.id == QuestionKnowledgeLink.knowledge_point_id)
                .where(QuestionKnowledgeLink.dataset_question_id.in_(ids))
            )).all()
            links: dict[str, list[dict[str, str]]] = {}
            for question_id, role, knowledge_id, name in rows:
                links.setdefault(question_id, []).append({"id": knowledge_id, "name": name, "role": role})
            texts = [retrieval_text(item, [card["name"] for card in links.get(item.id, [])]) for item in pending]
            dense, sparse = bge_runtime.embed(texts)
            points = []
            for question, dense_vector, sparse_weights in zip(pending, dense, sparse, strict=True):
                knowledge_ids = [card["id"] for card in links.get(question.id, [])]
                ordered = sorted(sparse_weights.items())
                points.append(models.PointStruct(
                    id=question.id,
                    vector={
                        "dense": dense_vector,
                        "sparse": models.SparseVector(
                            indices=[item[0] for item in ordered], values=[item[1] for item in ordered],
                        ),
                    },
                    payload={
                        "question_id": question.id, "source_dataset": sources[question.dataset_source_id],
                        "subject": question.subject,
                        "grade": normalized_grade(question.grade, question.grade_band),
                        "grade_band": question.grade_band, "knowledge_ids": knowledge_ids,
                        "question_type": question.question_type, "difficulty": question.difficulty,
                        "has_answer": question.has_answer, "quality_status": question.quality_status,
                        "usable_for_practice": question.usable_for_practice,
                    },
                ))
            client.upsert(settings.qdrant_collection, points, wait=True)
            indexed += len(points)
            print(f"checkpoint={last_id} indexed={indexed} skipped={skipped}")
    return indexed, skipped


async def main() -> None:
    parser = argparse.ArgumentParser(description="使用 BGE-M3 建立公开题库 Qdrant 混合检索索引")
    parser.add_argument("--batch-size", type=int, default=settings.retrieval_batch_size)
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    indexed, skipped = await index(args.batch_size, args.recreate, args.limit)
    count = QdrantClient(url=settings.qdrant_url).count(
        settings.qdrant_collection, exact=True,
    ).count
    print(f"indexed={indexed} skipped={skipped} qdrant_count={count}")


if __name__ == "__main__":
    asyncio.run(main())
