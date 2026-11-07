import hashlib
import os
import secrets
import uuid
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Account, Attempt, ClassMember, Classroom, FileAsset, HelpRecord, LearningTask, Lesson, LessonDraft, LoginSession, RepairAttempt, StudentRecord, SupplementalInstruction, SupportIssue, TeachingCase, WrongQuestion
from .seed import BLOCKS, CASE_TEXT, QUESTIONS, ensure_seed
from .security import hash_password, verify_password

app = FastAPI(title="师承智学业务服务", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5177", "http://127.0.0.1:5177", "http://localhost:5178", "http://127.0.0.1:5178"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
DB = Annotated[Session, Depends(get_db)]
COOKIE = "sczx_session"
COOKIE_SECURE = os.getenv("SCZX_COOKIE_SECURE", "false").lower() == "true"
STORAGE_DIR = Path(os.getenv("SCZX_STORAGE_DIR", "./var/uploads")).resolve()


class LoginInput(BaseModel):
    username: str
    password: str


class AccountInput(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    displayName: str = Field(min_length=1, max_length=120)
    role: str
    password: str = Field(min_length=8, max_length=200)


class ClassInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    grade: str = "七年级数学"


class MemberInput(BaseModel):
    studentId: str


class IssueReplyInput(BaseModel):
    reply: str = Field(min_length=1, max_length=10000)


class PlatformInput(BaseModel):
    data: dict


class PublishInput(BaseModel):
    classroomId: str
    lessonDraft: dict
    idempotencyKey: str = Field(min_length=8, max_length=100)


def account_json(user: Account) -> dict:
    return {"id": user.id, "username": user.username, "displayName": user.display_name, "role": user.role}


def current_user(request: Request, db: DB) -> Account:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "请先登录。")
    session_id = hashlib.sha256(token.encode()).hexdigest()
    session = db.get(LoginSession, session_id)
    if not session or session.expires_at < datetime.utcnow():
        raise HTTPException(401, "登录已失效，请重新登录。")
    user = db.get(Account, session.account_id)
    if not user or not user.active:
        raise HTTPException(401, "当前账号不可用，请联系管理员。")
    return user


def require_role(user: Account, *roles: str) -> None:
    if user.role not in roles:
        raise HTTPException(403, "当前账号没有此操作权限。")


def file_url(file_id: str | None) -> str:
    return f"/api/files/{file_id}" if file_id else ""


def file_id_from_url(value: str | None) -> str | None:
    if not value:
        return None
    prefix = "/api/files/"
    return value.rsplit(prefix, 1)[-1] if prefix in value else None


def import_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def record_json(db: Session, rec: StudentRecord) -> dict:
    student = db.get(Account, rec.student_id)
    attempts = db.scalars(select(Attempt).where(Attempt.record_id == rec.id).order_by(Attempt.created_at)).all()
    helps = db.scalars(select(HelpRecord).where(HelpRecord.record_id == rec.id).order_by(HelpRecord.created_at)).all()
    wrongs = db.scalars(select(WrongQuestion).where(WrongQuestion.record_id == rec.id).order_by(WrongQuestion.created_at)).all()
    wrong_json = []
    for item in wrongs:
        repairs = db.scalars(select(RepairAttempt).where(RepairAttempt.wrong_id == item.id).order_by(RepairAttempt.created_at)).all()
        wrong_json.append({"id": item.id, "taskId": rec.task_id, "attemptId": item.attempt_id, "prompt": item.prompt, "answer": item.answer, "reason": item.reason, "image": file_url(item.file_id), "createdAt": item.created_at.isoformat(), "repairs": [{"id": r.id, "taskId": rec.task_id, "wrongId": item.id, "answer": r.answer, "reason": r.reason, "correct": r.correct, "createdAt": r.created_at.isoformat()} for r in repairs]})
    return {"id": rec.id, "taskId": rec.task_id, "studentId": rec.student_id, "studentName": student.display_name if student else "学生", "observation": rec.observation, "drafts": rec.drafts or {}, "attempts": [{"id": a.id, "taskId": rec.task_id, "question": a.question, "answer": a.answer, "reason": a.reason, "helped": a.helped, "correct": a.correct, "createdAt": a.created_at.isoformat()} for a in attempts], "helps": [{"id": h.id, "taskId": rec.task_id, "question": h.question, "kind": h.kind, "message": h.message, "image": file_url(h.file_id), "attemptNumber": h.attempt_number, "createdAt": h.created_at.isoformat()} for h in helps], "repairs": [repair for wrong in wrong_json for repair in wrong["repairs"]], "wrongQuestions": wrong_json, "completed": rec.completed, "submittedAt": rec.submitted_at.isoformat() if rec.submitted_at else None, "feedback": rec.feedback, "feedbackAt": rec.feedback_at.isoformat() if rec.feedback_at else None, "updatedAt": rec.updated_at.isoformat() if rec.updated_at else None}


def platform_data(db: Session, user: Account) -> dict:
    classrooms = db.scalars(select(Classroom).order_by(Classroom.created_at)).all()
    if user.role == "teacher":
        classrooms = [c for c in classrooms if c.teacher_id == user.id]
    elif user.role == "student":
        memberships = db.scalars(select(ClassMember.classroom_id).where(ClassMember.student_id == user.id)).all()
        classrooms = [c for c in classrooms if c.id in memberships]
    classroom = classrooms[0] if classrooms else None
    lessons = db.scalars(select(Lesson).order_by(Lesson.position)).all()
    lesson = lessons[0] if lessons else None
    case = db.scalar(select(TeachingCase).where(TeachingCase.status == "published").order_by(TeachingCase.updated_at.desc()))
    draft = None
    if lesson and user.role == "teacher":
        draft = db.scalar(select(LessonDraft).where(LessonDraft.teacher_id == user.id, LessonDraft.lesson_id == lesson.id))
    if not draft and lesson and user.role == "admin":
        draft = db.scalar(select(LessonDraft).where(LessonDraft.lesson_id == lesson.id))
    tasks = []
    if user.role == "teacher":
        classroom_ids = [c.id for c in classrooms]
        tasks = db.scalars(select(LearningTask).where(LearningTask.classroom_id.in_(classroom_ids)).order_by(LearningTask.published_at.desc())).all() if classroom_ids else []
    elif user.role == "student":
        class_ids = [c.id for c in classrooms]
        tasks = db.scalars(select(LearningTask).where(LearningTask.classroom_id.in_(class_ids)).order_by(LearningTask.published_at.desc())).all() if class_ids else []
    elif user.role == "admin":
        tasks = db.scalars(select(LearningTask).order_by(LearningTask.published_at.desc())).all()
    task_json = []
    records = {}
    student_records = {}
    for task in tasks:
        task_classroom = db.get(Classroom, task.classroom_id)
        task_json.append({"id": task.id, "lessonId": task.lesson_id, "classId": task.classroom_id, "className": task_classroom.name if task_classroom else "班级", "title": task.title, "snapshot": task.snapshot, "questions": task.questions, "publishedAt": task.published_at.isoformat(), "dueDate": task.due_date, "source": task.source})
        if user.role == "student":
            recs = db.scalars(select(StudentRecord).where(StudentRecord.task_id == task.id, StudentRecord.student_id == user.id)).all()
        else:
            member_ids = db.scalars(select(ClassMember.student_id).where(ClassMember.classroom_id == task.classroom_id)).all()
            recs = db.scalars(select(StudentRecord).where(StudentRecord.task_id == task.id, StudentRecord.student_id.in_(member_ids))).all() if member_ids else []
        values = [record_json(db, rec) for rec in recs]
        student_records[task.id] = values
        if values:
            records[task.id] = values[0]
    first_case = db.scalar(select(TeachingCase).where(TeachingCase.status == "draft").order_by(TeachingCase.updated_at.desc())) or case
    issue = None
    if user.role == "student":
        issue = db.scalar(select(SupportIssue).where(SupportIssue.owner_id == user.id).order_by(SupportIssue.updated_at.desc()))
    elif user.role == "teacher" and classroom:
        member_ids = db.scalars(select(ClassMember.student_id).where(ClassMember.classroom_id == classroom.id)).all()
        if member_ids:
            issue = db.scalar(select(SupportIssue).where(SupportIssue.owner_id.in_(member_ids)).order_by(SupportIssue.updated_at.desc()))
    messages = []
    supplements = []
    task_ids = [item["id"] for item in task_json]
    if task_ids:
        supplements = [{"id": item.id, "taskId": item.task_id, "content": item.content, "createdAt": item.created_at.isoformat()} for item in db.scalars(select(SupplementalInstruction).where(SupplementalInstruction.task_id.in_(task_ids)).order_by(SupplementalInstruction.created_at)).all()]
    if user.role == "student":
        for task_id, rec in records.items():
            if rec.get("feedback"):
                task = next((item for item in task_json if item["id"] == task_id), None)
                messages.append({"id": rec["id"], "taskId": task_id, "title": f"{task['title'] if task else '课程'} · 教师反馈", "createdAt": rec.get("feedbackAt")})
    return {"version": 2, "currentUser": account_json(user), "classroom": {"id": classroom.id, "name": classroom.name, "grade": classroom.grade, "teacherId": classroom.teacher_id} if classroom else None, "classrooms": [{"id": c.id, "name": c.name, "grade": c.grade, "teacherId": c.teacher_id} for c in classrooms], "members": [{"id": m.id, "displayName": m.display_name, "username": m.username} for m in db.scalars(select(Account).join(ClassMember, ClassMember.student_id == Account.id).where(ClassMember.classroom_id == classroom.id)).all()] if classroom and user.role == "teacher" else [], "lesson": {"id": lesson.id, "title": lesson.title, "courseId": lesson.course_id} if lesson else None, "caseDraft": {"id": first_case.id, "title": first_case.title, "source": first_case.source, "content": first_case.content, "reviewed": first_case.status == "published", "fileName": "", "updatedAt": first_case.updated_at.isoformat()} if first_case else {"id": "case-balance", "title": "天平与等式性质", "source": "", "content": CASE_TEXT, "reviewed": False, "fileName": ""}, "publishedCase": {"id": case.id, "title": case.title, "source": case.source, "content": case.content, "publishedAt": case.updated_at.isoformat()} if case else None, "lessonDraft": {"id": draft.id, "caseId": draft.case_id, "goal": draft.goal, "studentBase": draft.student_base, "dueDate": draft.due_date, "blocks": draft.blocks, "questions": draft.questions, "updatedAt": draft.updated_at.isoformat()} if draft else {"id": "draft-equation", "caseId": case.id if case else None, "goal": "理解并应用等式两边的共同变化", "studentBase": "", "dueDate": "", "blocks": BLOCKS, "questions": QUESTIONS}, "tasks": task_json, "records": records, "studentRecords": student_records, "activeTaskId": task_json[0]["id"] if task_json else None, "activeStudentId": next(iter(student_records.values()))[0]["studentId"] if student_records and next(iter(student_records.values())) else user.id, "favorite": False, "issue": {"id": issue.id, "text": issue.text, "reply": issue.reply, "resolved": issue.resolved, "updatedAt": issue.updated_at.isoformat()} if issue else {"id": "issue-empty", "text": "", "reply": "", "resolved": False}, "runtime": {"id": "runtime-placeholder", "status": "idle"}, "supplements": supplements, "messages": messages}


@app.on_event("startup")
def startup() -> None:
    if os.getenv("SCZX_AUTO_CREATE_SCHEMA", "false").lower() == "true":
        from .database import Base, engine
        Base.metadata.create_all(engine)
        ensure_seed()


@app.get("/api/health")
def health(db: DB) -> dict:
    db.execute(select(1))
    return {"status": "ok", "database": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginInput, response: Response, db: DB) -> dict:
    user = db.scalar(select(Account).where(Account.username == payload.username, Account.active.is_(True)))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "账号或密码不正确。")
    token = secrets.token_urlsafe(36)
    session = LoginSession(id=hashlib.sha256(token.encode()).hexdigest(), account_id=user.id, expires_at=datetime.utcnow() + timedelta(days=7))
    db.add(session)
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=7 * 86400, path="/")
    return {"user": account_json(user)}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db: DB) -> dict:
    token = request.cookies.get(COOKIE)
    if token:
        session = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request, db: DB) -> dict:
    return {"user": account_json(current_user(request, db))}


@app.get("/api/accounts")
def list_accounts(request: Request, db: DB) -> list[dict]:
    user = current_user(request, db)
    require_role(user, "admin", "teacher")
    roles = ["student"] if user.role == "teacher" else ["admin", "teacher", "student"]
    return [account_json(a) for a in db.scalars(select(Account).where(Account.role.in_(roles), Account.active.is_(True)).order_by(Account.role, Account.display_name)).all()]


@app.post("/api/accounts", status_code=201)
def create_account(payload: AccountInput, request: Request, db: DB) -> dict:
    require_role(current_user(request, db), "admin")
    if payload.role not in {"teacher", "student"}:
        raise HTTPException(422, "只能创建教师或学生账号。")
    if db.scalar(select(Account.id).where(Account.username == payload.username)):
        raise HTTPException(409, "此账号名已存在。")
    account = Account(id=f"account-{uuid.uuid4().hex}", username=payload.username, display_name=payload.displayName, role=payload.role, password_hash=hash_password(payload.password))
    db.add(account)
    db.commit()
    return account_json(account)


@app.post("/api/classrooms", status_code=201)
def create_classroom(payload: ClassInput, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    require_role(user, "teacher")
    classroom = Classroom(id=f"class-{uuid.uuid4().hex}", teacher_id=user.id, name=payload.name, grade=payload.grade)
    db.add(classroom)
    db.commit()
    return {"id": classroom.id, "name": classroom.name, "grade": classroom.grade}


@app.post("/api/classrooms/{classroom_id}/members", status_code=201)
def add_member(classroom_id: str, payload: MemberInput, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    room = db.get(Classroom, classroom_id)
    if not room or room.teacher_id != user.id:
        raise HTTPException(404, "没有找到此班级。")
    student = db.get(Account, payload.studentId)
    if not student or student.role != "student" or not student.active:
        raise HTTPException(404, "没有找到可加入的学生账号。")
    if db.get(ClassMember, {"classroom_id": room.id, "student_id": student.id}):
        raise HTTPException(409, "该学生已经在班级中。")
    db.add(ClassMember(classroom_id=room.id, student_id=student.id))
    db.commit()
    return account_json(student)


@app.put("/api/issues/{issue_id}/reply")
def reply_issue(issue_id: str, payload: IssueReplyInput, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    require_role(user, "teacher")
    issue = db.get(SupportIssue, issue_id)
    if not issue:
        raise HTTPException(404, "没有找到这条学习疑问。")
    classroom = db.scalar(
        select(Classroom.id)
        .join(ClassMember, ClassMember.classroom_id == Classroom.id)
        .where(Classroom.teacher_id == user.id, ClassMember.student_id == issue.owner_id)
        .limit(1)
    )
    if not classroom:
        raise HTTPException(404, "没有找到本班学生的学习疑问。")
    reply = payload.reply.strip()
    if not reply:
        raise HTTPException(422, "请填写回复内容。")
    issue.reply = reply
    issue.resolved = True
    db.commit()
    return {"reply": issue.reply, "resolved": issue.resolved, "updatedAt": issue.updated_at.isoformat()}


@app.get("/api/classrooms/{classroom_id}/members")
def list_members(classroom_id: str, request: Request, db: DB) -> list[dict]:
    user = current_user(request, db)
    room = db.get(Classroom, classroom_id)
    if not room or room.teacher_id != user.id:
        raise HTTPException(404, "没有找到此班级。")
    return [account_json(a) for a in db.scalars(select(Account).join(ClassMember, ClassMember.student_id == Account.id).where(ClassMember.classroom_id == room.id).order_by(Account.display_name)).all()]


@app.get("/api/platform")
def get_platform(request: Request, db: DB) -> dict:
    return platform_data(db, current_user(request, db))


@app.put("/api/platform")
def save_platform(payload: PlatformInput, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    data = payload.data
    try:
        if user.role == "teacher":
            draft = data.get("lessonDraft") or {}
            lesson_id = data.get("lesson", {}).get("id", "lesson-equation")
            record = db.scalar(select(LessonDraft).where(LessonDraft.teacher_id == user.id, LessonDraft.lesson_id == lesson_id))
            if not record and db.get(Lesson, lesson_id):
                record = LessonDraft(
                    id=f"draft-{uuid.uuid4().hex}",
                    teacher_id=user.id,
                    lesson_id=lesson_id,
                    case_id=draft.get("caseId"),
                    goal="",
                    student_base="",
                    due_date="",
                    blocks=[],
                    questions=[],
                )
                db.add(record)
            if record:
                record.case_id = draft.get("caseId")
                record.goal = str(draft.get("goal", ""))
                record.student_base = str(draft.get("studentBase", ""))
                record.due_date = str(draft.get("dueDate", ""))
                record.blocks = draft.get("blocks") or []
                record.questions = draft.get("questions") or QUESTIONS
            case_payload = data.get("caseDraft") or {}
            case = db.get(TeachingCase, case_payload.get("id", ""))
            if case and case.status == "draft":
                case.title = str(case_payload.get("title", case.title))
                case.content = str(case_payload.get("content", case.content))
                case.source = str(case_payload.get("source", case.source))
            for task_id, record_data in (data.get("records") or {}).items():
                if isinstance(record_data, list):
                    continue
                rec = db.get(StudentRecord, record_data.get("id", ""))
                task = db.get(LearningTask, rec.task_id) if rec else None
                if rec and task and task.teacher_id == user.id:
                    rec.feedback = str(record_data.get("feedback", ""))
                    rec.feedback_at = datetime.utcnow() if rec.feedback else None
            for item in data.get("supplements", []):
                task = db.get(LearningTask, str(item.get("taskId", "")))
                if task and task.teacher_id == user.id:
                    supplement = db.get(SupplementalInstruction, str(item.get("id", "")))
                    if not supplement:
                        supplement = SupplementalInstruction(id=str(item.get("id") or f"supp-{uuid.uuid4().hex[:32]}"), task_id=task.id, teacher_id=user.id, content="")
                        db.add(supplement)
                    supplement.content = str(item.get("content", ""))
        elif user.role == "admin":
            case_payload = data.get("caseDraft") or {}
            case_id = case_payload.get("id") or f"case-draft-{user.id}"
            case = db.get(TeachingCase, case_id)
            if not case or case.status == "published":
                case_id = f"case-draft-{user.id}"
                case = db.get(TeachingCase, case_id)
            if not case:
                case = TeachingCase(id=case_id, title="", source="", content="", status="draft")
                db.add(case)
            case.title = str(case_payload.get("title", case.title))
            case.content = str(case_payload.get("content", case.content))
            case.source = str(case_payload.get("source", case.source))
        elif user.role == "student":
            for task_id, record_data in (data.get("records") or {}).items():
                rec = db.scalar(select(StudentRecord).where(StudentRecord.task_id == task_id, StudentRecord.student_id == user.id))
                if not rec:
                    continue
                rec.observation = str(record_data.get("observation", ""))
                rec.drafts = record_data.get("drafts") or {}
                if record_data.get("completed"):
                    rec.completed = True
                    rec.submitted_at = rec.submitted_at or datetime.utcnow()
                current_attempts = {item.id: item for item in db.scalars(select(Attempt).where(Attempt.record_id == rec.id)).all()}
                for item in record_data.get("attempts", []):
                    attempt = current_attempts.get(str(item.get("id", "")))
                    task = db.get(LearningTask, task_id)
                    idx = int(item.get("question", -1))
                    expected = task.questions[idx].get("answer") if task and 0 <= idx < len(task.questions) else None
                    answer = str(item.get("answer", "")).strip()
                    if not answer or expected is None:
                        continue
                    if not attempt:
                        attempt = Attempt(id=str(item.get("id") or f"attempt-{uuid.uuid4().hex}"), record_id=rec.id, question=idx, answer=answer, reason="")
                        db.add(attempt)
                    attempt.question = idx
                    attempt.answer = answer
                    attempt.reason = str(item.get("reason", ""))
                    attempt.helped = bool(item.get("helped"))
                    attempt.correct = answer == str(expected)
                current_helps = {item.id: item for item in db.scalars(select(HelpRecord).where(HelpRecord.record_id == rec.id)).all()}
                for item in record_data.get("helps", []):
                    help_item = current_helps.get(str(item.get("id", "")))
                    if not help_item:
                        help_item = HelpRecord(id=str(item.get("id") or f"help-{uuid.uuid4().hex}"), record_id=rec.id, kind="提示")
                        db.add(help_item)
                    help_item.question = item.get("question")
                    help_item.kind = str(item.get("kind", "提示"))
                    help_item.message = str(item.get("message", ""))
                    help_item.file_id = file_id_from_url(item.get("image"))
                    help_item.attempt_number = int(item.get("attemptNumber", 1))
                current_wrongs = {item.id: item for item in db.scalars(select(WrongQuestion).where(WrongQuestion.record_id == rec.id)).all()}
                for item in record_data.get("wrongQuestions", []):
                    wrong = current_wrongs.get(str(item.get("id", "")))
                    if not wrong:
                        wrong = WrongQuestion(id=str(item.get("id") or f"wrong-{uuid.uuid4().hex}"), record_id=rec.id, prompt="")
                        db.add(wrong)
                    wrong.prompt = str(item.get("prompt", ""))
                    wrong.answer = str(item.get("answer", ""))
                    wrong.reason = str(item.get("reason", ""))
                    wrong.file_id = file_id_from_url(item.get("image"))
                    old_attempt = item.get("attemptId")
                    wrong.attempt_id = old_attempt if old_attempt and db.get(Attempt, old_attempt) else None
                    old_repairs = {repair.id: repair for repair in db.scalars(select(RepairAttempt).where(RepairAttempt.wrong_id == wrong.id)).all()}
                    for repair_data in item.get("repairs", []):
                        repair = old_repairs.get(str(repair_data.get("id", "")))
                        if not repair:
                            repair = RepairAttempt(id=str(repair_data.get("id") or f"repair-{uuid.uuid4().hex}"), wrong_id=wrong.id, answer="")
                            db.add(repair)
                        repair.answer = str(repair_data.get("answer", ""))
                        repair.reason = str(repair_data.get("reason", ""))
                        repair.correct = bool(repair_data.get("correct"))
            issue_data = data.get("issue") or {}
            issue = db.get(SupportIssue, issue_data.get("id", ""))
            if not issue and str(issue_data.get("text", "")).strip():
                issue = SupportIssue(id=str(issue_data.get("id") or f"issue-{uuid.uuid4().hex[:32]}"), owner_id=user.id, text="")
                db.add(issue)
            if issue and issue.owner_id == user.id:
                issue.text = str(issue_data.get("text", issue.text))
                issue.reply = str(issue_data.get("reply", issue.reply))
                issue.resolved = bool(issue_data.get("resolved"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"saved": True}


@app.put("/api/cases/draft")
def save_case(payload: dict, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    require_role(user, "admin")
    case_id = str(payload.get("id") or f"case-draft-{user.id}")
    case = db.get(TeachingCase, case_id)
    if not case or case.status == "published":
        case_id = f"case-draft-{user.id}"
        case = db.get(TeachingCase, case_id)
    if not case:
        case = TeachingCase(id=case_id, title="", source="", content="", status="draft")
        db.add(case)
    case.title = str(payload.get("title", case.title))
    case.source = str(payload.get("source", case.source))
    case.content = str(payload.get("content", case.content))
    db.commit()
    return {"id": case.id, "saved": True}


@app.post("/api/cases/{case_id}/publish")
def publish_case(case_id: str, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    require_role(user, "admin")
    case = db.get(TeachingCase, case_id)
    if not case:
        raise HTTPException(404, "案例草稿不存在。")
    if not case.title.strip() or not case.content.strip():
        raise HTTPException(422, "请填写案例标题和内容。")
    case.status = "published"
    db.commit()
    return {"id": case.id, "published": True}


@app.post("/api/tasks/publish", status_code=201)
def publish(payload: PublishInput, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    require_role(user, "teacher")
    classroom = db.get(Classroom, payload.classroomId)
    if not classroom or classroom.teacher_id != user.id:
        raise HTTPException(404, "发布班级不存在或不可访问。")
    if not payload.lessonDraft.get("goal", "").strip() or any(not str(block.get("content", "")).strip() for block in payload.lessonDraft.get("blocks", [])):
        raise HTTPException(422, "请填写学习目标和全部教学活动。")
    if not payload.lessonDraft.get("dueDate"):
        raise HTTPException(422, "请选择完成日期。")
    members = db.scalars(select(ClassMember.student_id).where(ClassMember.classroom_id == classroom.id)).all()
    if not members:
        raise HTTPException(422, "请先向班级添加至少一名学生，再发布学习任务。")
    # The request key makes a retried publish safe after a lost response.
    task_id = f"task-{hashlib.sha256((user.id + payload.idempotencyKey).encode()).hexdigest()[:32]}"
    existing = db.get(LearningTask, task_id)
    if existing:
        return {"taskId": existing.id, "created": False}
    snapshot = {k: payload.lessonDraft.get(k) for k in ("id", "caseId", "goal", "studentBase", "dueDate", "blocks")}
    lesson = db.get(Lesson, "lesson-equation")
    task = LearningTask(id=task_id, classroom_id=classroom.id, teacher_id=user.id, lesson_id=lesson.id, title=lesson.title, snapshot=snapshot, questions=payload.lessonDraft.get("questions") or QUESTIONS, due_date=snapshot["dueDate"])
    db.add(task)
    for member in db.scalars(select(ClassMember).where(ClassMember.classroom_id == classroom.id)).all():
        db.add(StudentRecord(id=f"record-{uuid.uuid4().hex}", task_id=task_id, student_id=member.student_id, drafts={}, observation="", source="live"))
    db.commit()
    return {"taskId": task_id, "created": True}


@app.post("/api/records/{task_id}/attempts", status_code=201)
def add_attempt(task_id: str, body: dict, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    require_role(user, "student")
    rec = db.scalar(select(StudentRecord).where(StudentRecord.task_id == task_id, StudentRecord.student_id == user.id))
    task = db.get(LearningTask, task_id)
    if not rec or not task:
        raise HTTPException(404, "没有找到本人的学习任务。")
    index = int(body.get("question", -1))
    questions = task.questions or []
    if index < 0 or index >= len(questions):
        raise HTTPException(422, "检查题编号无效。")
    answer = str(body.get("answer", "")).strip()
    if not answer:
        raise HTTPException(422, "请先填写答案。")
    attempt = Attempt(id=f"attempt-{uuid.uuid4().hex}", record_id=rec.id, question=index, answer=answer, reason=str(body.get("reason", "")), helped=bool(body.get("helped")), correct=answer == str(questions[index].get("answer", "")))
    db.add(attempt)
    if not attempt.correct:
        db.add(WrongQuestion(id=f"wrong-{uuid.uuid4().hex}", record_id=rec.id, attempt_id=attempt.id, prompt=str(questions[index].get("equation", "")), answer=answer, reason=attempt.reason))
    db.commit()
    return {"id": attempt.id, "correct": attempt.correct}


@app.post("/api/records/{task_id}/helps", status_code=201)
def add_help(task_id: str, body: dict, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    rec = db.scalar(select(StudentRecord).where(StudentRecord.task_id == task_id, StudentRecord.student_id == user.id))
    if not rec:
        raise HTTPException(404, "没有找到本人的学习任务。")
    item = HelpRecord(id=f"help-{uuid.uuid4().hex}", record_id=rec.id, question=body.get("question"), kind=str(body.get("kind", "提示")), message=str(body.get("message", "")), attempt_number=len(db.scalars(select(Attempt).where(Attempt.record_id == rec.id)).all()) + 1)
    db.add(item)
    db.commit()
    return {"id": item.id}


@app.post("/api/records/{task_id}/repairs", status_code=201)
def add_repair(task_id: str, body: dict, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    wrong = db.get(WrongQuestion, str(body.get("wrongId", "")))
    rec = db.get(StudentRecord, wrong.record_id) if wrong else None
    if not rec or rec.task_id != task_id or rec.student_id != user.id:
        raise HTTPException(404, "没有找到对应错题。")
    correct = str(body.get("answer", "")).strip() == "7" # Explicit scope: fixed demo variation only.
    item = RepairAttempt(id=f"repair-{uuid.uuid4().hex}", wrong_id=wrong.id, answer=str(body.get("answer", "")), reason=str(body.get("reason", "")), correct=correct)
    db.add(item)
    db.commit()
    return {"id": item.id, "correct": correct}


@app.post("/api/records/{task_id}/submit")
def submit_task(task_id: str, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    rec = db.scalar(select(StudentRecord).where(StudentRecord.task_id == task_id, StudentRecord.student_id == user.id))
    if not rec:
        raise HTTPException(404, "没有找到本人的学习任务。")
    rec.completed = True
    rec.submitted_at = datetime.utcnow()
    db.commit()
    return {"submitted": True, "submittedAt": rec.submitted_at.isoformat()}


@app.put("/api/records/{record_id}/feedback")
def save_feedback(record_id: str, body: dict, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    require_role(user, "teacher")
    rec = db.get(StudentRecord, record_id)
    task = db.get(LearningTask, rec.task_id) if rec else None
    if not rec or not task or task.teacher_id != user.id:
        raise HTTPException(404, "没有找到可反馈的学生记录。")
    feedback = str(body.get("feedback", "")).strip()
    if not feedback:
        raise HTTPException(422, "请填写反馈内容。")
    rec.feedback = feedback
    rec.feedback_at = datetime.utcnow()
    db.commit()
    return {"feedback": rec.feedback, "feedbackAt": rec.feedback_at.isoformat()}


@app.post("/api/files", status_code=201)
async def upload_file(request: Request, db: DB, file: UploadFile = File(...)) -> dict:
    user = current_user(request, db)
    content_type = file.content_type or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise HTTPException(415, "目前只接收图片文件。")
    contents = await file.read(12 * 1024 * 1024 + 1)
    if len(contents) > 12 * 1024 * 1024:
        raise HTTPException(413, "图片不能超过 12 MB。")
    file_id = f"file-{uuid.uuid4().hex}"
    storage_key = uuid.uuid4().hex
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    destination = STORAGE_DIR / storage_key
    destination.write_bytes(contents)
    asset = FileAsset(id=file_id, owner_id=user.id, original_name=Path(file.filename or "image").name[:255], content_type=content_type, size=len(contents), storage_key=storage_key)
    db.add(asset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    return {"id": asset.id, "url": f"/api/files/{asset.id}", "name": asset.original_name}


@app.get("/api/files/{file_id}")
def read_file(file_id: str, request: Request, db: DB) -> Response:
    user = current_user(request, db)
    asset = db.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(404, "图片不存在。")
    allowed = asset.owner_id == user.id
    if not allowed:
        allowed = db.scalar(select(ClassMember.student_id).join(StudentRecord, StudentRecord.student_id == ClassMember.student_id).join(LearningTask, LearningTask.id == StudentRecord.task_id).where(LearningTask.teacher_id == user.id, StudentRecord.student_id == asset.owner_id).limit(1)) is not None
    if user.role == "admin":
        allowed = True
    if not allowed:
        raise HTTPException(403, "没有权限查看此图片。")
    path = STORAGE_DIR / asset.storage_key
    if not path.is_file():
        raise HTTPException(404, "图片文件缺失，可重新上传。")
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type=asset.content_type, filename=asset.original_name)


@app.post("/api/legacy-import")
def import_legacy(body: dict, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    require_role(user, "admin")
    if body.get("confirmed") is not True:
        raise HTTPException(422, "请先确认历史演示数据导入。")
    source_id = str(body.get("sourceId", "browser-local-v1"))
    payload = body.get("data") or {}
    payload = payload.get("state") or payload
    source_hash = hashlib.sha256((source_id + json.dumps(payload, ensure_ascii=False, sort_keys=True)).encode()).hexdigest()
    tasks = payload.get("tasks") or []
    records = payload.get("records") or {}
    if not tasks and (payload.get("published") or records or payload.get("completed") or payload.get("attempts")):
        tasks = [{"id": "legacy-single-record", "snapshot": payload.get("lessonDraft") or {}, "questions": QUESTIONS, "dueDate": (payload.get("lessonDraft") or {}).get("dueDate", ""), "title": "历史演示记录"}]
    if not tasks:
        raise HTTPException(422, "没有找到可导入的学习任务或学生记录。")
    task_markers = [f"legacy-{hashlib.sha256((source_hash + str(old.get('id', i))).encode()).hexdigest()[:32]}" for i, old in enumerate(tasks)]
    if all(db.get(LearningTask, marker) for marker in task_markers):
        return {"imported": False, "reason": "already-imported", "taskIds": task_markers}
    classroom = db.get(Classroom, "class-legacy-demo")
    legacy_student = db.scalar(select(Account).where(Account.username == "legacy-demo-student"))
    if not legacy_student:
        legacy_student = Account(id="account-legacy-demo-student", username="legacy-demo-student", display_name="历史演示学生", role="student", password_hash=hash_password(secrets.token_urlsafe(32)), active=False)
        db.add(legacy_student)
    if not classroom:
        classroom = Classroom(id="class-legacy-demo", teacher_id=user.id, name="历史演示班级", grade="历史演示数据")
        db.add(classroom)
    if not db.get(ClassMember, {"classroom_id": classroom.id, "student_id": legacy_student.id}):
        db.add(ClassMember(classroom_id=classroom.id, student_id=legacy_student.id))
    db.flush()
    total = 0
    imported_ids = []
    for index, old_task in enumerate(tasks):
        marker = task_markers[index]
        if db.get(LearningTask, marker):
            imported_ids.append(marker)
            continue
        old_task_id = str(old_task.get("id", ""))
        old_record = records.get(old_task_id) or (records.get("task-legacy") if old_task_id == "task-legacy" else None) or {}
        snapshot = old_task.get("snapshot") or payload.get("lessonDraft") or {}
        task = LearningTask(id=marker, classroom_id=classroom.id, teacher_id=user.id, lesson_id="lesson-equation", title=str(old_task.get("title") or "历史演示记录"), snapshot={k: snapshot.get(k) for k in ("id", "caseId", "goal", "studentBase", "dueDate", "blocks")}, questions=old_task.get("questions") or QUESTIONS, due_date=str(old_task.get("dueDate", snapshot.get("dueDate", ""))), source="legacy-demo", published_at=import_datetime(old_task.get("publishedAt")) or datetime.utcnow())
        db.add(task)
        db.flush()
        rec = StudentRecord(id=f"record-{uuid.uuid4().hex[:32]}", task_id=task.id, student_id=legacy_student.id, observation=str(old_record.get("observation", "")), drafts=old_record.get("drafts") or {}, completed=bool(old_record.get("completed")), submitted_at=import_datetime(old_record.get("submittedAt")), feedback=str(old_record.get("feedback", "")), feedback_at=import_datetime(old_record.get("feedbackAt")), source="legacy-demo")
        db.add(rec)
        db.flush()
        old_attempts = old_record.get("attempts", [])
        attempt_map = {}
        for old in old_attempts:
            attempt_id = f"attempt-{uuid.uuid4().hex[:32]}"
            attempt_map[str(old.get("id", ""))] = attempt_id
            db.add(Attempt(id=attempt_id, record_id=rec.id, question=int(old.get("question", 0)), answer=str(old.get("answer", "")), reason=str(old.get("reason", "")), helped=bool(old.get("helped")), correct=bool(old.get("correct")), created_at=import_datetime(old.get("createdAt")) or datetime.utcnow()))
            total += 1
        wrong_map = {}
        for old in old_record.get("wrongQuestions", []):
            wrong_id = f"wrong-{uuid.uuid4().hex[:32]}"
            wrong_map[str(old.get("id", ""))] = wrong_id
            db.add(WrongQuestion(id=wrong_id, record_id=rec.id, attempt_id=attempt_map.get(str(old.get("attemptId", ""))), prompt=str(old.get("prompt", "")), answer=str(old.get("answer", "")), reason=str(old.get("reason", "")), file_id=file_id_from_url(old.get("image")), created_at=import_datetime(old.get("createdAt")) or datetime.utcnow()))
            total += 1
        db.flush()
        for old in old_record.get("helps", []):
            db.add(HelpRecord(id=f"help-{uuid.uuid4().hex[:32]}", record_id=rec.id, question=old.get("question"), kind=str(old.get("kind", "提示")), message=str(old.get("message", "")), file_id=file_id_from_url(old.get("image")), attempt_number=int(old.get("attemptNumber", 1)), created_at=import_datetime(old.get("createdAt")) or datetime.utcnow()))
            total += 1
        for old in old_record.get("repairs", []):
            wrong_id = wrong_map.get(str(old.get("wrongId", "")))
            if wrong_id:
                db.add(RepairAttempt(id=f"repair-{uuid.uuid4().hex[:32]}", wrong_id=wrong_id, answer=str(old.get("answer", "")), reason=str(old.get("reason", "")), correct=bool(old.get("correct")), created_at=import_datetime(old.get("createdAt")) or datetime.utcnow()))
                total += 1
        imported_ids.append(marker)
    try:
        db.commit()
    except Exception as error:
        db.rollback()
        raise HTTPException(422, "历史记录关联不完整，导入未完成；请检查数据后重试。") from error
    return {"imported": True, "taskIds": imported_ids, "records": total, "source": "legacy-demo"}
