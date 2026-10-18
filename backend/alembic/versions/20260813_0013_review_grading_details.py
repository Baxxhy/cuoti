"""store review grading and handwriting evidence

Revision ID: 20260813_0013
Revises: 20260811_0012
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0013"
down_revision = "20260811_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("review_records")}
    if "grading_details" not in columns:
        op.add_column(
            "review_records",
            sa.Column("grading_details", sa.JSON(), nullable=True),
        )
    op.execute("UPDATE review_records SET grading_details = JSON_OBJECT() WHERE grading_details IS NULL")
    op.alter_column("review_records", "grading_details", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    op.drop_column("review_records", "grading_details")
