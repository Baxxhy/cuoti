from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import mysql

from app.services.knowledge_base import search_knowledge_cards


@pytest.mark.asyncio
async def test_grade_and_misconception_are_filtered_before_limit():
    db = AsyncMock()
    db.scalars.return_value = []
    assert await search_knowledge_cards(db, grade="高三", misconception="适用条件", limit=50) == []
    statement = db.scalars.call_args.args[0]
    compiled = statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True})
    sql = str(compiled)
    where = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    assert "高三" in where
    assert "适用条件" in where
    assert "LIMIT 50" in sql
