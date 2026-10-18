"""Student-facing evidence: project persisted facts, never infer mastery from completion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DatasetPracticeAttempt,
    Diagnosis,
    OCRRun,
    ProblemAnalysis,
    ProcessingJob,
    Question,
    ReviewPlan,
    ReviewRecord,
    TutorSession,
)


def utc(value: datetime) -> datetime:
    # MySQL DATETIME is stored in UTC but returned without tzinfo.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def build_learning_journey(
    question: Question,
    *,
    analysis: ProblemAnalysis | None = None,
    diagnosis: Diagnosis | None = None,
    job: ProcessingJob | None = None,
    ocr: OCRRun | None = None,
    sessions: list[TutorSession] | None = None,
    practices: list[DatasetPracticeAttempt] | None = None,
    plans: list[ReviewPlan] | None = None,
    reviews: list[ReviewRecord] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = utc(now or datetime.now(timezone.utc))
    sessions, practices, plans, reviews = sessions or [], practices or [], plans or [], reviews or []
    current_sessions = [s for s in sessions if not (s.state or {}).get("question_changed")]
    latest = max(current_sessions, key=lambda s: utc(s.created_at), default=None)
    active = next(
        (
            s
            for s in sorted(current_sessions, key=lambda s: utc(s.created_at), reverse=True)
            if s.status == "active"
        ),
        None,
    )
    evidence_states = [session.state or {} for session in current_sessions]
    understanding = any(
        state.get("understanding_passed") and state.get("teach_back_passed") for state in evidence_states
    )
    # A finished session can represent assisted learning or failed transfer.
    independent = any(
        state.get("near_transfer")
        and state.get("far_transfer")
        and not state.get("assisted")
        and not state.get("transfer_insufficient")
        for state in evidence_states
    )
    trusted_practices = [
        p
        for p in practices
        if (p.grading_details or {}).get("can_update_learning") is True
        and not (p.grading_details or {}).get("question_changed")
    ]
    completed_reviews = [
        r
        for r in reviews
        if r.grade != "pending"
        and (r.grading_details or {}).get("can_update_learning") is True
        and not (r.grading_details or {}).get("question_changed")
    ]
    pending = sorted((p for p in plans if p.status == "pending"), key=lambda p: utc(p.due_at))
    end_of_day = (
        now.astimezone(timezone(timedelta(hours=8))).replace(hour=0, minute=0, second=0, microsecond=0)
        + timedelta(days=1)
    ).astimezone(timezone.utc)
    due = [p for p in pending if utc(p.due_at) < end_of_day]
    qid = question.id
    action = {
        "label": "练一道相似题",
        "url": f"/pages/practice/practice?id={qid}",
        "reason": "用独立作答检验理解。",
    }
    if question.status == "awaiting_crop":
        action = {
            "label": "继续框选题目",
            "url": f"/pages/crop/crop?id={qid}",
            "reason": "框选要学习的题目，再开始识别。",
        }
    elif job and job.status in {"pending", "running"}:
        action = {
            "label": "查看识别进度",
            "url": f"/pages/ocr/ocr?id={qid}&job={job.id}",
            "reason": "识别仍在处理中，完成后核对题干和答案。",
        }
    elif not question.confirmed:
        action = {
            "label": "核对题目信息",
            "url": f"/pages/ocr/ocr?id={qid}" + (f"&job={job.id}" if job and job.status == "failed" else ""),
            "reason": "确认题干和自己的作答，避免识别偏差影响诊断。",
        }
    elif diagnosis is None:
        action = {
            "label": "开始错因诊断",
            "url": f"/pages/diagnosis/diagnosis?id={qid}",
            "reason": "根据确认后的题目与步骤寻找错误原因。",
        }
    elif active:
        action = {
            "label": "继续上次辅导",
            "url": f"/pages/tutor/tutor?id={active.id}",
            "reason": "从已保存的学习阶段继续。",
        }
    elif due:
        action = {
            "label": "完成到期复习",
            "url": f"/pages/review/review?plan={due[0].id}",
            "reason": "先独立回忆，再根据判题结果安排下次复习。",
        }
    elif not latest:
        action = {
            "label": "查看诊断并学习",
            "url": f"/pages/diagnosis/diagnosis?id={qid}",
            "reason": "理解首错原因，再练习验证。",
        }

    def step(key: str, label: str, done: bool, detail: str) -> dict[str, Any]:
        return {"key": key, "label": label, "completed": done, "detail": detail}

    stages = [
        step(
            "confirmed",
            "核对题目",
            bool(question.confirmed),
            "题干与作答已确认" if question.confirmed else "等待核对识别内容",
        ),
        step(
            "diagnosed",
            "找到错因",
            diagnosis is not None,
            "已有诊断证据，可查看和纠正" if diagnosis else "等待完成诊断",
        ),
        step(
            "understanding",
            "理解并讲清",
            understanding,
            "理解检查与教回均通过" if understanding else "以实际检查与教回结果为准",
        ),
        step(
            "transfer",
            "独立迁移",
            independent,
            "相似题和综合应用均独立通过" if independent else "尚无完整的独立迁移证据",
        ),
        step(
            "review",
            "间隔复习",
            any(r.correct for r in completed_reviews),
            f"完成 {len(completed_reviews)} 次有效复习" if completed_reviews else "等待复习验证长期保持",
        ),
    ]
    events: list[dict[str, str]] = []

    def event(identifier: str, time: datetime, title: str, detail: str) -> None:
        events.append({"id": identifier, "time": utc(time).isoformat(), "title": title, "detail": detail})

    event(
        f"question:{qid}", question.created_at, "记录错题", f"{question.subject} · {question.question_type}"
    )
    if ocr:
        event(f"ocr:{ocr.id}", ocr.created_at, "图片识别", "识别完成，请以人工核对后的内容为准。")
    if diagnosis:
        event(
            f"diagnosis:{diagnosis.id}",
            diagnosis.created_at,
            "错因诊断",
            diagnosis.root_misconception or "可在诊断页查看具体证据。",
        )
    for session in sessions:
        flags = session.state or {}
        detail = (
            "本轮已结束，后续仍需独立练习和复习。"
            if session.status == "completed"
            else "学习进度已保存，可继续。"
        )
        if (session.state or {}).get("question_changed"):
            detail = "题目信息已修改，本次记录保留为历史，不计入当前进度。"
        elif flags.get("assisted") or flags.get("transfer_insufficient"):
            detail = "本轮使用了辅助或迁移尚不稳定，仍需巩固。"
        event(f"session:{session.id}", session.updated_at, "辅导记录", detail)
    for attempt in practices:
        trusted = (attempt.grading_details or {}).get("can_update_learning") is True and not (
            attempt.grading_details or {}
        ).get("question_changed")
        detail = (
            ("独立练习作答正确" if attempt.correct else "本次作答仍需巩固")
            if trusted
            else "本次结果待核对，未作为掌握证据"
        )
        if (attempt.grading_details or {}).get("question_changed"):
            detail = "题目信息已修改，此次练习作为历史记录保留。"
        event(f"practice:{attempt.id}", attempt.created_at, "题库练习", detail)
    for record in reviews:
        trusted = (
            (record.grading_details or {}).get("can_update_learning") is True
            and record.grade != "pending"
            and not (record.grading_details or {}).get("question_changed")
        )
        detail = (
            ("复习作答正确" if record.correct else "复习仍需巩固") if trusted else "等待完成判定和难度反馈"
        )
        if (record.grading_details or {}).get("question_changed"):
            detail = "题目信息已修改，此次复习作为历史记录保留。"
        event(f"review:{record.id}", record.created_at, "复习作答", detail)
    events.sort(key=lambda item: item["time"], reverse=True)
    verification = "已完成规则校验" if analysis and analysis.verified else "尚未通过规则校验"
    return {
        "question_id": qid,
        "title": question.title,
        "question_text": question.question_text,
        "subject": question.subject,
        "generated_at": now.isoformat(),
        "stages": stages,
        "next_action": action,
        "summary": "曾有独立迁移证据，继续用复习检验保持。"
        if independent
        else "按记录逐步巩固，完成辅导不等于已经掌握。",
        "verification": {
            "label": verification,
            "verified": bool(analysis and analysis.verified),
            "diagnosis_confirmed": bool(diagnosis and diagnosis.user_confirmed),
        },
        "practice": {
            "attempts": len(practices),
            "verified_attempts": len(trusted_practices),
            "correct": sum(bool(p.correct) for p in trusted_practices),
            "pending": sum(
                (p.grading_details or {}).get("can_update_learning") is not True
                and not (p.grading_details or {}).get("question_changed")
                for p in practices
            ),
        },
        "review": {
            "completed": len(completed_reviews),
            "due": len(due),
            "next_due_at": utc(pending[0].due_at).isoformat() if pending else None,
        },
        "events": events[:30],
        "history_limit": 50,
    }


async def get_learning_journey(db: AsyncSession, question: Question) -> dict[str, Any]:
    async def latest(model: Any) -> Any:
        return (
            await db.scalars(
                select(model)
                .where(model.question_id == question.id)
                .order_by(model.created_at.desc())
                .limit(1)
            )
        ).first()

    analysis = await latest(ProblemAnalysis)
    diagnosis = await latest(Diagnosis)
    job = await latest(ProcessingJob)
    ocr = await latest(OCRRun)
    sessions = list(
        await db.scalars(
            select(TutorSession)
            .where(
                TutorSession.question_id == question.id,
                TutorSession.user_id == question.user_id,
            )
            .order_by(TutorSession.created_at.desc())
            .limit(50)
        )
    )
    practices = list(
        await db.scalars(
            select(DatasetPracticeAttempt)
            .where(
                DatasetPracticeAttempt.mistake_id == question.id,
                DatasetPracticeAttempt.user_id == question.user_id,
            )
            .order_by(DatasetPracticeAttempt.created_at.desc())
            .limit(50)
        )
    )
    plans = list(
        await db.scalars(
            select(ReviewPlan)
            .where(
                ReviewPlan.question_id == question.id,
                ReviewPlan.user_id == question.user_id,
                ReviewPlan.status == "pending",
            )
            .order_by(ReviewPlan.due_at)
            .limit(50)
        )
    )
    reviews = list(
        await db.scalars(
            select(ReviewRecord)
            .join(ReviewPlan, ReviewRecord.plan_id == ReviewPlan.id)
            .where(
                ReviewPlan.question_id == question.id,
                ReviewPlan.user_id == question.user_id,
            )
            .order_by(ReviewRecord.created_at.desc())
            .limit(50)
        )
    )
    return build_learning_journey(
        question,
        analysis=analysis,
        diagnosis=diagnosis,
        job=job,
        ocr=ocr,
        sessions=sessions,
        practices=practices,
        plans=plans,
        reviews=reviews,
    )
