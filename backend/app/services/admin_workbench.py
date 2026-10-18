from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgentRun,
    AgentToolCall,
    CognitiveUpdate,
    Diagnosis,
    MasteryState,
    MisconceptionState,
    Question,
    ReviewPlan,
    StudentProfile,
    TutorSession,
    TutorTurn,
    User,
)

_SENSITIVE_PARTS = (
    "credential",
    "password",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "authorization",
    "chain_of_thought",
    "reasoning_content",
    "raw_prompt",
    "system_prompt",
)

_AGENT_LABELS = {
    "mindtrace_tutor": "教学决策智能体",
    "diagnosis": "错因诊断智能体",
    "cognition": "认知建模智能体",
}

_BRANCH_LABELS = {
    "guided_question": "引导式提问",
    "direct_explanation": "直接讲解",
    "worked_example": "例题示范",
    "visualization": "可视化讲解",
    "teach_back": "学生复述",
    "near_transfer": "近迁移检验",
    "far_transfer": "远迁移检验",
    "review_schedule": "安排复习",
}

_TOOL_LABELS = {
    "knowledge_search": "知识检索",
    "step_alignment": "步骤对齐",
    "visualization": "生成教学图示",
    "rediagnose": "动态再诊断",
    "answer_reveal": "答案与步骤核对",
    "answer_check": "数学结论验证",
    "variant_generator": "生成迁移题",
    "cognition_update": "更新认知状态",
    "review_scheduler": "生成复习计划",
}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def sanitize_admin_value(value: Any) -> Any:
    """Remove credentials and private model reasoning from operator-facing payloads."""
    if isinstance(value, dict):
        return {
            str(key): sanitize_admin_value(item)
            for key, item in value.items()
            if not any(part in str(key).lower() for part in _SENSITIVE_PARTS)
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_admin_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def build_agent_trace(runs: Iterable[Any], calls: Iterable[Any]) -> list[dict[str, Any]]:
    calls_by_run: dict[str, list[Any]] = {}
    for call in calls:
        calls_by_run.setdefault(call.agent_run_id, []).append(call)

    trace: list[dict[str, Any]] = []
    for run in runs:
        result = run.result if isinstance(run.result, dict) else {}
        branch = str(result.get("branch") or "")
        trace.append(
            {
                "id": run.id,
                "time": _iso(run.created_at),
                "agent": _AGENT_LABELS.get(run.agent_name, run.agent_name),
                "status": run.status,
                "decision": _BRANCH_LABELS.get(branch, branch or "完成一次决策"),
                "goal": str(result.get("next_goal") or result.get("goal") or ""),
                "observation": sanitize_admin_value(result.get("observation") or {}),
                "plan": sanitize_admin_value(result.get("plan") or {}),
                "verification": sanitize_admin_value(result.get("verification") or {}),
                "actions": [
                    {
                        "id": call.id,
                        "tool": _TOOL_LABELS.get(call.tool_name, call.tool_name),
                        "input": sanitize_admin_value(call.input_json or {}),
                        "output": sanitize_admin_value(call.output_json or {}),
                    }
                    for call in sorted(calls_by_run.get(run.id, []), key=lambda item: item.created_at)
                ],
            }
        )
    return trace


async def _count(db: AsyncSession, model: Any, *conditions: Any) -> int:
    statement = select(func.count()).select_from(model)
    if conditions:
        statement = statement.where(*conditions)
    return int(await db.scalar(statement) or 0)


async def get_admin_workbench(
    db: AsyncSession,
    provider_health: dict[str, Any],
    voice_health: dict[str, Any],
) -> dict[str, Any]:
    students = list(
        await db.scalars(
            select(User).where(User.role == "student").order_by(User.updated_at.desc()).limit(50)
        )
    )
    recent_rows = (
        await db.execute(
            select(TutorSession, User, Question)
            .join(User, User.id == TutorSession.user_id)
            .join(Question, Question.id == TutorSession.question_id)
            .order_by(TutorSession.updated_at.desc())
            .limit(50)
        )
    ).all()

    student_items = []
    for student in students:
        profile = (
            await db.scalars(select(StudentProfile).where(StudentProfile.user_id == student.id))
        ).first()
        student_items.append(
            {
                "id": student.id,
                "name": student.name,
                "grade": profile.grade if profile else "未设置",
                "question_count": await _count(
                    db, Question, Question.user_id == student.id, Question.status != "archived"
                ),
                "session_count": await _count(db, TutorSession, TutorSession.user_id == student.id),
                "updated_at": _iso(student.updated_at),
            }
        )

    sessions = [
        {
            "id": session.id,
            "student_id": student.id,
            "student_name": student.name,
            "question_id": question.id,
            "question_title": question.title,
            "subject": question.subject,
            "stage": session.stage,
            "status": session.status,
            "turn_count": session.turn_count,
            "mastery_score": session.mastery_score,
            "updated_at": _iso(session.updated_at),
        }
        for session, student, question in recent_rows
    ]

    provider_public = {
        "logical_model": provider_health.get("logical_model"),
        "status": provider_health.get("last_status"),
        "total_entries": provider_health.get("total_entries", 0),
        "text_entries": provider_health.get("text_entries", 0),
        "vision_entries": provider_health.get("vision_entries", 0),
    }
    voice_public = {
        "status": voice_health.get("status"),
        "loaded": bool(voice_health.get("loaded")),
        "stt_model": voice_health.get("stt_model"),
        "tts_model": voice_health.get("tts_model"),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "students": await _count(db, User, User.role == "student"),
            "questions": await _count(db, Question, Question.status != "archived"),
            "diagnoses": await _count(db, Diagnosis),
            "sessions": await _count(db, TutorSession),
            "active_sessions": await _count(db, TutorSession, TutorSession.status == "active"),
            "agent_runs": await _count(db, AgentRun),
            "cognitive_updates": await _count(db, CognitiveUpdate),
            "pending_reviews": await _count(db, ReviewPlan, ReviewPlan.status == "pending"),
        },
        "students": student_items,
        "sessions": sessions,
        "system": {"database": "mysql", "provider": provider_public, "voice": voice_public},
    }


async def get_admin_student(db: AsyncSession, student_id: str) -> dict[str, Any]:
    student = await db.get(User, student_id)
    if student is None or student.role != "student":
        raise HTTPException(status_code=404, detail="未找到学生")
    profile = (await db.scalars(select(StudentProfile).where(StudentProfile.user_id == student_id))).first()
    mastery = list(
        await db.scalars(
            select(MasteryState)
            .where(MasteryState.user_id == student_id)
            .order_by(MasteryState.updated_at.desc())
            .limit(20)
        )
    )
    misconceptions = list(
        await db.scalars(
            select(MisconceptionState)
            .where(MisconceptionState.user_id == student_id)
            .order_by(MisconceptionState.probability.desc())
            .limit(20)
        )
    )
    reviews = list(
        await db.scalars(
            select(ReviewPlan)
            .where(ReviewPlan.user_id == student_id)
            .order_by(ReviewPlan.due_at.asc())
            .limit(20)
        )
    )
    return {
        "student": {
            "id": student.id,
            "name": student.name,
            "grade": profile.grade if profile else "未设置",
            "learning_goal": profile.learning_goal if profile else "",
            "created_at": _iso(student.created_at),
        },
        "metrics": {
            "questions": await _count(
                db, Question, Question.user_id == student_id, Question.status != "archived"
            ),
            "sessions": await _count(db, TutorSession, TutorSession.user_id == student_id),
            "pending_reviews": await _count(
                db, ReviewPlan, ReviewPlan.user_id == student_id, ReviewPlan.status == "pending"
            ),
        },
        "mastery": [
            {
                "subject": item.subject,
                "knowledge_point": item.knowledge_point,
                "score": item.mastery_score,
                "confidence": item.confidence,
                "forgetting_risk": item.forgetting_risk,
                "evidence_count": item.evidence_count,
            }
            for item in mastery
        ],
        "misconceptions": [
            {
                "code": item.code,
                "label": item.label,
                "probability": item.probability,
                "status": item.status,
                "evidence_count": item.evidence_count,
            }
            for item in misconceptions
        ],
        "reviews": [
            {
                "id": item.id,
                "question_id": item.question_id,
                "due_at": _iso(item.due_at),
                "status": item.status,
                "reason": item.reason,
            }
            for item in reviews
        ],
    }


async def get_admin_session(db: AsyncSession, session_id: str) -> dict[str, Any]:
    session = await db.get(TutorSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="未找到教学会话")
    student = await db.get(User, session.user_id)
    question = await db.get(Question, session.question_id)
    diagnosis = (
        await db.scalars(
            select(Diagnosis)
            .where(Diagnosis.question_id == session.question_id)
            .order_by(Diagnosis.created_at.desc())
            .limit(1)
        )
    ).first()
    turns = list(
        await db.scalars(
            select(TutorTurn).where(TutorTurn.session_id == session_id).order_by(TutorTurn.created_at.asc())
        )
    )
    runs = list(
        await db.scalars(
            select(AgentRun).where(AgentRun.session_id == session_id).order_by(AgentRun.created_at.asc())
        )
    )
    run_ids = [run.id for run in runs]
    calls = (
        list(
            await db.scalars(
                select(AgentToolCall)
                .where(AgentToolCall.agent_run_id.in_(run_ids))
                .order_by(AgentToolCall.created_at.asc())
            )
        )
        if run_ids
        else []
    )
    updates = list(
        await db.scalars(
            select(CognitiveUpdate)
            .where(
                CognitiveUpdate.user_id == session.user_id,
                CognitiveUpdate.question_id == session.question_id,
            )
            .order_by(CognitiveUpdate.created_at.asc())
        )
    )
    return {
        "session": {
            "id": session.id,
            "stage": session.stage,
            "status": session.status,
            "turn_count": session.turn_count,
            "hint_level": session.hint_level,
            "mastery_score": session.mastery_score,
            "created_at": _iso(session.created_at),
            "updated_at": _iso(session.updated_at),
        },
        "student": {"id": student.id, "name": student.name} if student else None,
        "question": {
            "id": question.id,
            "title": question.title,
            "subject": question.subject,
            "question_text": question.question_text,
            "student_answer": question.student_answer,
            "knowledge_points": question.knowledge_points,
        }
        if question
        else None,
        "diagnosis": {
            "first_error_step": diagnosis.first_error_step,
            "first_error_text": diagnosis.first_error_text,
            "error_type": diagnosis.error_type,
            "root_misconception": diagnosis.root_misconception,
            "confidence": diagnosis.confidence,
            "recommended_strategy": diagnosis.recommended_strategy,
        }
        if diagnosis
        else None,
        "turns": [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "stage": item.stage,
                "time": _iso(item.created_at),
                "decision": sanitize_admin_value(item.metadata_json or {}),
            }
            for item in turns
        ],
        "trace": build_agent_trace(runs, calls),
        "cognitive_updates": [
            {
                "id": item.id,
                "time": _iso(item.created_at),
                "entity_type": item.entity_type,
                "entity_key": item.entity_key,
                "old_value": item.old_value,
                "new_value": item.new_value,
                "reason": item.reason,
            }
            for item in updates
        ],
    }
