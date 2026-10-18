"""保存复习作答、判定和反馈。"""

import sqlalchemy as sa
from alembic import op

revision = "20260808_0004"
down_revision = "20260807_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("review_records")}
    if "student_answer" not in columns:
        op.add_column("review_records", sa.Column("student_answer", sa.Text(), nullable=True))
        op.add_column("review_records", sa.Column("expected_answer", sa.Text(), nullable=True))
        op.add_column("review_records", sa.Column("feedback", sa.Text(), nullable=True))
        op.add_column("review_records", sa.Column("score", sa.Integer(), nullable=True))
        op.execute("UPDATE review_records SET student_answer='', expected_answer='', feedback='', score=0")
        op.alter_column("review_records", "student_answer", existing_type=sa.Text(), nullable=False)
        op.alter_column("review_records", "expected_answer", existing_type=sa.Text(), nullable=False)
        op.alter_column("review_records", "feedback", existing_type=sa.Text(), nullable=False)
        op.alter_column("review_records", "score", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.drop_column("review_records", "score")
    op.drop_column("review_records", "feedback")
    op.drop_column("review_records", "expected_answer")
    op.drop_column("review_records", "student_answer")
