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
from .models import Account, Attempt, ClassMember, Classroom, FileAsset, HelpRecord, LearningTask, Lesson, LessonDraft, LoginSession, RepairAttempt, StudentRecord, SupplementRecipient, SupplementalInstruction, SupportIssue, TeachingCase, WrongQuestion
from .seed import BLOCKS, CASE_TEXT, QUESTIONS, ensure_seed
from .security import hash_password, verify_password
from .grading import assess, assess_repair
from .library import current_case as published_case_json
from .model_provider import ModelError
from fastapi.responses import JSONResponse

app = FastAPI(title="师承智学业务服务", version="0.1.0")


@app.exception_handler(ModelError)
async def model_configuration_error(request: Request, error: ModelError):
    return JSONResponse(status_code=422, content={"detail": str(error)})

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
    grade: str = Field(default="",max_length=80)
    subject: str = Field(default="",max_length=80)


class MemberInput(BaseModel):
    studentId: str


class IssueReplyInput(BaseModel):
    reply: str = Field(min_length=1, max_length=10000)


class PlatformInput(BaseModel):
    data: dict


class PublishInput(BaseModel):
    classroomId: str
    lessonDraft: dict
    lessonId: str | None = None
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
    record_task=db.get(LearningTask,rec.task_id)
    question_id=lambda index:record_task.questions[index].get("id") if record_task and isinstance(index,int) and 0<=index<len(record_task.questions) else None
    attempts = db.scalars(select(Attempt).where(Attempt.record_id == rec.id).order_by(Attempt.created_at)).all()
    helps = db.scalars(select(HelpRecord).where(HelpRecord.record_id == rec.id).order_by(HelpRecord.created_at)).all()
    wrongs = db.scalars(select(WrongQuestion).where(WrongQuestion.record_id == rec.id).order_by(WrongQuestion.created_at)).all()
    from .remediation import serialize as wrong_json_for
    wrong_json=[wrong_json_for(db,item) for item in wrongs]
    from .insights import record_metrics
    metrics=record_metrics(db,rec,record_task,attempts,helps)
    return {"metrics":metrics,"memberActive":bool(record_task and db.get(ClassMember,(record_task.classroom_id,rec.student_id))),"id": rec.id, "taskId": rec.task_id, "studentId": rec.student_id, "studentName": student.display_name if student else "学生", "observation": rec.observation, "drafts": rec.drafts or {}, "attempts": [{"id": a.id, "taskId": rec.task_id, "question": a.question, "questionId":question_id(a.question), "answer": a.answer, "reason": a.reason, "helped": a.helped, "correct": a.correct, "verification": a.verification, "createdAt": a.created_at.isoformat()} for a in attempts], "helps": [{"id": h.id, "taskId": rec.task_id, "question": h.question, "questionId":question_id(h.question), "kind": h.kind, "message": h.message, "image": file_url(h.file_id), "attemptNumber": h.attempt_number, "createdAt": h.created_at.isoformat()} for h in helps], "repairs": [repair for wrong in wrong_json for repair in wrong["repairs"]], "wrongQuestions": wrong_json, "completed": rec.completed, "submittedAt": rec.submitted_at.isoformat() if rec.submitted_at else None, "feedback": rec.feedback, "feedbackAt": rec.feedback_at.isoformat() if rec.feedback_at else None, "updatedAt": rec.updated_at.isoformat() if rec.updated_at else None}


def platform_data(db: Session, user: Account, lesson_id=None) -> dict:
    classrooms = db.scalars(select(Classroom).order_by(Classroom.created_at)).all()
    if user.role == "teacher":
        classrooms = [c for c in classrooms if c.teacher_id == user.id]
    elif user.role == "student":
        memberships = db.scalars(select(ClassMember.classroom_id).where(ClassMember.student_id == user.id)).all()
        classrooms = [c for c in classrooms if c.id in memberships]
    classroom = classrooms[0] if classrooms else None
    lessons = db.scalars(select(Lesson).order_by(Lesson.position)).all()
    lesson = db.get(Lesson,lesson_id) if lesson_id else db.get(Lesson,"lesson-equation") or (lessons[0] if lessons else None)
    if lesson_id and not lesson:raise HTTPException(404,"课时不存在。")
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
        tasks = db.scalars(select(LearningTask).join(StudentRecord).where(StudentRecord.student_id==user.id).order_by(LearningTask.published_at.desc())).all()
    elif user.role == "admin":
        tasks = [] # Admin operations do not expose unrelated student learning records.
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
            recs = db.scalars(select(StudentRecord).where(StudentRecord.task_id == task.id)).all()
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
            from .issues import permitted
            issue = next((i for i in db.scalars(select(SupportIssue).where(SupportIssue.owner_id.in_(member_ids)).order_by(SupportIssue.updated_at.desc())) if permitted(db,user,i)),None)
    messages = []
    supplements = []
    task_ids = [item["id"] for item in task_json]
    if task_ids:
        rows=db.scalars(select(SupplementalInstruction).where(SupplementalInstruction.task_id.in_(task_ids)).order_by(SupplementalInstruction.created_at)).all()
        supplements=[{'id':i.id,'taskId':i.task_id,'content':i.content,'kind':i.kind,'createdAt':i.created_at.isoformat()} for i in rows if user.role!='student' or db.get(SupplementRecipient,(i.id,user.id)) or (i.kind=='note' and not db.scalar(select(SupplementRecipient.student_id).where(SupplementRecipient.instruction_id==i.id).limit(1)))]
    if user.role == "student":
        for task_id, rec in records.items():
            if rec.get("feedback"):
                task = next((item for item in task_json if item["id"] == task_id), None)
                messages.append({"id": rec["id"], "taskId": task_id, "title": f"{task['title'] if task else '课程'} · 教师反馈", "createdAt": rec.get("feedbackAt")})
    result = {"version": 2, "currentUser": account_json(user), "classroom": {"id": classroom.id, "name": classroom.name, "grade": classroom.grade, "teacherId": classroom.teacher_id,"subject":classroom.subject} if classroom else None, "classrooms": [{"id": c.id, "name": c.name, "grade": c.grade, "teacherId": c.teacher_id,"subject":c.subject} for c in classrooms], "members": [{"id": m.id, "displayName": m.display_name, "username": m.username} for m in db.scalars(select(Account).join(ClassMember, ClassMember.student_id == Account.id).where(ClassMember.classroom_id == classroom.id)).all()] if classroom and user.role == "teacher" else [], "lesson": {"id": lesson.id, "title": lesson.title, "courseId": lesson.course_id} if lesson else None, "caseDraft": {"id": first_case.id, "title": first_case.title, "source": first_case.source, "content": first_case.content, "reviewed": first_case.status == "published", "fileName": "", "updatedAt": first_case.updated_at.isoformat()} if first_case else {"id": "case-balance", "title": "天平与等式性质", "source": "", "content": CASE_TEXT, "reviewed": False, "fileName": ""}, "publishedCase": published_case_json(db,case.id) if case else None, "lessonDraft": {"id": draft.id, "caseId": draft.case_id, "caseSnapshot": draft.case_snapshot, "lessonSnapshot": draft.lesson_snapshot, "lessonId":draft.lesson_id, "goal": draft.goal, "studentBase": draft.student_base, "dueDate": draft.due_date, "blocks": draft.blocks, "questions": draft.questions, "revision":draft.revision, "planningDetails":draft.planning_details or {}, "updatedAt": draft.updated_at.isoformat()} if draft else {"id": "draft-equation", "caseId": case.id if case else None, "goal": "理解并应用等式两边的共同变化", "studentBase": "", "dueDate": "", "blocks": BLOCKS, "questions": QUESTIONS}, "tasks": task_json, "records": records, "studentRecords": student_records, "activeTaskId": task_json[0]["id"] if task_json else None, "activeStudentId": next(iter(student_records.values()))[0]["studentId"] if student_records and next(iter(student_records.values())) else user.id, "favorite": False, "issue": {"id": issue.id, "text": issue.text, "reply": issue.reply, "resolved": issue.resolved, "updatedAt": issue.updated_at.isoformat()} if issue else {"id": "issue-empty", "text": "", "reply": "", "resolved": False}, "supplements": supplements, "messages": messages}
    from .teaching import task_json,materialize_messages,message_json
    from .models import BusinessMessage
    for entry,task in zip(result['tasks'],tasks):entry.update(task_json(db,user,task))
    if user.role in ('teacher','student'):
        materialize_messages(db,user);db.commit()
        result['messages']=[message_json(db,m) for m in db.scalars(select(BusinessMessage).where(BusinessMessage.recipient_id==user.id).order_by(BusinessMessage.created_at.desc()).limit(100))]
    from .curriculum import apply_template, student_content
    if lesson and not draft:result['lessonDraft']=apply_template(db,lesson)
    if user.role=='student':
        result['lessonDraft']={'blocks':[],'questions':[],'goal':''}
        result['caseDraft']=None
        for item in result['tasks']:
            item['snapshot']=student_content(item['snapshot'])
            if item['snapshot'].get('lessonSnapshot'):item['snapshot']['lessonSnapshot']=student_content(item['snapshot']['lessonSnapshot'])
            item['questions']=student_content({'questions':item['questions']})['questions']
    return result


@app.on_event("startup")
def startup() -> None:
    if os.getenv("SCZX_AUTO_CREATE_SCHEMA", "false").lower() == "true":
        from .database import Base, engine
        Base.metadata.create_all(engine)
        ensure_seed()


@app.on_event("startup")
async def start_model_worker():
    from .model_jobs import start
    await start()


@app.on_event("shutdown")
async def stop_model_worker():
    from .model_jobs import stop
    await stop()


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
    if not payload.name.strip():raise HTTPException(422,"请填写班级名称。")
    classroom = Classroom(id=f"class-{uuid.uuid4().hex}", teacher_id=user.id, name=payload.name.strip(), grade=payload.grade.strip(), subject=payload.subject.strip())
    db.add(classroom)
    db.commit()
    return {"id": classroom.id, "name": classroom.name, "grade": classroom.grade,"subject":classroom.subject}


@app.post("/api/classrooms/{classroom_id}/members", status_code=201)
def add_member(classroom_id: str, payload: MemberInput, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    from .teaching import owned_class
    room = owned_class(db,user,classroom_id,True)
    if not room or room.teacher_id != user.id:
        raise HTTPException(404, "没有找到此班级。")
    student = db.get(Account, payload.studentId)
    if not student or student.role != "student" or not student.active:
        raise HTTPException(404, "没有找到可加入的学生账号。")
    if db.scalar(select(ClassMember).where(ClassMember.classroom_id==room.id,ClassMember.student_id==student.id).with_for_update()):
        return account_json(student)
    db.add(ClassMember(classroom_id=room.id, student_id=student.id))
    db.commit()
    return account_json(student)


@app.put("/api/issues/{issue_id}/reply")
def reply_issue(issue_id: str, payload: IssueReplyInput, request: Request, db: DB) -> dict:
    from .issues import transition
    row=db.get(SupportIssue,issue_id)
    if not row:raise HTTPException(404,"没有找到这条学习疑问。")
    require_role(current_user(request,db),"teacher")
    result=transition(issue_id,{"status":"replied","content":payload.reply,"requestKey":uuid.uuid4().hex,"expectedRevision":row.revision},request,db)
    return {"reply":result["reply"],"resolved":result["resolved"],"updatedAt":result["updatedAt"]}



@app.get("/api/classrooms/{classroom_id}/members")
def list_members(classroom_id: str, request: Request, db: DB) -> list[dict]:
    user = current_user(request, db)
    room = db.get(Classroom, classroom_id)
    if not room or room.teacher_id != user.id:
        raise HTTPException(404, "没有找到此班级。")
    result=[]
    for a in db.scalars(select(Account).join(ClassMember,ClassMember.student_id==Account.id).where(ClassMember.classroom_id==room.id).order_by(Account.display_name)):
        own_rooms=db.scalars(select(Classroom).join(ClassMember).where(ClassMember.student_id==a.id,Classroom.teacher_id==user.id)).all()
        result.append({**account_json(a),'classes':[{'id':c.id,'name':c.name} for c in own_rooms]})
    return result


@app.get("/api/platform")
def get_platform(request: Request, db: DB) -> dict:
    return platform_data(db, current_user(request, db), request.query_params.get("lessonId"))


@app.put("/api/platform")
def save_platform(payload: PlatformInput, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    data = payload.data
    try:
        if user.role == "teacher":
            draft = data.get("lessonDraft") or {}
            lesson_id = draft.get("lessonId") or data.get("lesson", {}).get("id")
            if not lesson_id or not db.get(Lesson,lesson_id):raise HTTPException(422,"请选择有效课时。")
            record = db.scalar(select(LessonDraft).where(LessonDraft.teacher_id == user.id, LessonDraft.lesson_id == lesson_id).with_for_update())
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
                from .drafts import check_revision, snapshot, preserve_original, checkpoint, normalized_details
                check_revision(record,draft.get('revision',0))
                before=snapshot(record)
                if record.id and record.revision is not None:preserve_original(db,record)
                previous_case_id = record.case_id
                record.case_id = draft.get("caseId")
                from .library import current_case
                supplied = draft.get('caseSnapshot') or {}
                if supplied.get('versionId'):
                    selected = current_case(db, record.case_id, supplied['versionId'])
                    if not selected: raise HTTPException(422,'参考案例版本不存在，请重新选择。')
                    record.case_snapshot = selected
                elif not record.case_id:
                    record.case_snapshot = None
                elif record.case_id != previous_case_id:
                    record.case_snapshot = current_case(db,record.case_id)
                # 没有历史版本记录的旧教案不由聚合自动保存补造版本。
                record.goal = str(draft.get("goal", ""))
                record.student_base = str(draft.get("studentBase", ""))
                record.due_date = str(draft.get("dueDate", ""))
                record.blocks = draft.get("blocks") or []
                record.questions = draft.get("questions", [])
                supplied_lesson=draft.get('lessonSnapshot') or {}
                if supplied_lesson.get('versionId'):
                    from .curriculum import published_lesson
                    chosen=published_lesson(db,lesson_id,supplied_lesson['versionId'])
                    if not chosen:raise HTTPException(422,'课时版本不存在。')
                    record.lesson_snapshot=chosen
                record.planning_details=normalized_details(db,draft.get('planningDetails'))
                after=snapshot(record)
                if any(before.get(k)!=after.get(k) for k in after if k!='revision'):checkpoint(db,record,'教师保存')
            for task_id, record_data in (data.get("records") or {}).items():
                if isinstance(record_data, list):
                    continue
                rec = db.get(StudentRecord, record_data.get("id", ""))
                task = db.get(LearningTask, rec.task_id) if rec else None
                if rec and task and task.teacher_id == user.id:
                    text=str(record_data.get("feedback", ""))
                    if text!=rec.feedback:
                        rec.feedback=text;rec.feedback_at=datetime.utcnow() if text else None
                        from .teaching import feedback_message
                        feedback_message(db,task,rec)
            for item in data.get("supplements", []):
                task = db.get(LearningTask, str(item.get("taskId", "")))
                if task and task.teacher_id == user.id:
                    supplement = db.get(SupplementalInstruction, str(item.get("id", "")))
                    if not supplement:
                        supplement = SupplementalInstruction(id=str(item.get("id") or f"supp-{uuid.uuid4().hex[:32]}"), task_id=task.id, teacher_id=user.id, content="")
                        db.add(supplement)
                    if supplement.kind=="note":supplement.content = str(item.get("content", ""))
        elif user.role == "admin":
            pass  # 案例独立接口保存；聚合自动保存不改写案例草稿或发布版本。
        elif user.role == "student":
            for task_id, record_data in (data.get("records") or {}).items():
                rec = db.scalar(select(StudentRecord).where(StudentRecord.task_id == task_id, StudentRecord.student_id == user.id))
                if not rec:
                    continue
                if not db.get(ClassMember,(db.get(LearningTask,rec.task_id).classroom_id,user.id)):continue
                rec.observation = str(record_data.get("observation", ""))
                from .visualization import validate_progress
                drafts=record_data.get("drafts") or {}
                try:validate_progress(db.get(LearningTask,rec.task_id),drafts)
                except (ValueError,TypeError) as error:raise HTTPException(422,str(error)) from None
                rec.drafts = drafts
                # Completion is committed by the dedicated submit endpoint.
                current_attempts = {item.id: item for item in db.scalars(select(Attempt).where(Attempt.record_id == rec.id)).all()}
                for item in record_data.get("attempts", []):
                    attempt = current_attempts.get(str(item.get("id", "")))
                    if attempt:continue
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
                    attempt.verification = assess(answer, expected, task.questions[idx].get("equation", ""))
                    attempt.correct = attempt.verification["correct"]
                current_helps = {item.id: item for item in db.scalars(select(HelpRecord).where(HelpRecord.record_id == rec.id)).all()}
                for item in record_data.get("helps", []):
                    help_item = current_helps.get(str(item.get("id", "")))
                    if help_item:continue  # Broad autosave cannot rewrite original help evidence.
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
                    if wrong.id in current_wrongs:continue
                    wrong.owner_id=user.id
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
                        if repair.id in old_repairs:continue
                        repair.answer = str(repair_data.get("answer", ""))
                        repair.reason = str(repair_data.get("reason", ""))
                        repair.verification = {"status":"unverified","correct":False,"scope":"旧版兼容录入，无明确练习关联"}
                        repair.correct = repair.verification["correct"]
            issue_data = data.get("issue") or {}
            issue = db.get(SupportIssue, issue_data.get("id", ""))
            if not issue and str(issue_data.get("text", "")).strip():
                issue = SupportIssue(id=str(issue_data.get("id") or f"issue-{uuid.uuid4().hex[:32]}"), owner_id=user.id, text="")
                db.add(issue)
            if issue and issue.owner_id == user.id and issue in db.new:
                issue.text = str(issue_data.get("text", issue.text))
                # Existing replies and states are controlled by the scoped queue only.
                issue.reply = ""
                issue.resolved = False
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"saved": True, **({"draftRevision":record.revision} if user.role=="teacher" else {})}


@app.put("/api/cases/draft")
def save_case(payload: dict, request: Request, db: DB) -> dict:
    from .library_routes import save_draft, new_case, revise
    from .library import draft_json
    from .models import CaseDraftContent
    user = current_user(request, db)
    require_role(user, 'admin')
    case_id = payload.get('id')
    case = db.get(TeachingCase, case_id) if case_id else None
    if not case:
        created = new_case({'title':payload.get('title','新案例')}, request, db)
        case_id = created['id']
    if not db.get(CaseDraftContent, case_id): revise(case_id,request,db)
    draft = db.get(CaseDraftContent, case_id)
    data = {**draft.data, **{k:payload[k] for k in ('title','content','source') if k in payload}}
    save_draft(case_id, {'data':data}, request, db)
    return {'id':case_id,'saved':True}


@app.post("/api/cases/{case_id}/publish")
def publish_case(case_id: str, request: Request, db: DB) -> dict:
    from .library_routes import publish_case as publish_version
    result = publish_version(case_id, request, db)
    return {'id':case_id,'published':True,'version':result['published']['version']}


@app.post("/api/tasks/publish", status_code=201)
def publish(payload: PublishInput, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    require_role(user, "teacher")
    classroom = db.scalar(select(Classroom).where(Classroom.id==payload.classroomId).with_for_update())
    if not classroom or classroom.teacher_id != user.id:
        raise HTTPException(404, "发布班级不存在或不可访问。")
    if not payload.lessonDraft.get("goal", "").strip() or any(not str(block.get("content", "")).strip() for block in payload.lessonDraft.get("blocks", [])):
        raise HTTPException(422, "请填写学习目标和全部教学活动。")
    members = db.scalars(select(ClassMember.student_id).where(ClassMember.classroom_id == classroom.id)).all()
    if not members:
        raise HTTPException(422, "请先向班级添加至少一名学生，再发布学习任务。")
    from .teaching import cutoff
    cutoff(payload.lessonDraft.get("dueDate"),True)
    # The request key makes a retried publish safe after a lost response.
    task_id = f"task-{hashlib.sha256((user.id + payload.idempotencyKey).encode()).hexdigest()[:32]}"
    existing = db.scalar(select(LearningTask).where(LearningTask.id==task_id).with_for_update())
    if existing:
        return {"taskId": existing.id, "created": False}
    snapshot = {k: payload.lessonDraft.get(k) for k in ("id", "caseId", "goal", "studentBase", "dueDate", "blocks", "planningDetails", "revision")}
    snapshot["dueDate"]=str(payload.lessonDraft.get("dueDate") or "")
    from .library import current_case
    supplied = payload.lessonDraft.get('caseSnapshot') or {}
    snapshot['caseSnapshot'] = current_case(db, snapshot.get('caseId'), supplied.get('versionId')) if snapshot.get('caseId') else None
    if supplied.get('versionId') and not snapshot['caseSnapshot']: raise HTTPException(422,'参考案例版本不存在，请重新选择。')
    lesson_id=payload.lessonId or payload.lessonDraft.get('lessonId')
    if not lesson_id:raise HTTPException(422,'请选择要发布的课时。')
    lesson=db.get(Lesson,lesson_id)
    if not lesson:raise HTTPException(404,'课时不存在。')
    from .curriculum import published_lesson, content_errors
    supplied_lesson=payload.lessonDraft.get('lessonSnapshot') or {}
    if not supplied_lesson.get('versionId'):raise HTTPException(422,'请先在备课页使用已发布课时内容，再发布任务。')
    version=published_lesson(db,lesson_id,supplied_lesson.get('versionId')) if supplied_lesson.get('versionId') else None
    if supplied_lesson.get('versionId') and not version:raise HTTPException(422,'课时版本不存在。')
    if version:
        if not published_lesson(db,lesson_id):raise HTTPException(422,'课时已停用，不能发布新任务。')
        errors=content_errors(db,{**version,**payload.lessonDraft,'title':version['title'],
                                 'caseVersionId':(snapshot.get('caseSnapshot') or {}).get('versionId')})
        if errors:raise HTTPException(422,'；'.join(errors))
        snapshot['lessonSnapshot']=version
    task = LearningTask(id=task_id, classroom_id=classroom.id, teacher_id=user.id, lesson_id=lesson.id, title=version["title"] if version else lesson.title, snapshot=snapshot, questions=payload.lessonDraft.get("questions", []), due_date=snapshot["dueDate"],published_at=datetime.utcnow())
    db.add(task)
    db.flush()
    from .teaching import assign
    for member in db.scalars(select(ClassMember).where(ClassMember.classroom_id == classroom.id)).all():assign(db,task,member.student_id)
    db.commit()
    return {"taskId": task_id, "created": True}


@app.post("/api/records/{task_id}/attempts", status_code=201)
def add_attempt(task_id: str, body: dict, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    from .teaching import ensure_write
    ensure_write(db,user,task_id)
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
    from .curriculum import assess_question
    verification = assess_question(answer,questions[index])
    received_help=bool(db.scalar(select(HelpRecord.id).where(HelpRecord.record_id==rec.id,HelpRecord.question==index)))
    attempt = Attempt(id=f"attempt-{uuid.uuid4().hex}", record_id=rec.id, question=index, answer=answer, reason=str(body.get("reason", "")), helped=received_help or bool(body.get("helped")), correct=verification["correct"], verification=verification)
    db.add(attempt)
    if verification["status"] == "inconsistent":
        db.flush()
        source_image=db.scalar(select(HelpRecord.file_id).where(HelpRecord.record_id==rec.id,HelpRecord.question==index,HelpRecord.file_id.is_not(None)).order_by(HelpRecord.created_at.desc()).limit(1))
        source_image=source_image or file_id_from_url(questions[index].get('imageUrl'))
        db.add(WrongQuestion(id=f"wrong-{uuid.uuid4().hex}", owner_id=user.id, record_id=rec.id, attempt_id=attempt.id, prompt=str(questions[index].get("equation", "")), answer=answer, reason=attempt.reason,file_id=source_image,details={'version':'dynamic_v1','source':'course','equation':str(questions[index].get('equation','')),'originalPrompt':str(questions[index].get('prompt','')),'knowledgeIds':questions[index].get('knowledgeIds',[]),'cause':'其他或待确认','causeConfirmed':False}))
    db.commit()
    return {"id": attempt.id, "correct": attempt.correct, "verification": verification}


@app.post("/api/records/{task_id}/helps", status_code=201)
def add_help(task_id: str, body: dict, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    from .teaching import ensure_write
    ensure_write(db,user,task_id)
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
    from .teaching import ensure_write
    ensure_write(db,user,task_id)
    wrong = db.get(WrongQuestion, str(body.get("wrongId", "")))
    rec = db.get(StudentRecord, wrong.record_id) if wrong else None
    if not rec or rec.task_id != task_id or rec.student_id != user.id:
        raise HTTPException(404, "没有找到对应错题。")
    from .remediation import save_attempt
    return save_attempt(db,user,wrong,body)


@app.post("/api/records/{task_id}/submit")
def submit_task(task_id: str, request: Request, db: DB) -> dict:
    user = current_user(request, db)
    from .teaching import ensure_write
    ensure_write(db,user,task_id)
    rec = db.scalar(select(StudentRecord).where(StudentRecord.task_id == task_id, StudentRecord.student_id == user.id))
    if not rec:
        raise HTTPException(404, "没有找到本人的学习任务。")
    from .curriculum import completion_missing
    task=db.get(LearningTask,task_id)
    missing=completion_missing(task,rec,db.scalars(select(Attempt).where(Attempt.record_id==rec.id)).all())
    if missing:raise HTTPException(422,'请先完成：'+'、'.join(missing))
    if not rec.completed:
        rec.completed = True
        rec.submitted_at = datetime.now(timezone.utc).replace(tzinfo=None,microsecond=0)
        from .teaching import message
        message(db,task,task.teacher_id,'submission',sender=user.id,event_key=user.id)
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
    from .teaching import feedback_message
    feedback_message(db,task,rec)
    db.commit()
    return {"feedback": rec.feedback, "feedbackAt": rec.feedback_at.isoformat()}


@app.post("/api/files", status_code=201)
async def upload_file(request: Request, db: DB, file: UploadFile = File(...)) -> dict:
    user = current_user(request, db)
    content_type = file.content_type or "application/octet-stream"
    if not content_type.startswith(("image/", "audio/")):
        raise HTTPException(415, "请选择图片或音频文件。")
    contents = await file.read(12 * 1024 * 1024 + 1)
    if len(contents) > 12 * 1024 * 1024:
        raise HTTPException(413, "文件不能超过 12 MB。")
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
        allowed = db.scalar(select(HelpRecord.id).join(StudentRecord,HelpRecord.record_id==StudentRecord.id).join(LearningTask,LearningTask.id==StudentRecord.task_id).where(LearningTask.teacher_id==user.id,HelpRecord.file_id==file_id).limit(1)) is not None
        if not allowed:
            allowed = db.scalar(select(WrongQuestion.id).join(StudentRecord,WrongQuestion.record_id==StudentRecord.id).join(LearningTask,LearningTask.id==StudentRecord.task_id).where(LearningTask.teacher_id==user.id,(WrongQuestion.file_id==file_id)|(WrongQuestion.details['cropFileId'].as_string()==file_id)).limit(1)) is not None
        if not allowed:
            from .models import ModelJob
            allowed = db.scalar(select(ModelJob.id).join(StudentRecord,ModelJob.record_id==StudentRecord.id).join(LearningTask,LearningTask.id==StudentRecord.task_id).where(LearningTask.teacher_id==user.id,ModelJob.file_id==file_id).limit(1)) is not None
    if user.role == "admin":
        allowed = True
    if not allowed:
        from .models import MaterialUnit, SourceMaterial
        from .library import published_unit
        for unit in db.scalars(select(MaterialUnit).outerjoin(SourceMaterial, MaterialUnit.material_id==SourceMaterial.id).where((MaterialUnit.image_file_id==file_id) | (SourceMaterial.file_id==file_id))).all():
            if published_unit(db,unit.id): allowed=True; break
    if not allowed:
        from .models import LessonVersion
        for version in db.scalars(select(LessonVersion)).all():
            if any(b.get('imageUrl')=='/api/files/'+file_id for b in version.data.get('blocks',[])):allowed=True;break
    if not allowed:raise HTTPException(403,'没有权限查看此文件。')
    path = STORAGE_DIR / asset.storage_key
    if not path.is_file():
        raise HTTPException(404, "图片文件缺失，可重新上传。")
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type=asset.content_type, filename=asset.original_name, content_disposition_type="inline" if request.query_params.get("inline")=="1" and asset.content_type.startswith(("image/", "application/pdf")) else "attachment")


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
        task = LearningTask(id=marker, classroom_id=classroom.id, teacher_id=user.id, lesson_id="lesson-equation", title=str(old_task.get("title") or "历史演示记录"), snapshot={k: snapshot.get(k) for k in ("id", "caseId", "goal", "studentBase", "dueDate", "blocks", "planningDetails", "revision")}, questions=old_task.get("questions") or QUESTIONS, due_date=str(old_task.get("dueDate", snapshot.get("dueDate", ""))), source="legacy-demo", published_at=import_datetime(old_task.get("publishedAt")) or datetime.utcnow())
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


from .ai_routes import router as ai_router
app.include_router(ai_router)

from .library_routes import router as library_router
app.include_router(library_router)

from .curriculum import router as curriculum_router
app.include_router(curriculum_router)

from .drafts import router as preparation_router
app.include_router(preparation_router)

from .teaching import router as teaching_router
app.include_router(teaching_router)

from .remediation import router as remediation_router
app.include_router(remediation_router)

from .learning_memory import router as learning_memory_router
app.include_router(learning_memory_router)

from .insights import router as insights_router
from .issues import router as support_router
app.include_router(insights_router)
app.include_router(support_router)

from .unit_learning import router as unit_learning_router
app.include_router(unit_learning_router)

# Optional production frontend: hash routes share the same origin as the API.
if os.getenv('SCZX_FRONTEND_DIST'):
    from fastapi.staticfiles import StaticFiles
    frontend_dist=Path(os.environ['SCZX_FRONTEND_DIST']).resolve()
    if not (frontend_dist/'index.html').is_file():raise RuntimeError('SCZX_FRONTEND_DIST缺少生产构建index.html')
    app.mount('/',StaticFiles(directory=frontend_dist,html=True),name='frontend')
