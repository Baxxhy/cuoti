"""add learner question links to shared knowledge graph

Revision ID: 20260813_0016
Revises: 20260813_0015
"""

import sqlalchemy as sa

from alembic import op

revision = "20260813_0016"
down_revision = "20260813_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The app's legacy startup still calls metadata.create_all(). During a hot reload it may
    # create this additive table before Alembic advances its version, so keep the migration
    # safe to resume. Existing installations receive the same schema from the ORM metadata.
    if "user_question_knowledge_links" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "user_question_knowledge_links",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_point_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("mapping_method", sa.String(length=40), nullable=False),
        sa.Column("evidence_text", sa.String(length=255), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "knowledge_point_id", name="uq_user_question_knowledge_link"),
    )
    op.create_index("ix_user_question_knowledge_links_user_id", "user_question_knowledge_links", ["user_id"])
    op.create_index(
        "ix_user_question_knowledge_links_question_id", "user_question_knowledge_links", ["question_id"]
    )
    op.create_index(
        "ix_user_question_knowledge_links_knowledge_point_id",
        "user_question_knowledge_links",
        ["knowledge_point_id"],
    )
    op.create_index("ix_user_question_knowledge_links_role", "user_question_knowledge_links", ["role"])


def downgrade() -> None:
    op.drop_table("user_question_knowledge_links")
