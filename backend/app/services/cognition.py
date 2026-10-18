from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CognitiveUpdate, MasteryState, MisconceptionState
from app.services.cognition_rules import CognitionTarget as CognitionTarget
from app.services.cognition_rules import cognition_target as cognition_target
from app.services.cognition_rules import compute_cognition


async def update_cognition(
    db: AsyncSession,
    user_id: str,
    question_id: str,
    evidence: dict[str, Any],
    *,
    subject: str,
    knowledge_point: str,
    misconception_code: str,
    misconception_label: str | None = None,
) -> tuple[MasteryState, MisconceptionState]:
    subject = subject.strip()
    knowledge_point = knowledge_point.strip()
    misconception_code = misconception_code.strip()
    if not subject or not knowledge_point or not misconception_code:
        raise ValueError("认知更新必须明确提供学科、知识点和错因编码")
    mastery = (
        await db.scalars(
            select(MasteryState)
            .where(
                MasteryState.user_id == user_id,
                MasteryState.subject == subject,
                MasteryState.knowledge_point == knowledge_point,
            )
            .order_by(MasteryState.updated_at.desc())
        )
    ).first()
    if mastery is None:
        mastery = MasteryState(user_id=user_id, subject=subject, knowledge_point=knowledge_point)
        db.add(mastery)
        await db.flush()
    misconception = (
        await db.scalars(
            select(MisconceptionState)
            .where(
                MisconceptionState.user_id == user_id,
                MisconceptionState.subject == subject,
                MisconceptionState.code == misconception_code,
            )
            .order_by(MisconceptionState.updated_at.desc())
        )
    ).first()
    if misconception is None:
        misconception = MisconceptionState(
            user_id=user_id,
            subject=subject,
            code=misconception_code,
            label=misconception_label or misconception_code,
            first_seen_at=datetime.now(timezone.utc),
        )
        db.add(misconception)
        await db.flush()

    old_mastery = mastery.mastery_score
    old_probability = misconception.probability
    mastery_values, misconception_values = compute_cognition(
        {
            key: getattr(mastery, key)
            for key in [
                "mastery_score",
                "evidence_count",
                "confidence",
                "near_transfer_rate",
                "far_transfer_rate",
                "forgetting_risk",
                "update_reason",
            ]
        },
        {
            key: getattr(misconception, key)
            for key in [
                "probability",
                "evidence_count",
                "related_question_count",
                "label",
                "status",
                "successful_strategy",
                "failed_strategy",
            ]
        },
        evidence,
        misconception_label,
    )
    for key, value in mastery_values.items():
        setattr(mastery, key, value)
    for key, value in misconception_values.items():
        setattr(misconception, key, value)
    mastery.last_evidence_at = datetime.now(timezone.utc)
    misconception.last_seen_at = datetime.now(timezone.utc)

    db.add_all(
        [
            CognitiveUpdate(
                user_id=user_id,
                question_id=question_id,
                entity_type="mastery",
                entity_key=knowledge_point,
                old_value=old_mastery,
                new_value=mastery.mastery_score,
                evidence=evidence,
                reason=mastery.update_reason,
            ),
            CognitiveUpdate(
                user_id=user_id,
                question_id=question_id,
                entity_type="misconception",
                entity_key=misconception_code,
                old_value=old_probability,
                new_value=misconception.probability,
                evidence=evidence,
                reason=mastery.update_reason,
            ),
        ]
    )
    return mastery, misconception
