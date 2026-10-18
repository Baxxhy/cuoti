"""清理旧版本数据库结构。"""

import sqlalchemy as sa
from alembic import op

revision = "20260810_0009"
down_revision = "20260809_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "cognitive_updates" in tables:
        columns = {column["name"] for column in inspector.get_columns("cognitive_updates")}
        if "note_id" in columns:
            for foreign_key in inspector.get_foreign_keys("cognitive_updates"):
                if foreign_key.get("constrained_columns") == ["note_id"] and foreign_key.get("name"):
                    op.drop_constraint(foreign_key["name"], "cognitive_updates", type_="foreignkey")
            op.drop_column("cognitive_updates", "note_id")

    for table in (
        "note_processing_jobs",
        "note_knowledge_evidence",
        "note_blocks",
        "note_pages",
        "note_documents",
    ):
        if table in tables:
            op.drop_table(table)


def downgrade() -> None:
    pass
