"""扩展双流OCR、诊断证据、认知更新和语音记录。"""

import sqlalchemy as sa
from alembic import op

revision = "20260807_0002"
down_revision = "20260807_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 是早期的 metadata.create_all 迁移：全新安装会直接按当前模型建表。
    # 若扩展列已经存在，结构也已完整，只需让 Alembic 推进版本号。
    question_columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("questions")}
    if "formulas" in question_columns:
        return
    for name in ("formulas", "options", "knowledge_points"):
        op.add_column("questions", sa.Column(name, sa.JSON(), nullable=True))
    op.add_column(
        "questions", sa.Column("question_type", sa.String(50), nullable=False, server_default="综合题")
    )

    op.add_column("ocr_runs", sa.Column("stream", sa.String(30), nullable=False, server_default="fused"))
    op.add_column("ocr_runs", sa.Column("status", sa.String(30), nullable=False, server_default="completed"))
    op.add_column("ocr_runs", sa.Column("model_name", sa.String(120), nullable=False, server_default=""))
    op.add_column("ocr_runs", sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ocr_runs", sa.Column("error", sa.Text(), nullable=True))

    op.add_column(
        "question_blocks", sa.Column("reading_order", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "question_blocks", sa.Column("source", sa.String(50), nullable=False, server_default="paddle")
    )
    op.add_column(
        "question_blocks",
        sa.Column("low_confidence", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column("student_steps", sa.Column("raw_text", sa.Text(), nullable=True))
    op.add_column("student_steps", sa.Column("normalized_text", sa.Text(), nullable=True))
    op.add_column("student_steps", sa.Column("formula", sa.Text(), nullable=True))
    op.add_column("student_steps", sa.Column("confidence", sa.Float(), nullable=False, server_default="0"))
    op.add_column(
        "student_steps", sa.Column("source", sa.String(50), nullable=False, server_default="ocr_fusion")
    )
    op.add_column(
        "student_steps", sa.Column("user_confirmed", sa.Boolean(), nullable=False, server_default=sa.false())
    )

    op.add_column("diagnoses", sa.Column("error_location", sa.Text(), nullable=True))
    op.add_column("diagnoses", sa.Column("missing_prerequisites", sa.JSON(), nullable=True))
    op.add_column("diagnoses", sa.Column("recommended_strategy", sa.Text(), nullable=True))
    op.add_column(
        "diagnoses", sa.Column("user_confirmed", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("diagnoses", sa.Column("correction", sa.JSON(), nullable=True))

    for name in ("reference_step_id", "student_step_id"):
        target = "reference_steps.id" if name.startswith("reference") else "student_steps.id"
        op.add_column(
            "diagnosis_evidence", sa.Column(name, sa.String(36), sa.ForeignKey(target), nullable=True)
        )
    op.add_column(
        "diagnosis_evidence",
        sa.Column("alignment", sa.String(50), nullable=False, server_default="unmatched"),
    )
    for name in ("equivalent", "uses_condition", "is_first_error", "propagated", "math_valid"):
        op.add_column(
            "diagnosis_evidence", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.add_column("diagnosis_evidence", sa.Column("metadata_json", sa.JSON(), nullable=True))

    op.add_column("variant_questions", sa.Column("reference_solution", sa.JSON(), nullable=True))
    op.add_column(
        "variant_questions", sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "variant_attempts", sa.Column("elapsed_seconds", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "variant_attempts", sa.Column("hint_level", sa.Integer(), nullable=False, server_default="0")
    )

    for name in ("near_transfer_rate", "far_transfer_rate"):
        op.add_column("mastery_states", sa.Column(name, sa.Float(), nullable=False, server_default="0"))
    op.add_column(
        "mastery_states", sa.Column("forgetting_risk", sa.Float(), nullable=False, server_default="0.5")
    )
    op.add_column("mastery_states", sa.Column("last_evidence_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mastery_states", sa.Column("update_reason", sa.Text(), nullable=True))

    op.add_column(
        "misconception_states",
        sa.Column("related_question_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("misconception_states", sa.Column("successful_strategy", sa.Text(), nullable=True))
    op.add_column("misconception_states", sa.Column("failed_strategy", sa.Text(), nullable=True))
    op.add_column(
        "misconception_states", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "misconception_states", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("paper_items", sa.Column("score", sa.Integer(), nullable=False, server_default="10"))

    op.create_table(
        "teacher_marks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=False, index=True),
        sa.Column("mark_type", sa.String(50), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
    )
    op.create_table(
        "cognitive_updates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=True),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_key", sa.String(120), nullable=False),
        sa.Column("old_value", sa.Float(), nullable=False),
        sa.Column("new_value", sa.Float(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_table(
        "voice_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=True),
        sa.Column("work_id", sa.String(36), sa.ForeignKey("student_works.id"), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("audio_path", sa.String(500), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("voice_records")
    op.drop_table("cognitive_updates")
    op.drop_table("teacher_marks")
    # 本地功能版不执行破坏性列回滚；重建测试数据库可回到初始迁移。
