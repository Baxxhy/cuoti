"""允许识别阶段保留无法判断的年级和学生答案。"""

import sqlalchemy as sa
from alembic import op

revision = "20260811_0010"
down_revision = "20260810_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "questions",
        "grade",
        existing_type=sa.String(length=30),
        nullable=True,
        existing_server_default=None,
    )
    op.alter_column(
        "questions",
        "student_answer",
        existing_type=sa.Text(),
        nullable=True,
        existing_server_default=None,
    )


def downgrade() -> None:
    op.execute("UPDATE questions SET grade = '初二' WHERE grade IS NULL")
    op.execute("UPDATE questions SET student_answer = '' WHERE student_answer IS NULL")
    op.alter_column(
        "questions",
        "student_answer",
        existing_type=sa.Text(),
        nullable=False,
        existing_server_default=None,
    )
    op.alter_column(
        "questions",
        "grade",
        existing_type=sa.String(length=30),
        nullable=False,
        existing_server_default=None,
    )
