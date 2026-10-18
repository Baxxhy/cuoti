"""错因驱动的自适应练习。"""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0008"
down_revision = "20260809_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("dataset_questions")}
    indexes = {item["name"] for item in inspector.get_indexes("dataset_questions")}
    for name, column in (
        ("has_answer", sa.Column("has_answer", sa.Boolean(), nullable=False, server_default="0")),
        ("has_solution", sa.Column("has_solution", sa.Boolean(), nullable=False, server_default="0")),
        ("answer_verified", sa.Column("answer_verified", sa.Boolean(), nullable=False, server_default="0")),
        (
            "quality_status",
            sa.Column("quality_status", sa.String(30), nullable=False, server_default="pending"),
        ),
        (
            "usable_for_practice",
            sa.Column("usable_for_practice", sa.Boolean(), nullable=False, server_default="0"),
        ),
        (
            "usable_for_auto_grade",
            sa.Column("usable_for_auto_grade", sa.Boolean(), nullable=False, server_default="0"),
        ),
    ):
        if name not in columns:
            op.add_column("dataset_questions", column)
        if name not in {"has_solution", "answer_verified"} and f"ix_dataset_questions_{name}" not in indexes:
            op.create_index(f"ix_dataset_questions_{name}", "dataset_questions", [name])

    if "question_knowledge_links" not in tables:
        op.create_table(
            "question_knowledge_links",
            sa.Column("dataset_question_id", sa.String(36), nullable=False),
            sa.Column("knowledge_point_id", sa.String(36), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("mapping_method", sa.String(40), nullable=False),
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["dataset_question_id"], ["dataset_questions.id"]),
            sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"]),
            sa.UniqueConstraint(
                "dataset_question_id", "knowledge_point_id", name="uq_question_knowledge_link"
            ),
        )
        for name in ("dataset_question_id", "knowledge_point_id", "role"):
            op.create_index(f"ix_question_knowledge_links_{name}", "question_knowledge_links", [name])

    if "practice_recommendations" not in tables:
        op.create_table(
            "practice_recommendations",
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("mistake_id", sa.String(36), nullable=False),
            sa.Column("dataset_question_id", sa.String(36), nullable=False),
            sa.Column("mode", sa.String(20), nullable=False),
            sa.Column("retrieval_rank", sa.Integer(), nullable=False),
            sa.Column("retrieval_trace", sa.JSON(), nullable=False),
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["mistake_id"], ["questions.id"]),
            sa.ForeignKeyConstraint(["dataset_question_id"], ["dataset_questions.id"]),
        )
        for name in ("user_id", "mistake_id", "dataset_question_id", "mode"):
            op.create_index(f"ix_practice_recommendations_{name}", "practice_recommendations", [name])

    if "dataset_practice_attempts" not in tables:
        op.create_table(
            "dataset_practice_attempts",
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("mistake_id", sa.String(36), nullable=False),
            sa.Column("dataset_question_id", sa.String(36), nullable=False),
            sa.Column("source_dataset", sa.String(80), nullable=False),
            sa.Column("knowledge_id", sa.String(36), nullable=True),
            sa.Column("mode", sa.String(20), nullable=False),
            sa.Column("student_answer", sa.JSON(), nullable=False),
            sa.Column("correct", sa.Boolean(), nullable=False),
            sa.Column("duration_seconds", sa.Integer(), nullable=False),
            sa.Column("grading_details", sa.JSON(), nullable=False),
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["mistake_id"], ["questions.id"]),
            sa.ForeignKeyConstraint(["dataset_question_id"], ["dataset_questions.id"]),
            sa.ForeignKeyConstraint(["knowledge_id"], ["knowledge_points.id"]),
        )
        for name in ("user_id", "mistake_id", "dataset_question_id", "source_dataset", "mode"):
            op.create_index(f"ix_dataset_practice_attempts_{name}", "dataset_practice_attempts", [name])


def downgrade() -> None:
    op.drop_table("dataset_practice_attempts")
    op.drop_table("practice_recommendations")
    op.drop_table("question_knowledge_links")
    for name in (
        "usable_for_auto_grade",
        "usable_for_practice",
        "quality_status",
        "answer_verified",
        "has_solution",
        "has_answer",
    ):
        op.drop_column("dataset_questions", name)
