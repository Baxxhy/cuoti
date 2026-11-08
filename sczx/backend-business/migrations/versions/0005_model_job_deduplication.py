"""数据库保证同账号同输入至多一个进行中模型任务。"""
from alembic import op
import sqlalchemy as sa

revision = "0005_model_job_deduplication"
down_revision = "0004_model_job_utc"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "active_hash" not in {c["name"] for c in inspector.get_columns("model_jobs")}:
        op.add_column("model_jobs", sa.Column("active_hash", sa.String(64), nullable=True))
        connection.execute(sa.text("UPDATE model_jobs SET active_hash=input_hash WHERE status IN ('queued','running')"))
    if "uq_model_job_active_input" not in {item["name"] for item in sa.inspect(connection).get_unique_constraints("model_jobs")}:
        op.create_unique_constraint("uq_model_job_active_input", "model_jobs", ["owner_id", "active_hash"])


def downgrade():
    op.drop_constraint("uq_model_job_active_input", "model_jobs", type_="unique")
    op.drop_column("model_jobs", "active_hash")
