"""为题目视觉区域保存角色、坐标和客观描述。"""

import sqlalchemy as sa
from alembic import op

revision = "20260811_0011"
down_revision = "20260811_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("question_assets")}
    if "role" not in columns:
        op.add_column("question_assets", sa.Column("role", sa.String(length=40), nullable=True))
    if "bbox" not in columns:
        op.add_column("question_assets", sa.Column("bbox", sa.JSON(), nullable=True))
    if "description" not in columns:
        op.add_column("question_assets", sa.Column("description", sa.Text(), nullable=True))
    op.execute("UPDATE question_assets SET bbox = JSON_ARRAY() WHERE bbox IS NULL")
    op.alter_column("question_assets", "bbox", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    op.drop_column("question_assets", "description")
    op.drop_column("question_assets", "bbox")
    op.drop_column("question_assets", "role")
