"""Existing MySQL contracts through SQLAlchemy, with no schema changes."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

TYPES = json.loads((Path(__file__).parent / "resources/row_types.json").read_text())


def execute(db, sql, params=()):
    for index in range(len(params)):
        sql = sql.replace("?", f":p{index}", 1)
    return db.execute(text(sql), {f"p{i}": value for i, value in enumerate(params)})


def rows(db, sql, params=()):
    return [dict(row) for row in execute(db, sql, params).mappings()]


def serialize(table, row):
    result = {}
    for key, value in row.items():
        kind = TYPES.get(table, {}).get(key)
        if value is None:
            result[key] = None
        elif kind == "json":
            result[key] = json.loads(value) if isinstance(value, str) else value
        elif kind == "bool":
            result[key] = bool(int(value))
        elif isinstance(value, datetime):
            result[key] = value.replace(tzinfo=timezone.utc).isoformat()
        elif isinstance(value, Decimal) or kind == "float":
            result[key] = float(value)
        else:
            result[key] = value
    if table == "questions":
        title, content = result.get("title", ""), result.get("question_text", "")
        if (
            title
            and content != title
            and content.startswith(title)
            and ("$" in title or "\\" in title)
        ):
            result["title"] = content
    return result


def select_rows(db, table, sql, params=()):
    return [serialize(table, row) for row in rows(db, sql, params)]


def insert(db, table, *, timestamp_microseconds=True, **values):
    timestamp = "UTC_TIMESTAMP(6)" if timestamp_microseconds else "UTC_TIMESTAMP()"
    if table not in TYPES or set(values) - set(TYPES[table]):
        raise ValueError("Unknown persistence field")
    values.setdefault("id", str(uuid4()))
    columns = ",".join(f"`{key}`" for key in values)
    encoded = [
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        if TYPES[table].get(key) == "json"
        else value
        for key, value in values.items()
    ]
    execute(
        db,
        f"INSERT INTO `{table}` ({columns},created_at,updated_at) VALUES ({','.join('?' for _ in encoded)},{timestamp},{timestamp})",
        encoded,
    )
    return values["id"]


def update(db, table, id, *, timestamp_microseconds=True, **values):
    timestamp = "UTC_TIMESTAMP(6)" if timestamp_microseconds else "UTC_TIMESTAMP()"
    if table not in TYPES or set(values) - set(TYPES[table]):
        raise ValueError("Unknown persistence field")
    encoded = [
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        if TYPES[table].get(key) == "json"
        else value
        for key, value in values.items()
    ]
    execute(
        db,
        f"UPDATE `{table}` SET "
        + ",".join(f"`{key}`=?" for key in values)
        + f",updated_at={timestamp} WHERE id=?",
        [*encoded, id],
    )


def owned(db, id, owner, *, lock=False):
    from .protocol import ApiError

    items = select_rows(
        db,
        "questions",
        "SELECT * FROM questions WHERE id=? AND user_id=?"
        + (" FOR UPDATE" if lock else ""),
        [id, owner],
    )
    if not items:
        raise ApiError(404, "内容不存在或无权访问")
    return items[0]


def invalidate(db, id):
    preserve_references(db, id, "question_changed")
    statements = [
        "DELETE e FROM diagnosis_evidence e JOIN diagnoses d ON e.diagnosis_id=d.id WHERE d.question_id=?",
        "DELETE FROM diagnoses WHERE question_id=?",
        "DELETE s FROM reference_steps s JOIN problem_analyses a ON s.analysis_id=a.id WHERE a.question_id=?",
        "DELETE FROM problem_analyses WHERE question_id=?",
        "DELETE FROM user_question_knowledge_links WHERE question_id=?",
        "DELETE FROM practice_recommendations WHERE mistake_id=?",
        "UPDATE tutor_sessions SET state=JSON_SET(IF(JSON_TYPE(state)='OBJECT',state,JSON_OBJECT()),'$.question_changed',CAST('true' AS JSON)),updated_at=UTC_TIMESTAMP() WHERE question_id=?",
        "UPDATE review_plans SET status='cancelled',updated_at=UTC_TIMESTAMP() WHERE question_id=? AND status='pending'",
        "UPDATE dataset_practice_attempts SET grading_details=JSON_SET(IF(JSON_TYPE(grading_details)='OBJECT',grading_details,JSON_OBJECT()),'$.question_changed',CAST('true' AS JSON)),updated_at=UTC_TIMESTAMP() WHERE mistake_id=?",
        "UPDATE review_records r JOIN review_plans p ON r.plan_id=p.id SET r.grading_details=JSON_SET(IF(JSON_TYPE(r.grading_details)='OBJECT',r.grading_details,JSON_OBJECT()),'$.question_changed',CAST('true' AS JSON)),r.updated_at=UTC_TIMESTAMP() WHERE p.question_id=?",
    ]
    for sql in statements:
        execute(db, sql, [id])


def preserve_references(db, id, reason):
    """Keep removed derived records in the existing JSON audit table."""
    analysis = select_rows(
        db,
        "problem_analyses",
        "SELECT * FROM problem_analyses WHERE question_id=?",
        [id],
    )
    diagnoses = select_rows(
        db, "diagnoses", "SELECT * FROM diagnoses WHERE question_id=?", [id]
    )
    if not analysis and not diagnoses:
        return
    reference_steps = select_rows(
        db,
        "reference_steps",
        "SELECT r.* FROM reference_steps r JOIN problem_analyses a ON r.analysis_id=a.id WHERE a.question_id=? ORDER BY r.step_index",
        [id],
    )
    evidence = select_rows(
        db,
        "diagnosis_evidence",
        "SELECT e.* FROM diagnosis_evidence e JOIN diagnoses d ON e.diagnosis_id=d.id WHERE d.question_id=?",
        [id],
    )
    question = select_rows(db, "questions", "SELECT * FROM questions WHERE id=?", [id])[
        0
    ]
    assets = select_rows(
        db, "question_assets", "SELECT * FROM question_assets WHERE question_id=?", [id]
    )
    insert(
        db,
        "agent_runs",
        session_id=None,
        agent_name="question_revision",
        status="completed",
        result={
            "question_id": id,
            "reason": reason,
            "question": question,
            "assets": assets,
            "analysis": analysis,
            "reference_steps": reference_steps,
            "diagnoses": diagnoses,
            "evidence": evidence,
        },
    )
