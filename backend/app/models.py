from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uuid4() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IdTimeMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(IdTimeMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(30), default="student")
    password_hash: Mapped[str] = mapped_column(String(255))


class StudentProfile(IdTimeMixin, Base):
    __tablename__ = "student_profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    grade: Mapped[str] = mapped_column(String(30), default="初二")
    learning_goal: Mapped[str] = mapped_column(String(255), default="修复错误思维")
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class GuardianStudentLink(IdTimeMixin, Base):
    __tablename__ = "guardian_student_links"
    guardian_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class TeacherClass(IdTimeMixin, Base):
    __tablename__ = "teacher_classes"
    teacher_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    grade: Mapped[str] = mapped_column(String(30), default="")


class TeacherClassStudent(IdTimeMixin, Base):
    __tablename__ = "teacher_class_students"
    __table_args__ = (UniqueConstraint("class_id", "student_id", name="uq_teacher_class_student"),)
    class_id: Mapped[str] = mapped_column(ForeignKey("teacher_classes.id"))
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Question(IdTimeMixin, Base):
    __tablename__ = "questions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(30), default="数学")
    grade: Mapped[str | None] = mapped_column(String(30), nullable=True, default=None)
    title: Mapped[str] = mapped_column(String(255), default="新错题")
    question_text: Mapped[str] = mapped_column(Text, default="")
    student_answer: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(30), default="processing")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list[Any]] = mapped_column(JSON, default=list)
    formulas: Mapped[list[Any]] = mapped_column(JSON, default=list)
    options: Mapped[list[Any]] = mapped_column(JSON, default=list)
    question_type: Mapped[str] = mapped_column(String(50), default="综合题")
    knowledge_points: Mapped[list[Any]] = mapped_column(JSON, default=list)


class TeacherQuestion(IdTimeMixin, Base):
    __tablename__ = "teacher_questions"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), unique=True, index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(30), default="manual")
    standard_answer: Mapped[str] = mapped_column(Text, default="")
    reference_steps: Mapped[list[Any]] = mapped_column(JSON, default=list)
    scoring_points: Mapped[list[Any]] = mapped_column(JSON, default=list)
    difficulty: Mapped[str] = mapped_column(String(30), default="")
    allow_auto_grade: Mapped[bool] = mapped_column(Boolean, default=True)
    require_handwriting: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="draft")


class QuestionAssignment(IdTimeMixin, Base):
    __tablename__ = "question_assignments"
    teacher_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    class_id: Mapped[str | None] = mapped_column(ForeignKey("teacher_classes.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="练习任务")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="active")


class AssignmentStudent(IdTimeMixin, Base):
    __tablename__ = "assignment_students"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("question_assignments.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    latest_attempt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class AssignmentAttempt(IdTimeMixin, Base):
    __tablename__ = "assignment_attempts"
    assignment_student_id: Mapped[str] = mapped_column(ForeignKey("assignment_students.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    answer: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[list[Any]] = mapped_column(JSON, default=list)
    handwriting_asset_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    grading_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    verdict: Mapped[str] = mapped_column(String(30), default="review_required")
    status: Mapped[str] = mapped_column(String(30), default="submitted")
    version: Mapped[int] = mapped_column(Integer, default=1)


class TeacherReviewTask(IdTimeMixin, Base):
    __tablename__ = "teacher_review_tasks"
    __table_args__ = (UniqueConstraint("source_type", "source_id", name="uq_teacher_review_source"),)
    class_id: Mapped[str] = mapped_column(ForeignKey("teacher_classes.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(30), default="assignment_attempt")
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    reason_codes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    ai_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rule_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    has_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_teacher_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    learning_applied: Mapped[bool] = mapped_column(Boolean, default=False)


class TeacherReviewResult(IdTimeMixin, Base):
    __tablename__ = "teacher_review_results"
    task_id: Mapped[str] = mapped_column(ForeignKey("teacher_review_tasks.id"), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conclusion: Mapped[str] = mapped_column(String(30))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    first_key_error: Mapped[str] = mapped_column(Text, default="")
    error_type: Mapped[str] = mapped_column(String(80), default="")
    propagated_error: Mapped[bool] = mapped_column(Boolean, default=False)
    student_hint: Mapped[str] = mapped_column(Text, default="")
    next_task: Mapped[str] = mapped_column(Text, default="")
    mastered_steps: Mapped[list[Any]] = mapped_column(JSON, default=list)
    allow_learning_update: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    learning_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("teacher_review_results.id"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TeacherAuditLog(IdTimeMixin, Base):
    __tablename__ = "teacher_audit_logs"
    teacher_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    before_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    after_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")


class QuestionAsset(IdTimeMixin, Base):
    __tablename__ = "question_assets"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bbox: Mapped[list[Any]] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProcessingJob(IdTimeMixin, Base):
    __tablename__ = "processing_jobs"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="ingest")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class OCRRun(IdTimeMixin, Base):
    __tablename__ = "ocr_runs"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    provider: Mapped[str] = mapped_column(String(100), default="qwen")
    raw_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    stream: Mapped[str] = mapped_column(String(30), default="qwen_crop")
    status: Mapped[str] = mapped_column(String(30), default="completed")
    model_name: Mapped[str] = mapped_column(String(120), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class StudentWork(IdTimeMixin, Base):
    __tablename__ = "student_works"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    answer: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")


class StudentStep(IdTimeMixin, Base):
    __tablename__ = "student_steps"
    work_id: Mapped[str] = mapped_column(ForeignKey("student_works.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    bbox: Mapped[list[Any]] = mapped_column(JSON, default=list)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    formula: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(50), default="qwen_crop")
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class TeacherMark(IdTimeMixin, Base):
    __tablename__ = "teacher_marks"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    mark_type: Mapped[str] = mapped_column(String(50), default="comment")
    comment: Mapped[str] = mapped_column(Text, default="")
    bbox: Mapped[list[Any]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(50), default="qwen_vision")


class ProblemAnalysis(IdTimeMixin, Base):
    __tablename__ = "problem_analyses"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), unique=True)
    subject: Mapped[str] = mapped_column(String(30))
    problem_type: Mapped[str] = mapped_column(String(60), default="综合题")
    known_conditions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    goal: Mapped[str] = mapped_column(Text, default="")
    knowledge_points: Mapped[list[Any]] = mapped_column(JSON, default=list)
    prerequisites: Mapped[list[Any]] = mapped_column(JSON, default=list)
    final_answer: Mapped[str] = mapped_column(Text, default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ReferenceStep(IdTimeMixin, Base):
    __tablename__ = "reference_steps"
    analysis_id: Mapped[str] = mapped_column(ForeignKey("problem_analyses.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, default="")
    math_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    uses_condition: Mapped[bool] = mapped_column(Boolean, default=True)


class Diagnosis(IdTimeMixin, Base):
    __tablename__ = "diagnoses"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    first_error_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_error_text: Mapped[str] = mapped_column(Text, default="")
    error_type: Mapped[str] = mapped_column(String(60), default="unknown")
    root_misconception: Mapped[str] = mapped_column(Text, default="")
    propagated_errors: Mapped[list[Any]] = mapped_column(JSON, default=list)
    strategy_candidates: Mapped[list[Any]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    error_location: Mapped[str] = mapped_column(Text, default="")
    missing_prerequisites: Mapped[list[Any]] = mapped_column(JSON, default=list)
    recommended_strategy: Mapped[str] = mapped_column(Text, default="")
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    correction: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DiagnosisEvidence(IdTimeMixin, Base):
    __tablename__ = "diagnosis_evidence"
    diagnosis_id: Mapped[str] = mapped_column(ForeignKey("diagnoses.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    reference_step_id: Mapped[str | None] = mapped_column(ForeignKey("reference_steps.id"), nullable=True)
    student_step_id: Mapped[str | None] = mapped_column(ForeignKey("student_steps.id"), nullable=True)
    alignment: Mapped[str] = mapped_column(String(50), default="unmatched")
    equivalent: Mapped[bool] = mapped_column(Boolean, default=False)
    uses_condition: Mapped[bool] = mapped_column(Boolean, default=False)
    is_first_error: Mapped[bool] = mapped_column(Boolean, default=False)
    propagated: Mapped[bool] = mapped_column(Boolean, default=False)
    math_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class TutorSession(IdTimeMixin, Base):
    __tablename__ = "tutor_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    stage: Mapped[str] = mapped_column(String(50), default="understanding")
    hint_level: Mapped[int] = mapped_column(Integer, default=0)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="active")


class TutorTurn(IdTimeMixin, Base):
    __tablename__ = "tutor_turns"
    session_id: Mapped[str] = mapped_column(ForeignKey("tutor_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String(50), default="understanding")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AgentRun(IdTimeMixin, Base):
    __tablename__ = "agent_runs"
    session_id: Mapped[str | None] = mapped_column(ForeignKey("tutor_sessions.id"), nullable=True)
    agent_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="completed")
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AgentToolCall(IdTimeMixin, Base):
    __tablename__ = "agent_tool_calls"
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(80))
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class VisualizationSpec(IdTimeMixin, Base):
    __tablename__ = "visualization_specs"
    session_id: Mapped[str] = mapped_column(ForeignKey("tutor_sessions.id"), index=True)
    type: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(255))
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)


class VisualizationInteraction(IdTimeMixin, Base):
    __tablename__ = "visualization_interactions"
    visualization_id: Mapped[str] = mapped_column(ForeignKey("visualization_specs.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    observation: Mapped[str] = mapped_column(Text, default="")


class VariantQuestion(IdTimeMixin, Base):
    __tablename__ = "variant_questions"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("tutor_sessions.id"), index=True)
    transfer_type: Mapped[str] = mapped_column(String(20), default="near")
    question_text: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    reference_solution: Mapped[list[Any]] = mapped_column(JSON, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    generation_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class VariantAttempt(IdTimeMixin, Base):
    __tablename__ = "variant_attempts"
    variant_id: Mapped[str] = mapped_column(ForeignKey("variant_questions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    answer: Mapped[str] = mapped_column(Text)
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0)
    hint_level: Mapped[int] = mapped_column(Integer, default=0)


class KnowledgePoint(IdTimeMixin, Base):
    __tablename__ = "knowledge_points"
    code: Mapped[str] = mapped_column(String(100), unique=True)
    subject: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DatasetSource(IdTimeMixin, Base):
    __tablename__ = "dataset_sources"
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(100), default="")
    homepage: Mapped[str] = mapped_column(String(500), default="")
    license: Mapped[str] = mapped_column(String(100), default="")
    local_path: Mapped[str] = mapped_column(String(500), default="")
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    imported_items: Mapped[int] = mapped_column(Integer, default=0)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DatasetQuestion(IdTimeMixin, Base):
    __tablename__ = "dataset_questions"
    __table_args__ = (
        UniqueConstraint("dataset_source_id", "source_item_id", name="uq_dataset_question_source_item"),
    )
    dataset_source_id: Mapped[str] = mapped_column(ForeignKey("dataset_sources.id"), index=True)
    source_item_id: Mapped[str] = mapped_column(String(190))
    split: Mapped[str] = mapped_column(String(30), default="")
    subject: Mapped[str] = mapped_column(String(30), index=True)
    grade: Mapped[str] = mapped_column(String(30), default="")
    grade_band: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    question_text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(60), default="综合题")
    options: Mapped[list[Any]] = mapped_column(JSON, default=list)
    answer: Mapped[Any] = mapped_column(JSON, default=list)
    solution: Mapped[str] = mapped_column(Text, default="")
    knowledge_points: Mapped[list[Any]] = mapped_column(JSON, default=list)
    image_paths: Mapped[list[Any]] = mapped_column(JSON, default=list)
    difficulty: Mapped[str] = mapped_column(String(30), default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    has_answer: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    has_solution: Mapped[bool] = mapped_column(Boolean, default=False)
    answer_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    usable_for_practice: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    usable_for_auto_grade: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class QuestionKnowledgeLink(IdTimeMixin, Base):
    __tablename__ = "question_knowledge_links"
    __table_args__ = (
        UniqueConstraint("dataset_question_id", "knowledge_point_id", name="uq_question_knowledge_link"),
    )
    dataset_question_id: Mapped[str] = mapped_column(ForeignKey("dataset_questions.id"), index=True)
    knowledge_point_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="primary", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    mapping_method: Mapped[str] = mapped_column(String(40), default="offline_rules")


class UserQuestionKnowledgeLink(IdTimeMixin, Base):
    """Map a learner's uploaded mistake onto the shared knowledge graph."""

    __tablename__ = "user_question_knowledge_links"
    __table_args__ = (
        UniqueConstraint("question_id", "knowledge_point_id", name="uq_user_question_knowledge_link"),
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    knowledge_point_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="primary", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    mapping_method: Mapped[str] = mapped_column(String(40), default="analysis_match")
    evidence_text: Mapped[str] = mapped_column(String(255), default="")


class PracticeRecommendation(IdTimeMixin, Base):
    __tablename__ = "practice_recommendations"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    mistake_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    dataset_question_id: Mapped[str] = mapped_column(ForeignKey("dataset_questions.id"), index=True)
    mode: Mapped[str] = mapped_column(String(20), index=True)
    retrieval_rank: Mapped[int] = mapped_column(Integer, default=0)
    retrieval_trace: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DatasetPracticeAttempt(IdTimeMixin, Base):
    __tablename__ = "dataset_practice_attempts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    mistake_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    dataset_question_id: Mapped[str] = mapped_column(ForeignKey("dataset_questions.id"), index=True)
    source_dataset: Mapped[str] = mapped_column(String(80), index=True)
    knowledge_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(20), index=True)
    student_answer: Mapped[Any] = mapped_column(JSON, default=str)
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    grading_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class KnowledgeRelation(IdTimeMixin, Base):
    __tablename__ = "knowledge_relations"
    source_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"))
    target_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"))
    relation_type: Mapped[str] = mapped_column(String(30), default="prerequisite")


class MasteryState(IdTimeMixin, Base):
    __tablename__ = "mastery_states"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(30), index=True)
    knowledge_point: Mapped[str] = mapped_column(String(100))
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    near_transfer_rate: Mapped[float] = mapped_column(Float, default=0.0)
    far_transfer_rate: Mapped[float] = mapped_column(Float, default=0.0)
    forgetting_risk: Mapped[float] = mapped_column(Float, default=0.5)
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    update_reason: Mapped[str] = mapped_column(Text, default="")


class MisconceptionState(IdTimeMixin, Base):
    __tablename__ = "misconception_states"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(30), index=True)
    code: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(150))
    probability: Mapped[float] = mapped_column(Float, default=0.5)
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="active")
    related_question_count: Mapped[int] = mapped_column(Integer, default=1)
    successful_strategy: Mapped[str] = mapped_column(Text, default="")
    failed_strategy: Mapped[str] = mapped_column(Text, default="")
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CognitiveUpdate(IdTimeMixin, Base):
    __tablename__ = "cognitive_updates"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_key: Mapped[str] = mapped_column(String(120))
    old_value: Mapped[float] = mapped_column(Float, default=0.0)
    new_value: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")


class ReviewPlan(IdTimeMixin, Base):
    __tablename__ = "review_plans"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[str] = mapped_column(Text, default="首次修复后巩固")
    status: Mapped[str] = mapped_column(String(30), default="pending")


class ReviewRecord(IdTimeMixin, Base):
    __tablename__ = "review_records"
    plan_id: Mapped[str] = mapped_column(ForeignKey("review_plans.id"), index=True)
    grade: Mapped[str] = mapped_column(String(20))
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    student_answer: Mapped[str] = mapped_column(Text, default="")
    expected_answer: Mapped[str] = mapped_column(Text, default="")
    feedback: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    grading_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Paper(IdTimeMixin, Base):
    __tablename__ = "papers"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PaperItem(IdTimeMixin, Base):
    __tablename__ = "paper_items"
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=10)


class VoiceRecord(IdTimeMixin, Base):
    __tablename__ = "voice_records"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    work_id: Mapped[str | None] = mapped_column(ForeignKey("student_works.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="stt")
    audio_path: Mapped[str] = mapped_column(String(500))
    transcript: Mapped[str] = mapped_column(Text, default="")
    model_name: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(30), default="completed")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)


class ExportJob(IdTimeMixin, Base):
    __tablename__ = "export_jobs"
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="completed")
    path: Mapped[str] = mapped_column(String(500))
