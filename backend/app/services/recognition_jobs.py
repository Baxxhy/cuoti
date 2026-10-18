"""Find active recognition work and serialize changes to a question's crop."""

from math import isclose

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProcessingJob, Question, QuestionAsset

RECOGNITION_KINDS = ("ingest", "crop", "ocr", "reprocess")
ACTIVE_STATUSES = ("pending", "running")


async def active_recognition_job(db: AsyncSession, question_id: str) -> ProcessingJob | None:
    statement = (
        select(ProcessingJob)
        .where(
            ProcessingJob.question_id == question_id,
            ProcessingJob.kind.in_(RECOGNITION_KINDS),
            ProcessingJob.status.in_(ACTIVE_STATUSES),
        )
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    return (await db.scalars(statement)).first()


async def lock_recognition_question(db: AsyncSession, question_id: str) -> Question:
    # Recognition controllers have only read preflight data at this point.
    # End that snapshot before locking the parent; the following normal reads
    # see competing starts without gap-locking the empty job range in MySQL.
    await db.rollback()
    question = await db.get(Question, question_id, with_for_update=True, populate_existing=True)
    if question is None or question.status == "archived":
        raise HTTPException(404, "题目不存在或已归档")
    return question


def crop_box(asset: QuestionAsset | None) -> list[float] | None:
    # Asset bounds use normalized [left, top, right, bottom]; the picker uses x/y/w/h.
    if asset is None or not isinstance(asset.bbox, list) or len(asset.bbox) != 4:
        return None
    try:
        x, y, right, bottom = (float(value) for value in asset.bbox)
    except (ValueError, TypeError):
        return None
    if not (0 <= x < right <= 1 and 0 <= y < bottom <= 1):
        return None
    return [x, y, right - x, bottom - y]


def same_crop(asset: QuestionAsset | None, requested: list[float]) -> bool:
    stored = crop_box(asset)
    return stored is not None and all(
        isclose(a, b, abs_tol=1e-6) for a, b in zip(stored, requested, strict=True)
    )
