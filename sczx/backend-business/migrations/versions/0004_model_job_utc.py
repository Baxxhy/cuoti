"""模型任务时间统一为 UTC，历史教学数据保持原格式。"""
from alembic import op
from sqlalchemy import text

revision = "0004_model_job_utc"
down_revision = "0003_model_jobs"
branch_labels = None
depends_on = None


def shift(direction):
    connection = op.get_bind()
    offset = int(connection.scalar(text("SELECT TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), NOW())")))
    if offset:
        for table, columns in (("model_jobs", ("created_at", "updated_at")), ("model_runs", ("started_at",)), ("model_events", ("created_at",))):
            assignments = ", ".join(f"`{column}` = TIMESTAMPADD(SECOND, :offset, `{column}`)" for column in columns)
            connection.execute(text(f"UPDATE `{table}` SET {assignments}"), {"offset": direction * offset})


def upgrade():
    shift(-1)


def downgrade():
    shift(1)
