"""模型作业、执行尝试和可恢复事件。"""
from alembic import op
import sqlalchemy as sa
from sczx_business.models import ModelJob, ModelRun, ModelEvent

revision = "0003_model_jobs"
down_revision = "0002_file_links_and_supplements"
branch_labels = None
depends_on = None


def upgrade():
    for model in (ModelJob, ModelRun, ModelEvent):
        model.__table__.create(op.get_bind(), checkfirst=True)
    for table in ("attempts", "repair_attempts"):
        if "verification" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}:
            op.add_column(table, sa.Column("verification", sa.JSON(), nullable=True))


def downgrade():
    for table in ("attempts", "repair_attempts"):
        op.drop_column(table, "verification")
    for model in (ModelEvent, ModelRun, ModelJob):
        model.__table__.drop(op.get_bind(), checkfirst=True)
