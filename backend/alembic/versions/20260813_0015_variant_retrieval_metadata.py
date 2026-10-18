"""store tutor variant retrieval provenance

Revision ID: 20260813_0015
Revises: 20260813_0014
"""

import sqlalchemy as sa

from alembic import op

revision = "20260813_0015"
down_revision = "20260813_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("variant_questions")}
    if "generation_metadata" not in columns:
        op.add_column(
            "variant_questions",
            sa.Column("generation_metadata", sa.JSON(), nullable=True),
        )
    op.execute(
        "UPDATE variant_questions SET generation_metadata = JSON_OBJECT() WHERE generation_metadata IS NULL"
    )
    op.alter_column(
        "variant_questions",
        "generation_metadata",
        existing_type=sa.JSON(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("variant_questions", "generation_metadata")
