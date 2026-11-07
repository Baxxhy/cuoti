"""为求助题图建立关联，并持久化教师补充学习。"""

from alembic import op
from sqlalchemy import inspect

from sczx_business.models import SupplementalInstruction

revision = "0002_file_links_and_supplements"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    SupplementalInstruction.__table__.create(bind=connection, checkfirst=True)

    for table, name in (
        ("help_records", "fk_help_records_file_id_file_assets"),
        ("wrong_questions", "fk_wrong_questions_file_id_file_assets"),
    ):
        if table not in tables:
            continue
        foreign_keys = inspector.get_foreign_keys(table)
        if any(fk.get("constrained_columns") == ["file_id"] for fk in foreign_keys):
            continue
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "file_id" in columns and "file_assets" in tables:
            op.create_foreign_key(
                name,
                table,
                "file_assets",
                ["file_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    for table, name in (
        ("help_records", "fk_help_records_file_id_file_assets"),
        ("wrong_questions", "fk_wrong_questions_file_id_file_assets"),
    ):
        if table in inspector.get_table_names():
            if any(fk.get("name") == name for fk in inspector.get_foreign_keys(table)):
                op.drop_constraint(name, table, type_="foreignkey")
    SupplementalInstruction.__table__.drop(bind=connection, checkfirst=True)
