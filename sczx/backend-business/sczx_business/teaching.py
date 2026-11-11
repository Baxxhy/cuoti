"""Class-scoped teaching, assignment lifecycle and durable HTTP notifications."""
import copy,hashlib,secrets,uuid,json
from datetime import datetime,timedelta,time,date,timezone
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field
from sqlalchemy import select,func,or_
from sqlalchemy.dialects.mysql import insert
from .database import get_db
from .models import Account,Classroom,ClassMember,LearningTask,StudentRecord,Attempt,HelpRecord,ClassInvite,JoinThrottle,BusinessMessage,SupplementalInstruction,SupplementRecipient
router=APIRouter(prefix='/api/teaching')
def now():return datetime.now(timezone.utc).replace(tzinfo=None)
def iso(value):return value.isoformat()+'Z' if value else None
def uid(prefix):return prefix+'-'+uuid.uuid4().hex[:32]
def user_for(request,db):
    from .main import current_user
    return current_user(request,db)
def owned_class(db,user,ident,lock=False):
    stmt=select(Classroom).where(Classroom.id==ident,Classroom.teacher_id==user.id)
    room=db.scalar(stmt.with_for_update() if lock else stmt)
    if user.role!='teacher' or not room:raise HTTPException(404,'没有找到可管理的班级。')
    return room
def member(db,room,student):return db.get(ClassMember,(room,student)) is not None
def ensure_write(db,user,task_id):
    task=db.get(LearningTask,task_id)
    if task:db.scalar(select(Classroom).where(Classroom.id==task.classroom_id).with_for_update())
    active=db.scalar(select(ClassMember).where(ClassMember.classroom_id==task.classroom_id,ClassMember.student_id==user.id).with_for_update()) if task else None
    if task and task.snapshot.get('withdrawnAt'):raise HTTPException(409,'教师已撤回任务，仅可回看。')
    if not task or user.role!='student' or not active:raise HTTPException(403,'已移出班级的学习记录仅可回看，不能继续提交。')
    return task
def accessible_task(db,user,ident,lock=False):
    stmt=select(LearningTask).where(LearningTask.id==ident)
    task=db.scalar(stmt.with_for_update() if lock else stmt)
    allowed=task and ((user.role=='teacher' and task.teacher_id==user.id) or (user.role=='student' and db.scalar(select(StudentRecord.id).where(StudentRecord.task_id==ident,StudentRecord.student_id==user.id))))
    if not allowed:raise HTTPException(404,'没有找到有权限的学习任务。')
    return task

def cutoff(value,strict=False):
    if not value:return None
    try:
        if len(value)==10:dt=datetime.combine(date.fromisoformat(value),time.max).replace(tzinfo=ZoneInfo('Asia/Shanghai'))
        else:
            dt=datetime.fromisoformat(value.replace('Z','+00:00'))
            if dt.tzinfo is None:dt=dt.replace(tzinfo=ZoneInfo('Asia/Shanghai'))
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError,TypeError):
        if strict:raise HTTPException(422,'截止日期无效，请使用有效日期或带时区的时间。') from None
        return None

def has_started(rec):return bool(rec.observation or rec.drafts or rec.completed)
def personal_status(rec,due,active=True,clock=None):
    if not active:return '历史只读'
    if rec.completed:return '已反馈' if rec.feedback else '已提交'
    if due and (clock or now())>due:return '已逾期'
    return '学习中' if has_started(rec) else '待开始'
def summary(db,task):
    recs=db.scalars(select(StudentRecord).where(StudentRecord.task_id==task.id)).all();active=set(db.scalars(select(ClassMember.student_id).where(ClassMember.classroom_id==task.classroom_id)))
    # Attempts can exist without a saved browser draft.
    attempted=set(db.scalars(select(Attempt.record_id).where(Attempt.record_id.in_([r.id for r in recs])))) if recs else set()
    due=cutoff(task.due_date);submitted=sum(r.completed for r in recs);feedback=sum(bool(r.feedback) for r in recs)
    overdue=sum(not r.completed and r.student_id in active and bool(due and now()>due) for r in recs)
    started=sum(has_started(r) or r.id in attempted for r in recs)
    from .insights import metrics
    from .learning_memory import collect
    facts=[e for r in recs if r.student_id in active for e in collect(db,r.student_id,task.teacher_id,{task.classroom_id})[0] if e['taskId']==task.id]
    return {'metrics':metrics(facts),'members':len(active),'assigned':len(recs),'started':started,'submitted':submitted,'unsubmitted':len(recs)-submitted,'overdue':overdue,'feedback':feedback,'inactive':sum(r.student_id not in active for r in recs),'status':'未分配' if not recs else '已完成反馈' if feedback==len(recs) and submitted==len(recs) else '全员已提交' if submitted==len(recs) else '有逾期' if overdue else '学习中' if started else '待开始'}
def task_json(db,user,task):
    from .models import Lesson
    room=db.get(Classroom,task.classroom_id);rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==task.id,StudentRecord.student_id==user.id)) if user.role=='student' else None
    result={'unitId':db.get(Lesson,task.lesson_id).unit_id,'id':task.id,'lessonId':task.lesson_id,'classId':task.classroom_id,'className':room.name,'title':task.title,'dueDate':task.due_date,'dueAt':iso(cutoff(task.due_date)),'publishedAt':iso(task.published_at),'teacherName':db.get(Account,task.teacher_id).display_name,'source':task.source}
    if user.role=='teacher':result['summary']=summary(db,task)
    elif rec:
        status=personal_status(rec,cutoff(task.due_date),member(db,task.classroom_id,user.id))
        if status=='待开始' and db.scalar(select(Attempt.id).where(Attempt.record_id==rec.id).limit(1)):status='学习中'
        result.update(status=status,readOnly=bool(task.snapshot.get('withdrawnAt')) or not member(db,task.classroom_id,user.id))
    return result

def message(db,task,recipient,kind,body='',object_id=None,sender=None,event_key=None):
    sender=sender or task.teacher_id
    digest=hashlib.sha256(f'{kind}|{task.id}|{recipient}|{object_id or ""}|{event_key or ""}'.encode()).hexdigest();ident='msg-'+digest[:32]
    labels={'new_task':'新学习任务','deadline':'任务即将截止','overdue':'任务已逾期','feedback':'教师反馈','correction':'订正通知','supplement':'补充学习','note':'补充说明','submission':'学生已提交','supplement_submission':'补充学习已提交'}
    # Unique event identity survives concurrent HTTP reads and preserves read state.
    stmt=insert(BusinessMessage).values(id=ident,dedupe_key=digest,sender_id=sender,recipient_id=recipient,classroom_id=task.classroom_id,task_id=task.id,object_id=object_id,kind=kind,created_at=now(),title=(labels[kind]+' · '+task.title)[:240],body=body)
    db.execute(stmt.on_duplicate_key_update(id=stmt.inserted.id))
    return ident

def assign(db,task,student):
    rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==task.id,StudentRecord.student_id==student).with_for_update())
    if rec:return rec,False
    rec=StudentRecord(id=uid('record'),task_id=task.id,student_id=student,drafts={},observation='',source='live');db.add(rec);db.flush();message(db,task,student,'new_task');return rec,True

def feedback_message(db,task,rec):
    if rec.feedback:message(db,task,rec.student_id,'feedback',rec.feedback,event_key=hashlib.sha256(rec.feedback.encode()).hexdigest())
def materialize_messages(db,user):
    query=select(StudentRecord,LearningTask).join(LearningTask,LearningTask.id==StudentRecord.task_id)
    query=query.where(StudentRecord.student_id==user.id) if user.role=='student' else query.where(LearningTask.teacher_id==user.id)
    for rec,task in db.execute(query.order_by(LearningTask.id,StudentRecord.student_id)):
        feedback_message(db,task,rec)
        due=cutoff(task.due_date)
        if rec.completed or not due or not member(db,task.classroom_id,rec.student_id):continue
        delta=(due-now()).total_seconds()
        if delta<0:message(db,task,rec.student_id,'overdue')
        elif delta<=86400:message(db,task,rec.student_id,'deadline')
def message_json(db,row):
    room=db.get(Classroom,row.classroom_id);sender=db.get(Account,row.sender_id);recipient=db.get(Account,row.recipient_id)
    return {'id':row.id,'kind':row.kind,'taskId':row.task_id,'classId':row.classroom_id,'className':room.name,'objectId':row.object_id,'senderId':row.sender_id,'senderName':sender.display_name,'recipientId':row.recipient_id,'recipientName':recipient.display_name,'title':row.title,'body':row.body,'readAt':iso(row.read_at),'createdAt':iso(row.created_at)}

@router.get('/classes')
def classes(request:Request,db=Depends(get_db)):
    user=user_for(request,db)
    query=select(Classroom)
    if user.role=='teacher':query=query.where(Classroom.teacher_id==user.id)
    elif user.role=='student':query=query.join(ClassMember).where(ClassMember.student_id==user.id)
    else:return []
    return [{'id':c.id,'name':c.name,'grade':c.grade,'subject':c.subject,'teacherName':db.get(Account,c.teacher_id).display_name,'members':db.scalar(select(func.count()).select_from(ClassMember).where(ClassMember.classroom_id==c.id))} for c in db.scalars(query.order_by(Classroom.created_at))]
class ClassEdit(BaseModel):
    name:str=Field(min_length=1,max_length=160)
    grade:str=Field(min_length=1,max_length=80)
    subject:str=Field(min_length=1,max_length=80)
@router.put('/classes/{ident}')
def edit_class(ident:str,body:ClassEdit,request:Request,db=Depends(get_db)):
    if not all(v.strip() for v in (body.name,body.grade,body.subject)):raise HTTPException(422,'班级名称、年级和学科不能为空。')
    room=owned_class(db,user_for(request,db),ident,True);room.name=body.name.strip();room.grade=body.grade.strip();room.subject=body.subject.strip();db.commit();return {'id':room.id,'name':room.name,'grade':room.grade,'subject':room.subject}
@router.delete('/classes/{ident}/members/{student_id}')
def remove_member(ident:str,student_id:str,request:Request,db=Depends(get_db)):
    room=owned_class(db,user_for(request,db),ident,True);row=db.get(ClassMember,(room.id,student_id))
    if row:db.delete(row)
    db.commit();return {'removed':True,'historyPreserved':True}
@router.get('/classes/{ident}/tasks')
def class_tasks(ident:str,request:Request,db=Depends(get_db)):
    user=user_for(request,db);owned_class(db,user,ident)
    return [task_json(db,user,t) for t in db.scalars(select(LearningTask).where(LearningTask.classroom_id==ident).order_by(LearningTask.published_at.desc()))]
@router.get('/tasks/{ident}')
def task_detail(ident:str,request:Request,db=Depends(get_db)):
    user=user_for(request,db);task=accessible_task(db,user,ident)
    return task_json(db,user,task)
@router.post('/tasks/{ident}/assign')
def backfill(ident:str,body:dict,request:Request,db=Depends(get_db)):
    user=user_for(request,db);task=accessible_task(db,user,ident,True);owned_class(db,user,task.classroom_id)
    students=body.get('studentIds')
    if not isinstance(students,list) or not students or any(not isinstance(s,str) for s in students):raise HTTPException(422,'请选择要补发的学生。')
    if any(not member(db,task.classroom_id,s) for s in students):raise HTTPException(422,'只能补发给当前班级成员。')
    created=0
    for student in set(students):_,new=assign(db,task,student);created+=int(new)
    db.commit();return {'created':created,'taskId':task.id}
class InviteInput(BaseModel):days:int=Field(default=7,ge=1,le=30)
@router.post('/classes/{ident}/invites',status_code=201)
def new_invite(ident:str,body:InviteInput,request:Request,db=Depends(get_db)):
    room=owned_class(db,user_for(request,db),ident,True);code=secrets.token_hex(6).upper();item=ClassInvite(id=uid('invite'),classroom_id=room.id,code_hash=hashlib.sha256(code.encode()).hexdigest(),expires_at=now()+timedelta(days=body.days),created_at=now());db.add(item);db.commit();return {'id':item.id,'code':code,'expiresAt':iso(item.expires_at)}
@router.get('/classes/{ident}/invites')
def list_invites(ident:str,request:Request,db=Depends(get_db)):
    owned_class(db,user_for(request,db),ident)
    return [{'id':i.id,'expiresAt':iso(i.expires_at),'revoked':i.revoked,'expired':now()>=i.expires_at} for i in db.scalars(select(ClassInvite).where(ClassInvite.classroom_id==ident).order_by(ClassInvite.created_at.desc()))]
@router.post('/classes/{ident}/invites/{invite_id}/revoke')
def revoke(ident:str,invite_id:str,request:Request,db=Depends(get_db)):
    owned_class(db,user_for(request,db),ident,True);item=db.get(ClassInvite,invite_id)
    if not item or item.classroom_id!=ident:raise HTTPException(404,'邀请码不存在。')
    item.revoked=True;db.commit();return {'revoked':True}
class JoinInput(BaseModel):code:str=Field(min_length=1,max_length=40)
@router.post('/join')
def join(body:JoinInput,request:Request,db=Depends(get_db)):
    user=user_for(request,db)
    if user.role!='student':raise HTTPException(403,'请使用学生账号加入班级。')
    db.scalar(select(Account).where(Account.id==user.id).with_for_update())
    throttle=db.get(JoinThrottle,user.id)
    if not throttle:throttle=JoinThrottle(account_id=user.id,count=0,window_start=now());db.add(throttle)
    if now()-throttle.window_start>=timedelta(minutes=10):throttle.count=0;throttle.window_start=now()
    if throttle.count>=5:raise HTTPException(429,'尝试过多，请10分钟后重试。')
    throttle.count+=1
    code=body.code.strip().upper().replace('-','');invite=db.scalar(select(ClassInvite).where(ClassInvite.code_hash==hashlib.sha256(code.encode()).hexdigest()))
    if not invite:db.commit();raise HTTPException(422,'邀请码无效或已失效。')
    room=db.scalar(select(Classroom).where(Classroom.id==invite.classroom_id).with_for_update())
    invite=db.scalar(select(ClassInvite).where(ClassInvite.id==invite.id).with_for_update().execution_options(populate_existing=True))
    if invite.revoked or now()>=invite.expires_at:db.commit();raise HTTPException(422,'邀请码无效或已失效。')
    existing=db.scalar(select(ClassMember).where(ClassMember.classroom_id==room.id,ClassMember.student_id==user.id).with_for_update())
    if not existing:db.add(ClassMember(classroom_id=room.id,student_id=user.id))
    throttle.count=0;db.commit();return {'classId':room.id,'className':room.name,'created':not bool(existing),'historyTasksAutomaticallyAssigned':False}

@router.get('/messages')
def messages(request:Request,box:Literal['inbox','sent']='inbox',db=Depends(get_db)):
    user=user_for(request,db)
    if user.role not in ('teacher','student'):return []
    materialize_messages(db,user);db.commit()
    field=BusinessMessage.recipient_id if box=='inbox' else BusinessMessage.sender_id
    return [message_json(db,m) for m in db.scalars(select(BusinessMessage).where(field==user.id).order_by(BusinessMessage.created_at.desc(),BusinessMessage.id).limit(200))]
@router.post('/messages/{ident}/read')
def read_message(ident:str,request:Request,db=Depends(get_db)):
    user=user_for(request,db);row=db.get(BusinessMessage,ident)
    if not row or row.recipient_id!=user.id:raise HTTPException(404,'消息不存在。')
    if not row.read_at:row.read_at=now()
    db.commit();return {'readAt':iso(row.read_at)}
class SupplementInput(BaseModel):
    kind:Literal['note','correction','learning','foundation','retest']
    knowledgeId:str|None=None
    difficultyOnly:bool=False
    target:dict|None=None
    targets:dict={}
    caseId:str|None=None
    content:str=Field(min_length=1,max_length=6000)
    studentIds:list[str]|None=None
    dueDate:str=''
    requestKey:str=Field(min_length=8,max_length=100)
@router.post('/tasks/{ident}/supplements',status_code=201)
def send_supplement(ident:str,body:SupplementInput,request:Request,db=Depends(get_db)):
    user=user_for(request,db);task=accessible_task(db,user,ident,True);owned_class(db,user,task.classroom_id,True);cutoff(body.dueDate,True)
    if not body.content.strip():raise HTTPException(422,'请填写安排内容。')
    key=hashlib.sha256((user.id+ident+body.requestKey).encode()).hexdigest();sid='sup-'+key[:32]
    existing=db.scalar(select(SupplementalInstruction).where(SupplementalInstruction.id==sid).with_for_update())
    if existing:
        if (existing.details or {}).get('requestHash') and existing.details['requestHash']!=hashlib.sha256(json.dumps(body.model_dump(),sort_keys=True).encode()).hexdigest():raise HTTPException(409,'请求标识已经用于其他安排。')
        return {'id':sid,'created':False}
    assigned=set(db.scalars(select(StudentRecord.student_id).where(StudentRecord.task_id==ident)))
    active=set(db.scalars(select(ClassMember.student_id).where(ClassMember.classroom_id==task.classroom_id)))
    targets=set(body.studentIds) if body.studentIds is not None else assigned&active
    if not targets or not targets<=assigned&active:raise HTTPException(422,'请选择当前班级中已分配此任务的学生，晚加入学生请先补发原任务。')
    from .interventions import prepare
    details=prepare(db,user,task,targets,body) or {}
    details['requestHash']=hashlib.sha256(json.dumps(body.model_dump(),sort_keys=True).encode()).hexdigest()
    item=SupplementalInstruction(details=details,id=sid,task_id=ident,teacher_id=user.id,kind=body.kind,content=body.content,due_date=body.dueDate,status='active',created_at=now());db.add(item);db.flush()
    for student in targets:
        db.add(SupplementRecipient(instruction_id=sid,student_id=student));message(db,task,student,{'note':'note','correction':'correction','learning':'supplement','foundation':'supplement','retest':'supplement'}[body.kind],body.content,sid)
    db.commit();return {'id':sid,'created':True}
def supplement_json(db,user,item):
    task=db.get(LearningTask,item.task_id);recs=db.scalars(select(SupplementRecipient).where(SupplementRecipient.instruction_id==item.id)).all()
    visible=recs if user.role=='teacher' else [r for r in recs if r.student_id==user.id]
    from .interventions import outcomes
    result= {'id':item.id,'taskId':item.task_id,'className':db.get(Classroom,task.classroom_id).name,'teacherName':db.get(Account,item.teacher_id).display_name,'content':item.content,'kind':item.kind,'status':item.status,'dueDate':item.due_date,'dueAt':iso(cutoff(item.due_date)),'createdAt':iso(item.created_at),'recipients':[{'studentId':r.student_id,'studentName':db.get(Account,r.student_id).display_name,'startedAt':iso(r.started_at),'completedAt':iso(r.completed_at),'response':r.response,'feedback':r.feedback,'status':'已取消' if item.status=='cancelled' else '已送达' if item.kind=='note' else '已提交' if r.completed_at else '已逾期' if cutoff(item.due_date) and now()>cutoff(item.due_date) else '学习中' if r.started_at else '待开始'} for r in visible]}
    result['knowledgeId']=(item.details or {}).get('knowledgeId');result['case']=(item.details or {}).get('case')
    for r in result['recipients']:r['outcome']=outcomes(db,item,r['studentId'])
    return result
@router.get('/tasks/{ident}/supplements')
def supplements(ident:str,request:Request,db=Depends(get_db)):
    user=user_for(request,db);task=accessible_task(db,user,ident)
    rows=db.scalars(select(SupplementalInstruction).where(SupplementalInstruction.task_id==task.id).order_by(SupplementalInstruction.created_at.desc())).all()
    return [supplement_json(db,user,i) for i in rows if user.role=='teacher' or db.get(SupplementRecipient,(i.id,user.id)) or (i.kind=='note' and not db.scalar(select(SupplementRecipient.student_id).where(SupplementRecipient.instruction_id==i.id).limit(1)))]
@router.post('/supplements/{ident}/cancel')
def cancel_supplement(ident:str,request:Request,db=Depends(get_db)):
    user=user_for(request,db);item=db.scalar(select(SupplementalInstruction).where(SupplementalInstruction.id==ident).with_for_update())
    if not item or item.teacher_id!=user.id:raise HTTPException(404,'安排不存在。')
    if db.scalar(select(SupplementRecipient.student_id).where(SupplementRecipient.instruction_id==ident,SupplementRecipient.started_at.is_not(None)).limit(1)):raise HTTPException(409,'已有学生开始，不能取消；请发送补充说明。')
    item.status='cancelled';db.commit();return {'cancelled':True}
@router.post('/supplements/{ident}/{action}')
def act_supplement(ident:str,action:Literal['start','submit'],body:dict,request:Request,db=Depends(get_db)):
    user=user_for(request,db);item=db.scalar(select(SupplementalInstruction).where(SupplementalInstruction.id==ident).with_for_update());rec=db.get(SupplementRecipient,(ident,user.id)) if item else None
    if user.role!='student' or not rec:raise HTTPException(404,'安排不存在。')
    ensure_write(db,user,item.task_id)
    if item.status=='cancelled' or item.kind=='note':raise HTTPException(409,'此说明不可作为补充任务提交。')
    if not rec.started_at:rec.started_at=now()
    if action=='submit' and not rec.completed_at:
        response=body.get('response','')
        if not isinstance(response,str) or not response.strip():raise HTTPException(422,'请填写学习或订正说明。')
        rec.response=response[:6000];rec.completed_at=now();task=db.get(LearningTask,item.task_id);message(db,task,task.teacher_id,'supplement_submission',rec.response,ident,sender=user.id,event_key=user.id)
    db.commit();return {'startedAt':iso(rec.started_at),'completedAt':iso(rec.completed_at)}
@router.put('/supplements/{ident}/students/{student_id}/feedback')
def supplement_feedback(ident:str,student_id:str,body:dict,request:Request,db=Depends(get_db)):
    user=user_for(request,db);item=db.get(SupplementalInstruction,ident);rec=db.get(SupplementRecipient,(ident,student_id)) if item else None
    if not item or item.teacher_id!=user.id or not rec:raise HTTPException(404,'学生安排不存在。')
    if not rec.completed_at:raise HTTPException(422,'请等待学生提交学习或订正说明。')
    text=body.get('feedback','')
    if not isinstance(text,str) or not text.strip():raise HTTPException(422,'请填写反馈。')
    rec.feedback=text[:6000];task=db.get(LearningTask,item.task_id);message(db,task,student_id,'feedback',rec.feedback,ident,event_key=hashlib.sha256(rec.feedback.encode()).hexdigest());db.commit();return {'feedback':rec.feedback}

@router.get('/dashboard')
def dashboard(request:Request,classId:str|None=None,db=Depends(get_db)):
    user=user_for(request,db);rooms=classes(request,db);selected=classId or (rooms[0]['id'] if rooms else None)
    if user.role=='teacher':
        if selected:owned_class(db,user,selected)
        tasks=db.scalars(select(LearningTask).where(LearningTask.classroom_id==selected).order_by(LearningTask.published_at.desc())).all() if selected else []
        ids=[t.id for t in tasks];recs=db.scalars(select(StudentRecord).where(StudentRecord.task_id.in_(ids))).all() if ids else []
        from .insights import class_report
        aggregate=class_report(db,user,selected)['stats'] if selected else {}
        stats={'tasks':len(tasks),'unsubmittedStudents':len({r.student_id for r in recs if not r.completed and member(db,selected,r.student_id)}),'waitingFeedback':sum(r.completed and not r.feedback for r in recs)}
        recent=[{'recordId':r.id,'taskId':r.task_id,'studentName':db.get(Account,r.student_id).display_name,'taskTitle':db.get(LearningTask,r.task_id).title,'submittedAt':iso(r.submitted_at)} for r in sorted([r for r in recs if r.submitted_at],key=lambda r:r.submitted_at,reverse=True)[:8]]
    elif user.role=='student':
        tasks=db.scalars(select(LearningTask).join(StudentRecord).where(StudentRecord.student_id==user.id).order_by(LearningTask.published_at.desc())).all()
        recs=db.scalars(select(StudentRecord).where(StudentRecord.student_id==user.id)).all();stats={'pending':sum(not r.completed and member(db,db.get(LearningTask,r.task_id).classroom_id,user.id) for r in recs),'submitted':sum(r.completed for r in recs),'inProgress':sum(not r.completed and has_started(r) and member(db,db.get(LearningTask,r.task_id).classroom_id,user.id) for r in recs)};recent=[]
    else:return {'classes':[],'tasks':[],'stats':{},'recentSubmissions':[]}
    materialize_messages(db,user);db.commit()
    return {'learningMetrics':aggregate if user.role=='teacher' else {},'classes':rooms,'selectedClassId':selected,'tasks':[task_json(db,user,t) for t in tasks],'stats':stats,'recentSubmissions':recent,'unread':db.scalar(select(func.count()).select_from(BusinessMessage).where(BusinessMessage.recipient_id==user.id,BusinessMessage.read_at.is_(None)))}
