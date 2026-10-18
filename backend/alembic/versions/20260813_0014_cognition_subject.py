"""scope cognition states by subject

Revision ID: 20260813_0014
Revises: 20260813_0013
"""

import sqlalchemy as sa

from alembic import op

revision = "20260813_0014"
down_revision = "20260813_0013"
branch_labels = None
depends_on = None


def _backfill_subject(table: str) -> None:
    op.execute(f"""
        UPDATE {table} state
        JOIN (
            SELECT cu.user_id, cu.entity_key, MIN(q.subject) AS subject
            FROM cognitive_updates cu
            JOIN questions q ON q.id = cu.question_id
            WHERE cu.entity_type = '{"mastery" if table == "mastery_states" else "misconception"}'
            GROUP BY cu.user_id, cu.entity_key
            HAVING COUNT(DISTINCT q.subject) = 1
        ) evidence
          ON evidence.user_id = state.user_id
         AND evidence.entity_key = {"state.knowledge_point" if table == "mastery_states" else "state.code"}
        SET state.subject = evidence.subject
        WHERE state.subject IS NULL
    """)
    key_column = "knowledge_point" if table == "mastery_states" else "code"
    op.execute(f"""
        UPDATE {table} state
        JOIN (
            SELECT name, MIN(subject) AS subject
            FROM knowledge_points
            GROUP BY name
            HAVING COUNT(DISTINCT subject) = 1
        ) knowledge ON knowledge.name = state.{key_column}
        SET state.subject = knowledge.subject
        WHERE state.subject IS NULL
    """)
    op.execute(f"""
        UPDATE {table} state
        JOIN (
            SELECT user_id, MIN(subject) AS subject
            FROM questions
            GROUP BY user_id
            HAVING COUNT(DISTINCT subject) = 1
        ) learner ON learner.user_id = state.user_id
        SET state.subject = learner.subject
        WHERE state.subject IS NULL
    """)
    op.execute(f"UPDATE {table} SET subject = '未分类' WHERE subject IS NULL")


def upgrade() -> None:
    for table in ("mastery_states", "misconception_states"):
        inspector = sa.inspect(op.get_bind())
        columns = {item["name"] for item in inspector.get_columns(table)}
        indexes = {item["name"] for item in inspector.get_indexes(table)}
        if "subject" not in columns:
            op.add_column(table, sa.Column("subject", sa.String(length=30), nullable=True))
        _backfill_subject(table)
        op.alter_column(table, "subject", existing_type=sa.String(length=30), nullable=False)
        if f"ix_{table}_subject" not in indexes:
            op.create_index(f"ix_{table}_subject", table, ["subject"])


def downgrade() -> None:
    for table in ("misconception_states", "mastery_states"):
        op.drop_index(f"ix_{table}_subject", table_name=table)
        op.drop_column(table, "subject")
