from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.media import sign_media_url
from app.models import (
    AssignmentAttempt,
    AssignmentStudent,
    CognitiveUpdate,
    Diagnosis,
    MasteryState,
    MisconceptionState,
    OCRRun,
    ProblemAnalysis,
    Question,
    QuestionAsset,
    QuestionAssignment,
    ReferenceStep,
    ReviewPlan,
    TeacherAuditLog,
    TeacherClass,
    TeacherClassStudent,
    TeacherQuestion,
    TeacherReviewResult,
    TeacherReviewTask,
    User,
)
from app.providers.api_pool import ApiPoolProvider
from app.services.access_control import authenticated_account
from app.services.answer_handwriting import validate_answer_handwriting
from app.services.cognition import cognition_target, update_cognition
from app.services.grading import CONFIRMED_CORRECT, CONFIRMED_INCORRECT, REVIEW_REQUIRED, grade_answer
from app.services.timestamps import iso_timestamp, parse_timestamp


def _row(row: Any) -> dict[str, Any]:
    result = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    return {
        key: iso_timestamp(value) if isinstance(value, datetime) else value for key, value in result.items()
    }


async def _account(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await authenticated_account(authorization, db)


async def _teacher(user: User = Depends(_account)) -> User:
    if user.role != "teacher":
        raise HTTPException(403, "当前账号不是教师")
    return user


async def _managed_class(db: AsyncSession, teacher_id: str, class_id: str) -> TeacherClass:
    classroom = await db.get(TeacherClass, class_id)
    if classroom is None or classroom.teacher_id != teacher_id:
        raise HTTPException(404, "班级不存在或无权访问")
    return classroom


async def _managed_student(db: AsyncSession, teacher_id: str, class_id: str, student_id: str) -> User:
    await _managed_class(db, teacher_id, class_id)
    link = await db.scalar(
        select(TeacherClassStudent.id).where(
            TeacherClassStudent.class_id == class_id,
            TeacherClassStudent.student_id == student_id,
        )
    )
    student = await db.get(User, student_id)
    if not link or student is None or student.role != "student":
        raise HTTPException(404, "学生不在该班级")
    return student


def _audit(
    db: AsyncSession,
    teacher_id: str,
    action: str,
    target_type: str,
    target_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
    reason: str,
) -> None:
    db.add(
        TeacherAuditLog(
            teacher_id=teacher_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_json=before,
            after_json=after,
            reason=reason,
        )
    )


def _review_reasons(grading: dict[str, Any], ocr_confidence: float | None, incomplete: bool) -> list[str]:
    reasons: list[str] = []
    if grading.get("verdict") in {"probably_correct", "review_required"}:
        reasons.append(str(grading["verdict"]))
    if grading.get("conflict"):
        reasons.append("rule_llm_conflict")
    if ocr_confidence is not None and ocr_confidence < 0.65:
        reasons.append("low_ocr_confidence")
    if incomplete:
        reasons.append("incomplete_reference")
    return reasons


async def _question_target(db: AsyncSession, question: Question) -> tuple[str, str, str, str]:
    analysis = await db.scalar(select(ProblemAnalysis).where(ProblemAnalysis.question_id == question.id))
    diagnosis = await db.scalar(
        select(Diagnosis)
        .where(
            Diagnosis.question_id == question.id,
        )
        .order_by(Diagnosis.created_at.desc())
    )
    target = cognition_target(
        subject=question.subject,
        question_type=question.question_type,
        title=question.title,
        question_knowledge_points=question.knowledge_points,
        analysis_knowledge_points=analysis.knowledge_points if analysis else None,
        diagnosis_error_type=diagnosis.error_type if diagnosis else None,
        diagnosis_root_misconception=diagnosis.root_misconception if diagnosis else None,
    )
    return target.subject, target.knowledge_point, target.misconception_code, target.misconception_label


async def _apply_learning(
    db: AsyncSession,
    student_id: str,
    question: Question,
    correct: bool,
    source_id: str,
) -> dict[str, Any]:
    subject, point, error_code, error_label = await _question_target(db, question)
    before_mastery = await db.scalar(
        select(MasteryState)
        .where(
            MasteryState.user_id == student_id,
            MasteryState.subject == subject,
            MasteryState.knowledge_point == point,
        )
        .order_by(MasteryState.updated_at.desc())
    )
    before_error = await db.scalar(
        select(MisconceptionState)
        .where(
            MisconceptionState.user_id == student_id,
            MisconceptionState.subject == subject,
            MisconceptionState.code == error_code,
        )
        .order_by(MisconceptionState.updated_at.desc())
    )
    snapshot = {
        "mastery_before": _row(before_mastery) if before_mastery else None,
        "misconception_before": _row(before_error) if before_error else None,
    }
    mastery, misconception = await update_cognition(
        db,
        student_id,
        question.id,
        {
            "near_transfer": correct,
            "hint_level": 0,
            "strategy": "teacher_review",
            "teacher_review_id": source_id,
        },
        subject=subject,
        knowledge_point=point,
        misconception_code=error_code,
        misconception_label=error_label,
    )
    snapshot.update({"mastery_after": _row(mastery), "misconception_after": _row(misconception)})
    return snapshot


async def _assignment_review_context(
    db: AsyncSession,
    task: TeacherReviewTask,
) -> tuple[AssignmentAttempt, AssignmentStudent, QuestionAssignment] | None:
    attempt = await db.get(AssignmentAttempt, task.source_id)
    if attempt is None or attempt.student_id != task.student_id or attempt.question_id != task.question_id:
        return None
    link = await db.get(AssignmentStudent, attempt.assignment_student_id, with_for_update=True)
    assignment = await db.get(QuestionAssignment, link.assignment_id) if link else None
    if link is None or assignment is None:
        return None
    return attempt, link, assignment


def _sync_assignment_review(attempt: AssignmentAttempt, link: AssignmentStudent, conclusion: str) -> None:
    if conclusion in {"confirmed_correct", "confirmed_incorrect", "partially_correct"}:
        attempt.status = "graded"
        status = "completed"
    elif conclusion == "resubmit":
        attempt.status = "resubmit"
        status = "pending"
    elif conclusion == "question_issue":
        attempt.status = "question_issue"
        status = "question_issue"
    else:
        attempt.status = "review_pending"
        status = "review_pending"
    # A decision about an earlier attempt must not finish a newer submission.
    if link.latest_attempt_id == attempt.id:
        link.status = status


def create_teacher_router(provider: ApiPoolProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/teachers/dashboard")
    async def dashboard(user: User = Depends(_teacher), db: AsyncSession = Depends(get_db)):
        class_ids = select(TeacherClass.id).where(TeacherClass.teacher_id == user.id)
        student_ids = select(TeacherClassStudent.student_id).where(
            TeacherClassStudent.class_id.in_(class_ids)
        )
        today = datetime.now(timezone.utc).date()
        pending = int(
            await db.scalar(
                select(func.count())
                .select_from(TeacherReviewTask)
                .where(
                    TeacherReviewTask.class_id.in_(class_ids),
                    TeacherReviewTask.status == "pending",
                )
            )
            or 0
        )
        new_mistakes = int(
            await db.scalar(
                select(func.count())
                .select_from(Question)
                .where(
                    Question.user_id.in_(student_ids),
                    func.date(Question.created_at) == today,
                )
            )
            or 0
        )
        overdue_students = int(
            await db.scalar(
                select(func.count(func.distinct(ReviewPlan.user_id))).where(
                    ReviewPlan.user_id.in_(student_ids),
                    ReviewPlan.status == "pending",
                    ReviewPlan.due_at < datetime.now(timezone.utc),
                )
            )
            or 0
        )
        unfinished = int(
            await db.scalar(
                select(func.count())
                .select_from(AssignmentStudent)
                .join(
                    QuestionAssignment,
                    QuestionAssignment.id == AssignmentStudent.assignment_id,
                )
                .where(QuestionAssignment.teacher_id == user.id, AssignmentStudent.status == "pending")
            )
            or 0
        )
        mastery = list(await db.scalars(select(MasteryState).where(MasteryState.user_id.in_(student_ids))))
        weak = sorted(mastery, key=lambda item: item.mastery_score)[:5]
        errors = list(
            await db.scalars(
                select(MisconceptionState)
                .where(
                    MisconceptionState.user_id.in_(student_ids),
                    MisconceptionState.status != "resolved",
                )
                .order_by(MisconceptionState.probability.desc())
                .limit(5)
            )
        )
        attention = list(
            await db.execute(
                select(User.id, User.name, func.count(TeacherReviewTask.id))
                .join(
                    TeacherReviewTask,
                    TeacherReviewTask.student_id == User.id,
                )
                .where(TeacherReviewTask.class_id.in_(class_ids), TeacherReviewTask.status == "pending")
                .group_by(User.id, User.name)
                .order_by(func.count(TeacherReviewTask.id).desc())
                .limit(5)
            )
        )
        return {
            "pending_reviews": pending,
            "today_mistakes": new_mistakes,
            "overdue_students": overdue_students,
            "unfinished_assignments": unfinished,
            "average_mastery": round(sum(item.mastery_score for item in mastery) / len(mastery), 3)
            if mastery
            else 0,
            "weak_points": [{"name": item.knowledge_point, "score": item.mastery_score} for item in weak],
            "frequent_errors": [{"name": item.label, "probability": item.probability} for item in errors],
            "attention_students": [
                {"id": row[0], "name": row[1], "pending_reviews": row[2]} for row in attention
            ],
        }

    @router.post("/teachers/classes")
    async def create_class(
        payload: dict = Body(...), user: User = Depends(_teacher), db: AsyncSession = Depends(get_db)
    ):
        name = str(payload.get("name", "")).strip()
        if not name:
            raise HTTPException(422, "请填写班级名称")
        classroom = TeacherClass(teacher_id=user.id, name=name, grade=str(payload.get("grade", "")))
        db.add(classroom)
        await db.flush()
        _audit(
            db,
            user.id,
            "class.create",
            "class",
            classroom.id,
            {},
            _row(classroom),
            str(payload.get("reason", "创建班级")),
        )
        await db.commit()
        return _row(classroom)

    @router.post("/teachers/classes/{class_id}/students")
    async def add_student(
        class_id: str,
        payload: dict = Body(...),
        user: User = Depends(_teacher),
        db: AsyncSession = Depends(get_db),
    ):
        await _managed_class(db, user.id, class_id)
        student = await db.scalar(
            select(User).where(User.email == str(payload.get("email", "")).strip().lower())
        )
        if student is None or student.role != "student":
            raise HTTPException(404, "未找到该学生账号")
        exists = await db.scalar(
            select(TeacherClassStudent.id).where(
                TeacherClassStudent.class_id == class_id,
                TeacherClassStudent.student_id == student.id,
            )
        )
        if not exists:
            db.add(TeacherClassStudent(class_id=class_id, student_id=student.id))
            _audit(
                db,
                user.id,
                "class.student.add",
                "class",
                class_id,
                {},
                {"student_id": student.id},
                str(payload.get("reason", "加入班级")),
            )
            await db.commit()
        return {"id": student.id, "name": student.name, "email": student.email}

    @router.delete("/teachers/classes/{class_id}/students/{student_id}")
    async def remove_student(
        class_id: str,
        student_id: str,
        reason: str = Query(...),
        user: User = Depends(_teacher),
        db: AsyncSession = Depends(get_db),
    ):
        await _managed_student(db, user.id, class_id, student_id)
        link = await db.scalar(
            select(TeacherClassStudent).where(
                TeacherClassStudent.class_id == class_id,
                TeacherClassStudent.student_id == student_id,
            )
        )
        await db.delete(link)
        _audit(db, user.id, "class.student.remove", "class", class_id, {"student_id": student_id}, {}, reason)
        await db.commit()
        return {"removed": True}

    @router.get("/teachers/reviews")
    async def review_queue(
        class_id: str | None = None,
        student_id: str | None = None,
        subject: str | None = None,
        verdict: str | None = None,
        conflict: bool | None = None,
        user: User = Depends(_teacher),
        db: AsyncSession = Depends(get_db),
    ):
        query = (
            select(TeacherReviewTask, User, Question)
            .join(User, User.id == TeacherReviewTask.student_id)
            .join(
                Question,
                Question.id == TeacherReviewTask.question_id,
            )
            .join(TeacherClass, TeacherClass.id == TeacherReviewTask.class_id)
            .where(
                TeacherClass.teacher_id == user.id,
                TeacherReviewTask.status == "pending",
            )
        )
        if class_id:
            await _managed_class(db, user.id, class_id)
            query = query.where(TeacherReviewTask.class_id == class_id)
        if student_id:
            query = query.where(TeacherReviewTask.student_id == student_id)
        if subject:
            query = query.where(Question.subject == subject)
        if verdict:
            query = query.where(TeacherReviewTask.ai_result["verdict"].as_string() == verdict)
        if conflict is not None:
            query = query.where(TeacherReviewTask.has_conflict == conflict)
        rows = list(await db.execute(query.order_by(TeacherReviewTask.created_at)))
        now = datetime.now(timezone.utc)
        return [
            {
                **_row(task),
                "student_name": student.name,
                "question_title": question.title,
                "question_summary": question.question_text[:100],
                "student_answer": task.ai_result.get("student_answer", ""),
                "subject": question.subject,
                "question_type": question.question_type,
                "verdict": task.ai_result.get("verdict"),
                "waiting_minutes": max(
                    0,
                    int(
                        (
                            now - task.created_at.replace(tzinfo=task.created_at.tzinfo or timezone.utc)
                        ).total_seconds()
                        / 60
                    ),
                ),
            }
            for task, student, question in rows
        ]

    @router.get("/teachers/reviews/{task_id}")
    async def review_detail(task_id: str, user: User = Depends(_teacher), db: AsyncSession = Depends(get_db)):
        task = await db.get(TeacherReviewTask, task_id)
        if task is None:
            raise HTTPException(404, "复核任务不存在")
        await _managed_student(db, user.id, task.class_id, task.student_id)
        question = await db.get(Question, task.question_id)
        if question is None:
            raise HTTPException(409, "题目已不存在")
        teacher_question = await db.scalar(
            select(TeacherQuestion).where(
                TeacherQuestion.question_id == task.question_id,
            )
        )
        attempt = (
            await db.get(AssignmentAttempt, task.source_id)
            if task.source_type == "assignment_attempt"
            else None
        )
        analysis = await db.scalar(
            select(ProblemAnalysis).where(ProblemAnalysis.question_id == task.question_id)
        )
        references = (
            list(
                await db.scalars(
                    select(ReferenceStep)
                    .where(
                        ReferenceStep.analysis_id == analysis.id,
                    )
                    .order_by(ReferenceStep.step_index)
                )
            )
            if analysis
            else []
        )
        ocr = await db.scalar(
            select(OCRRun).where(OCRRun.question_id == task.question_id).order_by(OCRRun.created_at.desc())
        )
        assets = list(
            await db.scalars(select(QuestionAsset).where(QuestionAsset.question_id == task.question_id))
        )
        mastery = list(
            await db.scalars(
                select(MasteryState).where(
                    MasteryState.user_id == task.student_id,
                    MasteryState.subject == question.subject,
                )
            )
        )
        results = list(
            await db.scalars(
                select(TeacherReviewResult)
                .where(
                    TeacherReviewResult.task_id == task.id,
                )
                .order_by(TeacherReviewResult.created_at)
            )
        )
        return {
            "task": _row(task),
            "question": _row(question),
            "teacher_question": _row(teacher_question) if teacher_question else None,
            "attempt": {
                **_row(attempt),
                "handwriting_image_url": sign_media_url(attempt.handwriting_asset_ref, settings.auth_secret)
                if attempt.handwriting_asset_ref
                else "",
            }
            if attempt
            else None,
            "ocr": _row(ocr) if ocr else None,
            "analysis": _row(analysis) if analysis else None,
            "reference_steps": [_row(item) for item in references],
            "assets": [
                {**_row(item), "url": sign_media_url("/" + item.path, settings.auth_secret)}
                for item in assets
            ],
            "mastery": [_row(item) for item in mastery],
            "history": [_row(item) for item in results],
        }

    @router.post("/teachers/reviews/{task_id}/decision")
    async def decide_review(
        task_id: str,
        payload: dict = Body(...),
        user: User = Depends(_teacher),
        db: AsyncSession = Depends(get_db),
    ):
        task = await db.scalar(
            select(TeacherReviewTask).where(TeacherReviewTask.id == task_id).with_for_update()
        )
        if task is None:
            raise HTTPException(404, "复核任务不存在")
        await _managed_student(db, user.id, task.class_id, task.student_id)
        expected_version = int(payload.get("version", 0))
        if task.version != expected_version or task.status != "pending":
            raise HTTPException(409, "任务已被处理或作答已更新，请刷新后重试")
        conclusion = str(payload.get("conclusion", ""))
        if conclusion not in {
            "confirmed_correct",
            "confirmed_incorrect",
            "partially_correct",
            "resubmit",
            "question_issue",
        }:
            raise HTTPException(422, "人工结论无效")
        reason = str(payload.get("reason", "")).strip()
        if not reason:
            raise HTTPException(422, "请填写复核理由")
        before = _row(task)
        assignment_context = await _assignment_review_context(db, task)
        count_mastery = not assignment_context or (assignment_context[2].settings or {}).get(
            "count_mastery", True
        )
        result = TeacherReviewResult(
            task_id=task.id,
            teacher_id=user.id,
            conclusion=conclusion,
            score=float(payload["score"]) if payload.get("score") is not None else None,
            reason=reason,
            first_key_error=str(payload.get("first_key_error", "")),
            error_type=str(payload.get("error_type", "")),
            propagated_error=bool(payload.get("propagated_error", False)),
            student_hint=str(payload.get("student_hint", "")),
            next_task=str(payload.get("next_task", "")),
            mastered_steps=list(payload.get("mastered_steps", [])),
            allow_learning_update=bool(payload.get("allow_learning_update", True))
            and bool(count_mastery)
            and conclusion in {"confirmed_correct", "confirmed_incorrect"},
            evidence_snapshot={"ai": task.ai_result, "rule": task.rule_result, "task_version": task.version},
        )
        db.add(result)
        await db.flush()
        if result.allow_learning_update and not task.learning_applied:
            question = await db.get(Question, task.question_id)
            if question is None:
                raise HTTPException(409, "题目已不存在")
            result.learning_snapshot = await _apply_learning(
                db,
                task.student_id,
                question,
                conclusion == "confirmed_correct",
                result.id,
            )
            task.learning_applied = True
        task.status = (
            "resubmit"
            if conclusion == "resubmit"
            else "question_issue"
            if conclusion == "question_issue"
            else "resolved"
        )
        if assignment_context:
            _sync_assignment_review(assignment_context[0], assignment_context[1], conclusion)
        task.version += 1
        _audit(db, user.id, "review.decision", "teacher_review_task", task.id, before, _row(result), reason)
        await db.commit()
        return {"task": _row(task), "result": _row(result)}

    @router.post("/teachers/reviews/{task_id}/revoke")
    async def revoke_review(
        task_id: str,
        payload: dict = Body(...),
        user: User = Depends(_teacher),
        db: AsyncSession = Depends(get_db),
    ):
        task = await db.scalar(
            select(TeacherReviewTask).where(TeacherReviewTask.id == task_id).with_for_update()
        )
        if task is None:
            raise HTTPException(404, "复核任务不存在")
        await _managed_student(db, user.id, task.class_id, task.student_id)
        reason = str(payload.get("reason", "")).strip()
        if not reason:
            raise HTTPException(422, "请填写撤销原因")
        result = await db.scalar(
            select(TeacherReviewResult)
            .where(
                TeacherReviewResult.task_id == task.id,
                TeacherReviewResult.revoked_at.is_(None),
            )
            .order_by(TeacherReviewResult.created_at.desc())
        )
        if result is None:
            raise HTTPException(409, "没有可撤销的人工结论")
        snapshot = result.learning_snapshot or {}
        if task.learning_applied and snapshot:
            after_mastery, before_mastery = snapshot.get("mastery_after"), snapshot.get("mastery_before")
            after_error, before_error = (
                snapshot.get("misconception_after"),
                snapshot.get("misconception_before"),
            )
            mastery = (
                await db.get(MasteryState, after_mastery["id"]) if isinstance(after_mastery, dict) else None
            )
            misconception = (
                await db.get(MisconceptionState, after_error["id"]) if isinstance(after_error, dict) else None
            )
            if (
                mastery
                and isinstance(after_mastery, dict)
                and mastery.mastery_score == after_mastery.get("mastery_score")
            ):
                mastery.mastery_score = (
                    before_mastery.get("mastery_score", 0) if isinstance(before_mastery, dict) else 0
                )
                mastery.evidence_count = max(0, mastery.evidence_count - 1)
            if (
                misconception
                and isinstance(after_error, dict)
                and misconception.probability == after_error.get("probability")
            ):
                misconception.probability = (
                    before_error.get("probability", 0.5) if isinstance(before_error, dict) else 0.5
                )
                misconception.evidence_count = max(0, misconception.evidence_count - 1)
            db.add(
                CognitiveUpdate(
                    user_id=task.student_id,
                    question_id=task.question_id,
                    entity_type="teacher_review_reversal",
                    entity_key=result.id,
                    old_value=1,
                    new_value=0,
                    evidence={"revoked_review_id": result.id},
                    reason=reason,
                )
            )
        result.revoked_at = datetime.now(timezone.utc)
        task.status = "pending"
        task.learning_applied = False
        task.version += 1
        assignment_context = await _assignment_review_context(db, task)
        if assignment_context:
            _sync_assignment_review(assignment_context[0], assignment_context[1], "revoke")
        _audit(db, user.id, "review.revoke", "teacher_review_task", task.id, _row(result), _row(task), reason)
        await db.commit()
        return _row(task)

    @router.post("/teachers/reviews/{task_id}/regrade")
    async def regrade_review(
        task_id: str,
        payload: dict = Body(...),
        user: User = Depends(_teacher),
        db: AsyncSession = Depends(get_db),
    ):
        task = await db.scalar(
            select(TeacherReviewTask).where(TeacherReviewTask.id == task_id).with_for_update()
        )
        if task is None:
            raise HTTPException(404, "复核任务不存在")
        await _managed_student(db, user.id, task.class_id, task.student_id)
        if task.version != int(payload.get("version", 0)) or task.status != "pending":
            raise HTTPException(409, "任务已发生变化，请刷新后重试")
        reason = str(payload.get("reason", "")).strip()
        if not reason:
            raise HTTPException(422, "请填写重新判定原因")
        attempt = await db.get(AssignmentAttempt, task.source_id)
        question = await db.get(Question, task.question_id)
        if question is None:
            raise HTTPException(409, "题目已不存在")
        meta = await db.scalar(select(TeacherQuestion).where(TeacherQuestion.question_id == question.id))
        if attempt is None or meta is None:
            raise HTTPException(409, "原始作答证据不可用")
        before = {"task": _row(task), "attempt": _row(attempt)}
        answer = str(payload.get("ocr_text", attempt.answer)).strip()
        expected = str(payload.get("standard_answer", meta.standard_answer)).strip()
        references = list(payload.get("reference_steps", meta.reference_steps))
        grading = await grade_answer(
            provider,
            question=question.question_text,
            answer=answer,
            expected=expected,
            reference_solution=references,
            subject=question.subject,
            question_type=question.question_type,
            options=question.options,
        )
        attempt.grading_details = {
            **grading,
            "student_answer": answer,
            "original_grading": attempt.grading_details,
            "teacher_revision": {
                "ocr_text": payload.get("ocr_text"),
                "standard_answer": payload.get("standard_answer"),
                "reason": reason,
            },
        }
        attempt.verdict = str(grading["verdict"])
        attempt.version += 1
        task.ai_result = {**grading, "student_answer": answer}
        task.rule_result = {key: grading.get(key) for key in ("method", "correct", "score", "evidence")}
        task.confidence = float(grading.get("confidence", 0))
        task.has_conflict = bool(grading.get("conflict"))
        task.reason_codes = _review_reasons(grading, None, not expected or not references)
        if not task.reason_codes:
            task.reason_codes = ["teacher_regrade_confirmation"]
        task.version += 1
        _audit(
            db,
            user.id,
            "review.regrade",
            "teacher_review_task",
            task.id,
            before,
            {"task": _row(task), "grading": grading},
            reason,
        )
        await db.commit()
        return {"task": _row(task), "grading": grading}

    @router.post("/teachers/reviews/{task_id}/transfer")
    async def transfer_review(
        task_id: str,
        payload: dict = Body(...),
        user: User = Depends(_teacher),
        db: AsyncSession = Depends(get_db),
    ):
        task = await db.scalar(
            select(TeacherReviewTask).where(TeacherReviewTask.id == task_id).with_for_update()
        )
        if task is None:
            raise HTTPException(404, "复核任务不存在")
        classroom = await _managed_class(db, user.id, task.class_id)
        target = await db.get(User, str(payload.get("teacher_id", "")))
        reason = str(payload.get("reason", "")).strip()
        if target is None or target.role != "teacher" or not reason:
            raise HTTPException(422, "请选择教师并填写转交原因")
        # Minimal single-owner classes only allow transfer to the current class owner.
        if target.id != classroom.teacher_id:
            raise HTTPException(403, "目标教师不是该班级管理员")
        before = _row(task)
        task.assigned_teacher_id = target.id
        task.version += 1
        _audit(db, user.id, "review.transfer", "teacher_review_task", task.id, before, _row(task), reason)
        await db.commit()
        return _row(task)

    @router.get("/teachers/questions")
    async def teacher_questions(user: User = Depends(_teacher), db: AsyncSession = Depends(get_db)):
        rows = list(
            await db.execute(
                select(TeacherQuestion, Question)
                .join(
                    Question,
                    Question.id == TeacherQuestion.question_id,
                )
                .where(TeacherQuestion.teacher_id == user.id)
                .order_by(TeacherQuestion.created_at.desc())
            )
        )
        return [{"teacher_question": _row(meta), "question": _row(question)} for meta, question in rows]

    @router.post("/teachers/questions")
    async def create_question(
        payload: dict = Body(...), user: User = Depends(_teacher), db: AsyncSession = Depends(get_db)
    ):
        text = str(payload.get("question_text", "")).strip()
        if not text:
            raise HTTPException(422, "请填写题干")
        question = Question(
            user_id=user.id,
            subject=str(payload.get("subject", "数学")),
            grade=payload.get("grade"),
            title=str(payload.get("title", text[:40])),
            question_text=text,
            status="confirmed",
            confirmed=True,
            options=list(payload.get("options", [])),
            question_type=str(payload.get("question_type", "综合题")),
            knowledge_points=list(payload.get("knowledge_points", [])),
        )
        db.add(question)
        await db.flush()
        meta = TeacherQuestion(
            question_id=question.id,
            teacher_id=user.id,
            source_type=str(payload.get("source_type", "manual")),
            standard_answer=str(payload.get("standard_answer", "")),
            reference_steps=list(payload.get("reference_steps", [])),
            scoring_points=list(payload.get("scoring_points", [])),
            difficulty=str(payload.get("difficulty", "")),
            allow_auto_grade=bool(payload.get("allow_auto_grade", True)),
            require_handwriting=bool(payload.get("require_handwriting", False)),
            status="published",
        )
        db.add(meta)
        await db.flush()
        _audit(
            db,
            user.id,
            "question.create",
            "question",
            question.id,
            {},
            {"question": _row(question), "teacher_question": _row(meta)},
            str(payload.get("reason", "录入题目")),
        )
        await db.commit()
        return {"question": _row(question), "teacher_question": _row(meta)}

    @router.post("/teachers/assignments")
    async def create_assignment(
        payload: dict = Body(...), user: User = Depends(_teacher), db: AsyncSession = Depends(get_db)
    ):
        class_id = str(payload.get("class_id", ""))
        classroom = await _managed_class(db, user.id, class_id)
        question_id = str(payload.get("question_id", ""))
        owned = await db.scalar(
            select(TeacherQuestion).where(
                TeacherQuestion.question_id == question_id,
                TeacherQuestion.teacher_id == user.id,
            )
        )
        if owned is None:
            raise HTTPException(404, "题目不存在或无权布置")
        requested = set(payload.get("student_ids") or [])
        links = list(
            await db.scalars(select(TeacherClassStudent).where(TeacherClassStudent.class_id == classroom.id))
        )
        targets = [link.student_id for link in links if not requested or link.student_id in requested]
        if requested - set(targets):
            raise HTTPException(403, "包含不属于该班级的学生")
        if not targets:
            raise HTTPException(422, "班级中没有可布置的学生")
        try:
            due_at = parse_timestamp(str(payload["due_at"])) if payload.get("due_at") else None
        except ValueError as exc:
            raise HTTPException(422, "截止时间无效，请重新选择") from exc
        assignment = QuestionAssignment(
            teacher_id=user.id,
            question_id=question_id,
            class_id=class_id,
            title=str(payload.get("title", "练习任务")),
            due_at=due_at,
            settings=dict(payload.get("settings", {})),
        )
        db.add(assignment)
        await db.flush()
        db.add_all(
            [AssignmentStudent(assignment_id=assignment.id, student_id=student_id) for student_id in targets]
        )
        _audit(
            db,
            user.id,
            "assignment.create",
            "assignment",
            assignment.id,
            {},
            {**_row(assignment), "student_ids": targets},
            str(payload.get("reason", "布置练习")),
        )
        await db.commit()
        return {**_row(assignment), "student_count": len(targets)}

    @router.get("/teachers/assignments")
    async def assignments(user: User = Depends(_teacher), db: AsyncSession = Depends(get_db)):
        rows = list(
            await db.scalars(
                select(QuestionAssignment)
                .where(
                    QuestionAssignment.teacher_id == user.id,
                )
                .order_by(QuestionAssignment.created_at.desc())
            )
        )
        result = []
        for item in rows:
            total = int(
                await db.scalar(
                    select(func.count())
                    .select_from(AssignmentStudent)
                    .where(AssignmentStudent.assignment_id == item.id)
                )
                or 0
            )
            completed = int(
                await db.scalar(
                    select(func.count())
                    .select_from(AssignmentStudent)
                    .where(
                        AssignmentStudent.assignment_id == item.id,
                        AssignmentStudent.status == "completed",
                    )
                )
                or 0
            )
            result.append({**_row(item), "student_count": total, "completed_count": completed})
        return result

    @router.get("/students/assignments")
    async def student_assignments(user: User = Depends(_account), db: AsyncSession = Depends(get_db)):
        if user.role != "student":
            raise HTTPException(403, "当前账号不是学生")
        rows = list(
            await db.execute(
                select(AssignmentStudent, QuestionAssignment, Question)
                .join(
                    QuestionAssignment,
                    QuestionAssignment.id == AssignmentStudent.assignment_id,
                )
                .join(Question, Question.id == QuestionAssignment.question_id)
                .where(
                    AssignmentStudent.student_id == user.id,
                )
                .order_by(QuestionAssignment.due_at)
            )
        )
        attempt_ids = {link.latest_attempt_id for link, _, _ in rows if link.latest_attempt_id}
        attempts = (
            {
                item.id: item
                for item in await db.scalars(
                    select(AssignmentAttempt).where(
                        AssignmentAttempt.id.in_(attempt_ids),
                        AssignmentAttempt.student_id == user.id,
                    )
                )
            }
            if attempt_ids
            else {}
        )
        feedback_rows = (
            list(
                await db.execute(
                    select(TeacherReviewTask.source_id, TeacherReviewResult)
                    .join(
                        TeacherReviewResult,
                        TeacherReviewResult.task_id == TeacherReviewTask.id,
                    )
                    .where(
                        TeacherReviewTask.student_id == user.id,
                        TeacherReviewTask.source_type == "assignment_attempt",
                        TeacherReviewTask.source_id.in_(attempt_ids),
                        TeacherReviewResult.revoked_at.is_(None),
                    )
                    .order_by(TeacherReviewResult.created_at.desc())
                )
            )
            if attempt_ids
            else []
        )
        feedback: dict[str, dict[str, Any]] = {}
        for source_id, decision in feedback_rows:
            feedback.setdefault(
                source_id,
                {
                    field: getattr(decision, field)
                    for field in (
                        "conclusion",
                        "score",
                        "first_key_error",
                        "student_hint",
                        "next_task",
                    )
                },
            )
        question_ids = {question.id for _, _, question in rows}
        handwritten_questions = (
            set(
                await db.scalars(
                    select(TeacherQuestion.question_id).where(
                        TeacherQuestion.question_id.in_(question_ids),
                        TeacherQuestion.require_handwriting.is_(True),
                    )
                )
            )
            if question_ids
            else set()
        )
        result = []
        for link, item, question in rows:
            attempt = attempts.get(link.latest_attempt_id)
            decision = feedback.get(link.latest_attempt_id)
            public_link = _row(link)
            if decision and decision["conclusion"] == "question_issue":
                public_link["status"] = "question_issue"
            result.append(
                {
                    "student_assignment": public_link,
                    "assignment": _row(item),
                    "question": _row(question),
                    "latest_attempt": {"answer": attempt.answer, "steps": attempt.steps} if attempt else None,
                    "teacher_feedback": decision,
                    "require_handwriting": question.id in handwritten_questions,
                    "grading_feedback": (attempt.grading_details or {}).get("feedback", "")
                    if attempt and link.status == "completed" and not decision
                    else "",
                }
            )
        return result

    @router.post("/students/assignments/{student_assignment_id}/attempts")
    async def submit_assignment(
        student_assignment_id: str,
        payload: dict = Body(...),
        user: User = Depends(_account),
        db: AsyncSession = Depends(get_db),
    ):
        link = await db.get(
            AssignmentStudent, student_assignment_id, with_for_update=True, populate_existing=True
        )
        if link is None or link.student_id != user.id:
            raise HTTPException(404, "布置任务不存在")
        assignment = await db.get(QuestionAssignment, link.assignment_id)
        if assignment is None:
            raise HTTPException(409, "布置记录已不存在")
        question = await db.get(Question, assignment.question_id)
        if question is None:
            raise HTTPException(409, "题目已不存在")
        meta = await db.scalar(select(TeacherQuestion).where(TeacherQuestion.question_id == question.id))
        if meta is None:
            raise HTTPException(409, "题目判题配置已不存在")
        can_repeat = link.status == "completed" and (assignment.settings or {}).get("allow_repeat", False)
        if link.status != "pending" and not can_repeat:
            raise HTTPException(409, "当前任务暂不能再次作答")
        image_url, recognition = validate_answer_handwriting(
            user_id=user.id,
            context_type="assignment",
            context_id=link.id,
            image_url=str(payload.get("handwriting_image_url") or payload.get("handwriting_asset_ref") or ""),
            recognition=payload.get("handwriting_recognition"),
        )
        if meta.require_handwriting and not image_url:
            raise HTTPException(422, "该任务需要上传手写作答照片")
        answer = str(payload.get("answer", "")).strip()
        if not answer:
            raise HTTPException(422, "请填写答案")
        settings_json = assignment.settings or {}
        if meta.allow_auto_grade and settings_json.get("allow_auto_grade", True):
            grading = await grade_answer(
                provider,
                question=question.question_text,
                answer=answer,
                expected=meta.standard_answer,
                reference_solution=meta.reference_steps,
                subject=question.subject,
                question_type=question.question_type,
                options=question.options,
            )
        else:
            grading = {
                "correct": None,
                "score": None,
                "verdict": REVIEW_REQUIRED,
                "decisive": False,
                "can_update_learning": False,
                "confidence": 0,
                "method": "teacher_pending",
                "grader": "teacher_pending",
                "conflict": False,
                "feedback": "该任务由教师批改，作答已保存并提交核对。",
                "evidence": [],
            }
        recognition = recognition or {}
        ocr_confidence = (
            float(recognition["confidence"]) if recognition.get("confidence") is not None else None
        )
        process_question = any(
            marker in question.question_type.casefold()
            for marker in (
                "综合",
                "解答",
                "证明",
                "计算",
                "主观",
                "材料",
                "proof",
                "subjective",
                "calculation",
            )
        )
        incomplete = not meta.standard_answer or (process_question and not meta.reference_steps)
        reasons = _review_reasons(grading, ocr_confidence, incomplete)
        if settings_json.get("require_teacher_review"):
            reasons.append("teacher_required")
        if not meta.allow_auto_grade or not settings_json.get("allow_auto_grade", True):
            reasons.append("auto_grade_disabled")
        attempt = AssignmentAttempt(
            assignment_student_id=link.id,
            student_id=user.id,
            question_id=question.id,
            answer=answer,
            steps=list(payload.get("steps", [])),
            handwriting_asset_ref=image_url or None,
            grading_details={**grading, "student_answer": answer, "handwriting_recognition": recognition},
            verdict=str(grading["verdict"]),
            status="review_pending" if reasons else "graded",
        )
        db.add(attempt)
        await db.flush()
        link.latest_attempt_id = attempt.id
        if reasons:
            link.status = "review_pending"
            db.add(
                TeacherReviewTask(
                    class_id=assignment.class_id,
                    student_id=user.id,
                    question_id=question.id,
                    source_id=attempt.id,
                    reason_codes=list(dict.fromkeys(reasons)),
                    ai_result={**grading, "student_answer": answer},
                    rule_result={key: grading.get(key) for key in ("method", "correct", "score", "evidence")},
                    confidence=float(grading.get("confidence", 0)),
                    has_conflict=bool(grading.get("conflict")),
                    assigned_teacher_id=assignment.teacher_id,
                )
            )
        else:
            link.status = "completed"
            if grading["verdict"] in {CONFIRMED_CORRECT, CONFIRMED_INCORRECT} and settings_json.get(
                "count_mastery", True
            ):
                await _apply_learning(
                    db, user.id, question, grading["verdict"] == CONFIRMED_CORRECT, attempt.id
                )
        await db.commit()
        return {"attempt": _row(attempt), "grading": grading, "entered_review_queue": bool(reasons)}

    @router.get("/students/teacher-feedback")
    async def student_feedback(user: User = Depends(_account), db: AsyncSession = Depends(get_db)):
        if user.role != "student":
            raise HTTPException(403, "当前账号不是学生")
        rows = list(
            await db.execute(
                select(TeacherReviewResult, TeacherReviewTask)
                .join(
                    TeacherReviewTask,
                    TeacherReviewTask.id == TeacherReviewResult.task_id,
                )
                .where(TeacherReviewTask.student_id == user.id, TeacherReviewResult.revoked_at.is_(None))
                .order_by(TeacherReviewResult.created_at.desc())
                .limit(20)
            )
        )
        return [{"result": _row(result), "task": _row(task)} for result, task in rows]

    @router.get("/teachers/students/{student_id}/plans")
    async def student_plans(
        student_id: str, class_id: str, user: User = Depends(_teacher), db: AsyncSession = Depends(get_db)
    ):
        await _managed_student(db, user.id, class_id, student_id)
        plans = list(
            await db.scalars(
                select(ReviewPlan).where(ReviewPlan.user_id == student_id).order_by(ReviewPlan.due_at)
            )
        )
        return [_row(item) for item in plans]

    @router.patch("/teachers/plans/{plan_id}")
    async def update_plan(
        plan_id: str,
        payload: dict = Body(...),
        user: User = Depends(_teacher),
        db: AsyncSession = Depends(get_db),
    ):
        plan = await db.get(ReviewPlan, plan_id)
        if plan is None:
            raise HTTPException(404, "学习计划不存在")
        class_id = str(payload.get("class_id", ""))
        await _managed_student(db, user.id, class_id, plan.user_id)
        reason = str(payload.get("reason", "")).strip()
        if not reason:
            raise HTTPException(422, "请填写修改原因")
        before = _row(plan)
        if "due_at" in payload:
            try:
                plan.due_at = parse_timestamp(str(payload["due_at"]))
            except ValueError as exc:
                raise HTTPException(422, "请选择有效的截止时间") from exc
        if "status" in payload and payload["status"] in {"pending", "paused", "cancelled"}:
            plan.status = payload["status"]
        if "task_reason" in payload:
            plan.reason = str(payload["task_reason"])
        _audit(db, user.id, "plan.update", "review_plan", plan.id, before, _row(plan), reason)
        await db.commit()
        return _row(plan)

    @router.get("/teachers/audit-logs")
    async def audit_logs(user: User = Depends(_teacher), db: AsyncSession = Depends(get_db)):
        rows = list(
            await db.scalars(
                select(TeacherAuditLog)
                .where(
                    TeacherAuditLog.teacher_id == user.id,
                )
                .order_by(TeacherAuditLog.created_at.desc())
                .limit(200)
            )
        )
        return [_row(item) for item in rows]

    return router
