from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Diagnosis,
    KnowledgePoint,
    ProblemAnalysis,
    Question,
    UserQuestionKnowledgeLink,
)


def _normal(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value).lower())


def _phrases(
    question: Question, analysis: ProblemAnalysis | None, diagnosis: Diagnosis | None
) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    values.extend((str(item), "primary") for item in (question.knowledge_points or []))
    if analysis:
        values.extend((str(item), "primary") for item in (analysis.knowledge_points or []))
        values.extend((str(item), "prerequisite") for item in (analysis.prerequisites or []))
    if diagnosis:
        values.extend((str(item), "prerequisite") for item in (diagnosis.missing_prerequisites or []))
    seen: set[tuple[str, str]] = set()
    phrases: list[tuple[str, str]] = []
    for item in values:
        if item[0].strip() and item not in seen:
            seen.add(item)
            phrases.append(item)
    return phrases


def match_knowledge_points(
    phrases: Iterable[tuple[str, str]],
    cards: Iterable[KnowledgePoint],
) -> list[dict[str, Any]]:
    """Conservatively associate labels with existing cards; never create graph nodes."""
    card_rows = list(cards)
    selected: dict[str, dict[str, Any]] = {}
    role_rank = {"prerequisite": 1, "primary": 2}
    for phrase, role in phrases:
        needle = _normal(phrase)
        if len(needle) < 2:
            continue
        candidates: list[tuple[float, str, KnowledgePoint]] = []
        for card in card_rows:
            names = [card.name, card.code]
            content = card.content or {}
            names.extend(str(item) for item in content.get("related_knowledge", []))
            normalized = [_normal(value) for value in names if value]
            if needle in normalized:
                candidates.append((1.0, "exact_label", card))
            elif any(len(value) >= 2 and (value in needle or needle in value) for value in normalized):
                candidates.append((0.86, "contained_label", card))
        if not candidates:
            continue
        confidence, method, card = max(candidates, key=lambda item: (item[0], len(_normal(item[2].name))))
        old = selected.get(card.id)
        candidate = {
            "knowledge_point_id": card.id,
            "role": role,
            "confidence": confidence,
            "mapping_method": method,
            "evidence_text": phrase[:255],
        }
        if old is None or (role_rank.get(role, 0), confidence) > (
            role_rank.get(old["role"], 0),
            old["confidence"],
        ):
            selected[card.id] = candidate
    return list(selected.values())


async def sync_personal_knowledge_links(
    db: AsyncSession,
    question: Question,
    analysis: ProblemAnalysis | None,
    diagnosis: Diagnosis | None = None,
) -> list[UserQuestionKnowledgeLink]:
    cards = list(await db.scalars(select(KnowledgePoint).where(KnowledgePoint.subject == question.subject)))
    matches = match_knowledge_points(_phrases(question, analysis, diagnosis), cards)
    existing = {
        item.knowledge_point_id: item
        for item in await db.scalars(
            select(UserQuestionKnowledgeLink).where(
                UserQuestionKnowledgeLink.question_id == question.id,
            )
        )
    }
    result: list[UserQuestionKnowledgeLink] = []
    for match in matches:
        item = existing.get(match["knowledge_point_id"])
        if item is None:
            item = UserQuestionKnowledgeLink(
                user_id=question.user_id,
                question_id=question.id,
                **match,
            )
            db.add(item)
        else:
            item.role = match["role"]
            item.confidence = match["confidence"]
            item.mapping_method = match["mapping_method"]
            item.evidence_text = match["evidence_text"]
        result.append(item)
    await db.flush()
    return result
