"""增加参考步骤验证字段。"""

import sqlalchemy as sa
from alembic import op

revision = "20260807_0003"
down_revision = "20260807_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("reference_steps")}
    if "explanation" in columns:
        return
    op.add_column("reference_steps", sa.Column("explanation", sa.Text(), nullable=True))
    op.add_column(
        "reference_steps", sa.Column("math_valid", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "reference_steps", sa.Column("uses_condition", sa.Boolean(), nullable=False, server_default=sa.true())
    )


def downgrade() -> None:
    pass
