"""A durable, scoped queue over the original support_issues table."""
import hashlib
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from .database import get_db
from .models import SupportIssue,SupportIssueEvent,Classroom,ClassMember,LearningTask,StudentRecord,Account
from .teaching import user_for,uid,now,iso,accessible_task,member
router=APIRouter(prefix='/api/support')
STATES={'pending':'待处理','processing':'处理中','replied':'已回复','closed':'已关闭'}

def permitted(db,user,row):
    if row.owner_id==user.id:return True
    if user.role=='admin':return row.category in ('system','content')
    if user.role!='teacher' or row.category!='learning':return False
    if row.task_id:
        t=db.get(LearningTask,row.task_id)
        return bool(t and t.teacher_id==user.id and member(db,t.classroom_id,row.owner_id))
    return bool(db.scalar(select(Classroom.id).join(ClassMember).where(Classroom.teacher_id==user.id,ClassMember.student_id==row.owner_id).limit(1)))

def serialize(db,row):
    task=db.get(LearningTask,row.task_id) if row.task_id else None
    return {'id':row.id,'ownerId':row.owner_id,'ownerName':db.get(Account,row.owner_id).display_name,'text':row.text,'reply':row.reply,'resolved':row.resolved,'category':row.category,'taskId':row.task_id,'taskTitle':task.title if task else None,'status':row.status,'statusLabel':STATES[row.status],'revision':row.revision,'createdAt':iso(row.created_at),'updatedAt':iso(row.updated_at),'legacyReply':row.reply,'history':[{'id':e.id,'actorId':e.actor_id,'actorName':db.get(Account,e.actor_id).display_name,'oldStatus':e.old_status,'status':e.new_status,'content':e.content,'createdAt':iso(e.created_at)} for e in db.scalars(select(SupportIssueEvent).where(SupportIssueEvent.issue_id==row.id).order_by(SupportIssueEvent.created_at,SupportIssueEvent.id))]}

@router.get('')
def listing(request:Request,status:str|None=None,q:str='',db=Depends(get_db)):
    user=user_for(request,db)
    # Filter before serialization; never expose out-of-scope counts or names.
    rows=db.scalars(select(SupportIssue).order_by(SupportIssue.updated_at.desc(),SupportIssue.id)).all()
    return [serialize(db,r) for r in rows if permitted(db,user,r) and (not status or r.status==status) and (not q or q.casefold() in r.text.casefold())]

@router.post('',status_code=201)
def create(body:dict,request:Request,db=Depends(get_db)):
    user=user_for(request,db);text=str(body.get('text','')).strip();category=body.get('category','learning');key=str(body.get('requestKey',''))
    if not text or len(text)>6000 or category not in ('learning','content','system') or not 8<=len(key)<=80:raise HTTPException(422,'请填写有效问题并选择类型。')
    task_id=body.get('taskId') or None
    if task_id:accessible_task(db,user,task_id)
    if user.role=='student' and category=='learning' and not task_id:raise HTTPException(422,'学习问题请选择对应任务；系统问题不需要任务。')
    digest=hashlib.sha256((user.id+key).encode()).hexdigest()
    db.scalar(select(Account).where(Account.id==user.id).with_for_update())
    old=db.scalar(select(SupportIssue).where(SupportIssue.request_key==digest))
    if old:
        if (old.text,old.category,old.task_id)!=(text,category,task_id):raise HTTPException(409,'请求标识已用于另一条问题。')
        return serialize(db,old)
    row=SupportIssue(id=uid('issue'),owner_id=user.id,text=text,reply='',resolved=False,status='pending',revision=1,category=category,task_id=task_id,request_key=digest,created_at=now(),updated_at=now());db.add(row);db.flush()
    db.add(SupportIssueEvent(id=uid('ise'),issue_id=row.id,actor_id=user.id,request_key=key,old_status='',new_status='pending',content=text));db.commit();return serialize(db,row)

@router.post('/{ident}/events')
def transition(ident:str,body:dict,request:Request,db=Depends(get_db)):
    user=user_for(request,db);row=db.scalar(select(SupportIssue).where(SupportIssue.id==ident).with_for_update())
    if not row or not permitted(db,user,row):raise HTTPException(404,'没有找到有权限的问题。')
    status=body.get('status');content=str(body.get('content','')).strip();key=str(body.get('requestKey',''))
    if status not in STATES or not 8<=len(key)<=80 or len(content)>6000:raise HTTPException(422,'请选择有效状态。')
    previous=db.scalar(select(SupportIssueEvent).where(SupportIssueEvent.actor_id==user.id,SupportIssueEvent.request_key==key))
    if previous:
        if previous.issue_id!=ident or previous.new_status!=status or previous.content!=content:raise HTTPException(409,'请求标识已使用。')
        return serialize(db,row)
    if user.role=='student' and status not in ('pending','closed'):raise HTTPException(403,'学生可以补充或关闭自己的问题。')
    if body.get('expectedRevision')!=row.revision:raise HTTPException(409,'问题已被更新，请重新读取；本次输入保留。')
    if status=='replied' and not content:raise HTTPException(422,'请填写回复内容。')
    db.add(SupportIssueEvent(id=uid('ise'),issue_id=row.id,actor_id=user.id,request_key=key,old_status=row.status,new_status=status,content=content))
    if status=='replied':row.reply=content
    row.status=status;row.resolved=status in ('replied','closed');row.revision+=1;row.updated_at=now();db.commit();return serialize(db,row)
