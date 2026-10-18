"""Remove the unused PaddleOCR evidence table and legacy defaults."""

import sqlalchemy as sa
from alembic import op

revision = "20260825_0017"
down_revision = "20260813_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "question_blocks" in inspector.get_table_names():
        op.drop_table("question_blocks")
    op.alter_column("ocr_runs", "stream", existing_type=sa.String(30), server_default="qwen_crop")
    op.alter_column("student_steps", "source", existing_type=sa.String(50), server_default="qwen_crop")


def downgrade() -> None:
    op.create_table(
        "question_blocks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=False, index=True),
        sa.Column("block_type", sa.String(30), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reading_order", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("low_confidence", sa.Boolean(), nullable=False),
    )
    op.alter_column("ocr_runs", "stream", existing_type=sa.String(30), server_default="fused")
    op.alter_column("student_steps", "source", existing_type=sa.String(50), server_default="ocr_fusion")
