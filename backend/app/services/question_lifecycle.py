"""Invalidate computed results when the source question or work changes."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DatasetPracticeAttempt,
    Diagnosis,
    DiagnosisEvidence,
    PracticeRecommendation,
    ProblemAnalysis,
    ProcessingJob,
    Question,
    ReferenceStep,
    ReviewPlan,
    ReviewRecord,
    StudentWork,
    TutorSession,
    UserQuestionKnowledgeLink,
)


def question_source_fingerprint(question: Question, student_work_ids: tuple[str, ...] = ()) -> str:
    fields = (
        "question_text",
        "student_answer",
        "subject",
        "grade",
        "title",
        "formulas",
        "options",
        "question_type",
        "knowledge_points",
    )
    content = {field: getattr(question, field) for field in fields}
    content["student_work_revisions"] = sorted(student_work_ids)
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


async def learning_source_fingerprint(
    db: AsyncSession, question: Question, *, current_read: bool = False
) -> str:
    statement = select(StudentWork).where(StudentWork.question_id == question.id)
    if current_read:
        statement = statement.with_for_update()
    works = await db.scalars(statement)
    return question_source_fingerprint(question, tuple(work.id for work in works))


async def recover_interrupted_recognition(db: AsyncSession) -> int:
    """Recover jobs left by the previous local, single-worker process."""
    jobs = list(
        await db.scalars(
            select(ProcessingJob).where(
                ProcessingJob.status.in_(("pending", "running")),
                ProcessingJob.kind.in_(("ingest", "crop", "ocr", "reprocess")),
            )
        )
    )
    for job in jobs:
        job.status = "failed"
        job.error = "识别任务因服务重启中断，请重新识别或重试"
        question = await db.get(Question, job.question_id)
        if question is not None and question.status in {"processing", "awaiting_crop", "pending"}:
            question.status = "partial"
    return len(jobs)


async def recognition_question_for_write(db: AsyncSession, job: ProcessingJob) -> Question | None:
    question = await db.get(Question, job.question_id, with_for_update=True, populate_existing=True)
    if question is None or question.status == "archived":
        job.status = "cancelled"
        job.error = "题目已归档，识别任务已取消"
        await db.commit()
        return None
    return question


async def invalidate_question_learning(db: AsyncSession, question: Question) -> None:
    # Evidence points at both reference and student steps. Remove computed evidence
    # first; retain original uploads, student work, tutor turns and past review records.
    diagnosis_ids = select(Diagnosis.id).where(Diagnosis.question_id == question.id)
    analysis_ids = select(ProblemAnalysis.id).where(ProblemAnalysis.question_id == question.id)
    await db.execute(delete(DiagnosisEvidence).where(DiagnosisEvidence.diagnosis_id.in_(diagnosis_ids)))
    await db.execute(delete(Diagnosis).where(Diagnosis.question_id == question.id))
    await db.execute(delete(ReferenceStep).where(ReferenceStep.analysis_id.in_(analysis_ids)))
    await db.execute(delete(ProblemAnalysis).where(ProblemAnalysis.question_id == question.id))
    await db.execute(
        delete(UserQuestionKnowledgeLink).where(UserQuestionKnowledgeLink.question_id == question.id)
    )
    # Recommendations are a cache, with no dependent foreign keys. Attempt rows
    # remain as history and are marked below as belonging to the previous version.
    await db.execute(delete(PracticeRecommendation).where(PracticeRecommendation.mistake_id == question.id))
    for session in await db.scalars(select(TutorSession).where(TutorSession.question_id == question.id)):
        session.state = {**(session.state or {}), "question_changed": True}
    for plan in await db.scalars(
        select(ReviewPlan).where(
            ReviewPlan.question_id == question.id,
            ReviewPlan.status == "pending",
        )
    ):
        plan.status = "cancelled"
    for attempt in await db.scalars(
        select(DatasetPracticeAttempt).where(
            DatasetPracticeAttempt.mistake_id == question.id,
        )
    ):
        attempt.grading_details = {**(attempt.grading_details or {}), "question_changed": True}
    for record in await db.scalars(
        select(ReviewRecord)
        .join(ReviewPlan, ReviewRecord.plan_id == ReviewPlan.id)
        .where(
            ReviewPlan.question_id == question.id,
        )
    ):
        record.grading_details = {**(record.grading_details or {}), "question_changed": True}
    question.status = "confirmed" if question.confirmed else "needs_confirmation"
