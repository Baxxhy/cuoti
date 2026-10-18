from __future__ import annotations

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgePoint


async def search_knowledge_cards(
    db: AsyncSession,
    query: str = "",
    subject: str | None = None,
    grade: str | None = None,
    misconception: str | None = None,
    limit: int = 10,
) -> list[KnowledgePoint]:
    statement = select(KnowledgePoint)
    if subject:
        statement = statement.where(KnowledgePoint.subject == subject)
    words = [word for word in query.replace("，", " ").replace("、", " ").split() if len(word) >= 2]
    if words:
        statement = statement.where(
            or_(
                *[
                    or_(
                        KnowledgePoint.name.contains(word),
                        KnowledgePoint.code.contains(word),
                        KnowledgePoint.content.contains(word),
                    )
                    for word in words[:5]
                ]
            )
        )
    if grade:
        statement = statement.where(KnowledgePoint.content["grade"].as_string().contains(grade))
    if misconception:
        statement = statement.where(
            cast(KnowledgePoint.content["common_misconceptions"], Text).contains(misconception)
        )
    return list(
        await db.scalars(statement.order_by(KnowledgePoint.subject, KnowledgePoint.code).limit(limit))
    )
