"""add teacher workspace and review evidence

Revision ID: 20260814_0017
Revises: 20260813_0016
"""

import sqlalchemy as sa

from alembic import op

revision = "20260814_0017"
down_revision = "20260813_0016"
branch_labels = None
depends_on = None


def id_time_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    class_columns = {column["name"] for column in inspector.get_columns("teacher_classes")}
    if "grade" not in class_columns:
        op.add_column("teacher_classes", sa.Column("grade", sa.String(30), nullable=False, server_default=""))
    existing_class_constraints = {
        item.get("name") for item in inspector.get_unique_constraints("teacher_class_students")
    }
    if "uq_teacher_class_student" not in existing_class_constraints:
        op.create_unique_constraint(
            "uq_teacher_class_student",
            "teacher_class_students",
            ["class_id", "student_id"],
        )

    if "teacher_questions" not in tables:
        op.create_table(
            "teacher_questions",
            sa.Column(
                "question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=False, unique=True
            ),
            sa.Column("teacher_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("source_type", sa.String(30), nullable=False),
            sa.Column("standard_answer", sa.Text(), nullable=False),
            sa.Column("reference_steps", sa.JSON(), nullable=False),
            sa.Column("scoring_points", sa.JSON(), nullable=False),
            sa.Column("difficulty", sa.String(30), nullable=False),
            sa.Column("allow_auto_grade", sa.Boolean(), nullable=False),
            sa.Column("require_handwriting", sa.Boolean(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            *id_time_columns(),
        )
        op.create_index("ix_teacher_questions_teacher_id", "teacher_questions", ["teacher_id"])
        op.create_index("ix_teacher_questions_question_id", "teacher_questions", ["question_id"])

    if "question_assignments" not in tables:
        op.create_table(
            "question_assignments",
            sa.Column("teacher_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("class_id", sa.String(36), sa.ForeignKey("teacher_classes.id"), nullable=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("settings", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            *id_time_columns(),
        )
        for column in ("teacher_id", "question_id", "class_id"):
            op.create_index(f"ix_question_assignments_{column}", "question_assignments", [column])

    if "assignment_students" not in tables:
        op.create_table(
            "assignment_students",
            sa.Column(
                "assignment_id", sa.String(36), sa.ForeignKey("question_assignments.id"), nullable=False
            ),
            sa.Column("student_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("latest_attempt_id", sa.String(36), nullable=True),
            *id_time_columns(),
            sa.UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),
        )
        for column in ("assignment_id", "student_id"):
            op.create_index(f"ix_assignment_students_{column}", "assignment_students", [column])

    if "assignment_attempts" not in tables:
        op.create_table(
            "assignment_attempts",
            sa.Column(
                "assignment_student_id",
                sa.String(36),
                sa.ForeignKey("assignment_students.id"),
                nullable=False,
            ),
            sa.Column("student_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("steps", sa.JSON(), nullable=False),
            sa.Column("handwriting_asset_ref", sa.String(500), nullable=True),
            sa.Column("grading_details", sa.JSON(), nullable=False),
            sa.Column("verdict", sa.String(30), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            *id_time_columns(),
        )
        for column in ("assignment_student_id", "student_id", "question_id"):
            op.create_index(f"ix_assignment_attempts_{column}", "assignment_attempts", [column])

    if "teacher_review_tasks" not in tables:
        op.create_table(
            "teacher_review_tasks",
            sa.Column("class_id", sa.String(36), sa.ForeignKey("teacher_classes.id"), nullable=False),
            sa.Column("student_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("source_type", sa.String(30), nullable=False),
            sa.Column("source_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("reason_codes", sa.JSON(), nullable=False),
            sa.Column("ai_result", sa.JSON(), nullable=False),
            sa.Column("rule_result", sa.JSON(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("has_conflict", sa.Boolean(), nullable=False),
            sa.Column("assigned_teacher_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("learning_applied", sa.Boolean(), nullable=False),
            *id_time_columns(),
            sa.UniqueConstraint("source_type", "source_id", name="uq_teacher_review_source"),
        )
        for column in ("class_id", "student_id", "question_id", "source_id", "status"):
            op.create_index(f"ix_teacher_review_tasks_{column}", "teacher_review_tasks", [column])

    if "teacher_review_results" not in tables:
        op.create_table(
            "teacher_review_results",
            sa.Column("task_id", sa.String(36), sa.ForeignKey("teacher_review_tasks.id"), nullable=False),
            sa.Column("teacher_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("conclusion", sa.String(30), nullable=False),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("first_key_error", sa.Text(), nullable=False),
            sa.Column("error_type", sa.String(80), nullable=False),
            sa.Column("propagated_error", sa.Boolean(), nullable=False),
            sa.Column("student_hint", sa.Text(), nullable=False),
            sa.Column("next_task", sa.Text(), nullable=False),
            sa.Column("mastered_steps", sa.JSON(), nullable=False),
            sa.Column("allow_learning_update", sa.Boolean(), nullable=False),
            sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
            sa.Column("learning_snapshot", sa.JSON(), nullable=False),
            sa.Column(
                "supersedes_id", sa.String(36), sa.ForeignKey("teacher_review_results.id"), nullable=True
            ),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            *id_time_columns(),
        )
        for column in ("task_id", "teacher_id"):
            op.create_index(f"ix_teacher_review_results_{column}", "teacher_review_results", [column])

    if "teacher_audit_logs" not in tables:
        op.create_table(
            "teacher_audit_logs",
            sa.Column("teacher_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("action", sa.String(80), nullable=False),
            sa.Column("target_type", sa.String(50), nullable=False),
            sa.Column("target_id", sa.String(36), nullable=False),
            sa.Column("before_json", sa.JSON(), nullable=False),
            sa.Column("after_json", sa.JSON(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            *id_time_columns(),
        )
        for column in ("teacher_id", "action", "target_id"):
            op.create_index(f"ix_teacher_audit_logs_{column}", "teacher_audit_logs", [column])


def downgrade() -> None:
    for table in (
        "teacher_audit_logs",
        "teacher_review_results",
        "teacher_review_tasks",
        "assignment_attempts",
        "assignment_students",
        "question_assignments",
        "teacher_questions",
    ):
        op.drop_table(table)
    op.drop_column("teacher_classes", "grade")
    op.drop_constraint("uq_teacher_class_student", "teacher_class_students", type_="unique")
