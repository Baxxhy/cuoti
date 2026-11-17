"""Existing MySQL schema bootstrap; never initialize a nonempty database."""

import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from .protocol import ApiError

RESOURCES = Path(__file__).parent / "resources"
PRECISION = {
    "002_work_precision": ["student_works"],
    "003_diagnosis_precision": ["diagnoses"],
    "004_tutor_precision": ["tutor_turns"],
    "005_practice_precision": ["practice_recommendations", "dataset_practice_attempts"],
}
SCRIPTS = [
    "006_learning_tasks",
    "007_self_checks",
    "008_task_handwriting",
    "009_task_sources",
    "010_study_sessions",
    "012_personal_learning",
]
INDEXES = {
    "011_bank_browse_index": (
        "ix_bank_browse",
        "usable_for_practice,usable_for_auto_grade,has_answer,subject,id,grade_band,dataset_source_id",
    ),
    "013_bank_grade_index": (
        "ix_bank_grade",
        "usable_for_practice,usable_for_auto_grade,has_answer,grade,subject,id",
    ),
}
VERSIONS = {"001_initial", *PRECISION, *SCRIPTS, *INDEXES}


def script(connection, name):
    # Historical scripts contain simple DDL, no routines or quoted semicolons.
    for statement in (RESOURCES / "schema" / (name + ".sql")).read_text().split(";"):
        if statement.strip():
            connection.execute(text(statement))


def applied(connection):
    return set(
        connection.execute(
            text("SELECT version FROM cangjie_schema_versions")
        ).scalars()
    )


def upgrade(connection):
    versions = applied(connection)
    if "001_initial" not in versions:
        raise ApiError(409, "缺少历史初始版本，不能升级")
    for version, tables in PRECISION.items():
        if version in versions:
            continue
        for table in tables:
            connection.execute(
                text(
                    f"ALTER TABLE {table} MODIFY created_at DATETIME(6) NOT NULL, MODIFY updated_at DATETIME(6) NOT NULL"
                )
            )
        record(connection, version)
    for version in SCRIPTS:
        if version not in versions:
            script(connection, version)
            record(connection, version)
    for version, (name, columns) in INDEXES.items():
        if version in versions:
            continue
        exists = connection.execute(
            text(
                "SELECT INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() "
                "AND TABLE_NAME='dataset_questions' AND INDEX_NAME=:name"
            ),
            {"name": name},
        ).first()
        if exists is None:
            connection.execute(
                text(
                    f"ALTER TABLE dataset_questions ADD INDEX {name} ({columns}), ALGORITHM=INPLACE, LOCK=NONE"
                )
            )
        record(connection, version)


def record(connection, version):
    connection.execute(
        text(
            "INSERT IGNORE INTO cangjie_schema_versions VALUES (:version, UTC_TIMESTAMP())"
        ),
        {"version": version},
    )
    # MySQL DDL commits implicitly; persist each completed historical step.
    connection.commit()


def initialize(connection):
    if (
        connection.execute(
            text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE()"
            )
        ).first()
        is not None
    ):
        raise ApiError(409, "初始化只允许空数据库；已有数据库请使用升级命令")
    script(connection, "001_initial")
    connection.execute(
        text(
            "CREATE TABLE cangjie_schema_versions (version VARCHAR(100) PRIMARY KEY, applied_at DATETIME NOT NULL) ENGINE=InnoDB"
        )
    )
    record(connection, "001_initial")
    upgrade(connection)


def seed(connection):
    data = json.loads((RESOURCES / "knowledge_seed.json").read_text())
    for card in data["cards"]:
        connection.execute(
            text(
                "INSERT INTO knowledge_points (id,code,subject,name,content,created_at,updated_at) "
                "VALUES (:id,:code,:subject,:name,:content,UTC_TIMESTAMP(),UTC_TIMESTAMP()) "
                "ON DUPLICATE KEY UPDATE subject=VALUES(subject),name=VALUES(name),content=VALUES(content),updated_at=UTC_TIMESTAMP()"
            ),
            {
                "id": str(uuid4()),
                **{key: card[key] for key in ["code", "subject", "name"]},
                "content": json.dumps(card["content"], ensure_ascii=False),
            },
        )
    for relation in data["relations"]:
        connection.execute(
            text(
                "INSERT INTO knowledge_relations (id,source_id,target_id,relation_type,created_at,updated_at) "
                "SELECT :id,s.id,t.id,'prerequisite',UTC_TIMESTAMP(),UTC_TIMESTAMP() FROM knowledge_points s "
                "JOIN knowledge_points t ON t.code=:target WHERE s.code=:source AND NOT EXISTS "
                "(SELECT 1 FROM knowledge_relations r WHERE r.source_id=s.id AND r.target_id=t.id AND r.relation_type='prerequisite')"
            ),
            {
                "id": str(uuid4()),
                "target": relation["target"],
                "source": relation["source"],
            },
        )
