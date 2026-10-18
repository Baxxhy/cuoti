"""公共中学题库数据集。"""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0007"
down_revision = "20260808_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "dataset_sources" not in tables:
        op.create_table(
            "dataset_sources",
            sa.Column("key", sa.String(80), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("version", sa.String(100), nullable=False),
            sa.Column("homepage", sa.String(500), nullable=False),
            sa.Column("license", sa.String(100), nullable=False),
            sa.Column("local_path", sa.String(500), nullable=False),
            sa.Column("total_items", sa.Integer(), nullable=False),
            sa.Column("imported_items", sa.Integer(), nullable=False),
            sa.Column("source_metadata", sa.JSON(), nullable=False),
            sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key"),
        )
        op.create_index("ix_dataset_sources_key", "dataset_sources", ["key"])
    if "dataset_questions" not in tables:
        op.create_table(
            "dataset_questions",
            sa.Column("dataset_source_id", sa.String(36), nullable=False),
            sa.Column("source_item_id", sa.String(190), nullable=False),
            sa.Column("split", sa.String(30), nullable=False),
            sa.Column("subject", sa.String(30), nullable=False),
            sa.Column("grade", sa.String(30), nullable=False),
            sa.Column("grade_band", sa.String(30), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("question_type", sa.String(60), nullable=False),
            sa.Column("options", sa.JSON(), nullable=False),
            sa.Column("answer", sa.JSON(), nullable=False),
            sa.Column("solution", sa.Text(), nullable=False),
            sa.Column("knowledge_points", sa.JSON(), nullable=False),
            sa.Column("image_paths", sa.JSON(), nullable=False),
            sa.Column("difficulty", sa.String(30), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("source_metadata", sa.JSON(), nullable=False),
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["dataset_source_id"], ["dataset_sources.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "dataset_source_id", "source_item_id", name="uq_dataset_question_source_item"
            ),
        )
        op.create_index("ix_dataset_questions_dataset_source_id", "dataset_questions", ["dataset_source_id"])
        op.create_index("ix_dataset_questions_subject", "dataset_questions", ["subject"])
        op.create_index("ix_dataset_questions_grade_band", "dataset_questions", ["grade_band"])
        op.create_index("ix_dataset_questions_content_hash", "dataset_questions", ["content_hash"])


def downgrade() -> None:
    op.drop_table("dataset_questions")
    op.drop_table("dataset_sources")
