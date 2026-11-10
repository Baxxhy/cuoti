from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LoginSession(Base):
    __tablename__ = "login_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    grade: Mapped[str] = mapped_column(String(80), default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)
    unit_id: Mapped[str | None] = mapped_column(ForeignKey("course_units.id"), nullable=True)


class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    grade: Mapped[str] = mapped_column(String(80), default="")
    subject: Mapped[str] = mapped_column(String(80), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ClassMember(Base):
    __tablename__ = "class_members"

    classroom_id: Mapped[str] = mapped_column(ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TeachingCase(Base):
    __tablename__ = "teaching_cases"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    source: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class LessonDraft(Base):
    __tablename__ = "lesson_drafts"
    __table_args__ = (UniqueConstraint("teacher_id", "lesson_id", name="uq_lesson_draft_owner_lesson"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), index=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("teaching_cases.id"), nullable=True)
    case_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    lesson_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    goal: Mapped[str] = mapped_column(Text, default="")
    student_base: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[str] = mapped_column(String(30), default="")
    blocks: Mapped[list] = mapped_column(JSON, default=list)
    questions: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    planning_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class LearningTask(Base):
    __tablename__ = "learning_tasks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    classroom_id: Mapped[str] = mapped_column(ForeignKey("classrooms.id"), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    snapshot: Mapped[dict] = mapped_column(JSON)
    questions: Mapped[list] = mapped_column(JSON)
    due_date: Mapped[str] = mapped_column(String(30), default="")
    source: Mapped[str] = mapped_column(String(40), default="published")
    published_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class StudentRecord(Base):
    __tablename__ = "student_records"
    __table_args__ = (UniqueConstraint("task_id", "student_id", name="uq_task_student_record"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    observation: Mapped[str] = mapped_column(Text, default="")
    drafts: Mapped[dict] = mapped_column(JSON, default=dict)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, default="")
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="live")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("student_records.id", ondelete="CASCADE"), index=True)
    question: Mapped[int] = mapped_column(Integer)
    answer: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, default="")
    helped: Mapped[bool] = mapped_column(Boolean, default=False)
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    verification: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class HelpRecord(Base):
    __tablename__ = "help_records"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("student_records.id", ondelete="CASCADE"), index=True)
    question: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text, default="")
    file_id: Mapped[str | None] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WrongQuestion(Base):
    __tablename__ = "wrong_questions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    record_id: Mapped[str | None] = mapped_column(ForeignKey("student_records.id", ondelete="CASCADE"), nullable=True, index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("attempts.id", ondelete="SET NULL"), nullable=True)
    prompt: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    file_id: Mapped[str | None] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RepairAttempt(Base):
    __tablename__ = "repair_attempts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    wrong_id: Mapped[str] = mapped_column(ForeignKey("wrong_questions.id", ondelete="CASCADE"), index=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    answer: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, default="")
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    verification: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FileAsset(Base):
    __tablename__ = "file_assets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SupplementalInstruction(Base):
    __tablename__ = "supplemental_instructions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="CASCADE"), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(24), default='note', server_default='note')
    due_date: Mapped[str] = mapped_column(String(40), default='', server_default='')
    status: Mapped[str] = mapped_column(String(24), default='active', server_default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SupportIssue(Base):
    __tablename__ = "support_issues"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    reply: Mapped[str] = mapped_column(Text, default="")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ModelJob(Base):
    __tablename__ = "model_jobs"
    __table_args__ = (UniqueConstraint("owner_id", "request_key", name="uq_model_job_request"), UniqueConstraint("owner_id", "active_hash", name="uq_model_job_active_input"))
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    record_id: Mapped[str | None] = mapped_column(ForeignKey("student_records.id"), nullable=True, index=True)
    file_id: Mapped[str | None] = mapped_column(ForeignKey("file_assets.id"), nullable=True)
    capability: Mapped[str] = mapped_column(String(30), index=True)
    request_key: Mapped[str] = mapped_column(String(80))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    active_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    step: Mapped[str] = mapped_column(String(100), default="排队中")
    error: Mapped[str] = mapped_column(Text, default="")
    attempt_number: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("model_jobs.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="running")
    model: Mapped[str] = mapped_column(String(160), default="")
    provider: Mapped[str] = mapped_column(String(100), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ModelEvent(Base):
    __tablename__ = "model_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("model_jobs.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    step: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SourceMaterial(Base):
    __tablename__ = 'source_materials'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'), index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey('file_assets.id'))
    title: Mapped[str] = mapped_column(String(240))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    parse_job_id: Mapped[str | None] = mapped_column(ForeignKey('model_jobs.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MaterialUnit(Base):
    __tablename__ = 'material_units'
    __table_args__ = (UniqueConstraint('material_id', 'position', name='uq_material_position'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    material_id: Mapped[str] = mapped_column(ForeignKey('source_materials.id'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(30))
    original_text: Mapped[str] = mapped_column(Text, default='')
    text: Mapped[str] = mapped_column(Text, default='')
    image_file_id: Mapped[str | None] = mapped_column(ForeignKey('file_assets.id'), nullable=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey('model_jobs.id'), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CaseDraftContent(Base):
    __tablename__ = 'case_draft_contents'
    case_id: Mapped[str] = mapped_column(ForeignKey('teaching_cases.id'), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CaseVersion(Base):
    __tablename__ = 'case_versions'
    __table_args__ = (UniqueConstraint('case_id', 'number', name='uq_case_version_number'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey('teaching_cases.id'), index=True)
    number: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.utcnow().replace(microsecond=0))


class CourseUnit(Base):
    __tablename__ = 'course_units'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey('courses.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)


class KnowledgePoint(Base):
    __tablename__ = 'knowledge_points'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    aliases: Mapped[list] = mapped_column(JSON, default=list, nullable=True)
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)


class LessonContent(Base):
    __tablename__ = 'lesson_contents'
    lesson_id: Mapped[str] = mapped_column(ForeignKey('lessons.id'), primary_key=True)
    draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default='draft')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LessonVersion(Base):
    __tablename__ = 'lesson_versions'
    __table_args__ = (UniqueConstraint('lesson_id', 'number', name='uq_lesson_version'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey('lessons.id'), index=True)
    number: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LessonDraftVersion(Base):
    __tablename__ = 'lesson_draft_versions'
    __table_args__ = (UniqueConstraint('draft_id','number',name='uq_draft_version_number'),)
    id: Mapped[str] = mapped_column(String(40),primary_key=True)
    draft_id: Mapped[str] = mapped_column(ForeignKey('lesson_drafts.id'),index=True)
    number: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime,server_default=func.now())


class ClassInvite(Base):
    __tablename__='class_invites'
    id: Mapped[str] = mapped_column(String(40),primary_key=True)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'),index=True)
    code_hash: Mapped[str] = mapped_column(String(64),unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean,default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime,server_default=func.now())

class JoinThrottle(Base):
    __tablename__='class_join_throttles'
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'),primary_key=True)
    count: Mapped[int] = mapped_column(Integer,default=0)
    window_start: Mapped[datetime] = mapped_column(DateTime)

class BusinessMessage(Base):
    __tablename__='business_messages'
    id: Mapped[str] = mapped_column(String(40),primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(64),unique=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'),index=True)
    recipient_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'),index=True)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'),index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey('learning_tasks.id'),index=True)
    object_id: Mapped[str | None] = mapped_column(String(40),nullable=True)
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text,default='')
    read_at: Mapped[datetime | None] = mapped_column(DateTime,nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime,server_default=func.now())

class SupplementRecipient(Base):
    __tablename__='supplement_recipients'
    instruction_id: Mapped[str] = mapped_column(ForeignKey('supplemental_instructions.id'),primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'),primary_key=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime,nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime,nullable=True)
    response: Mapped[str] = mapped_column(Text,default='')
    feedback: Mapped[str] = mapped_column(Text,default='')
