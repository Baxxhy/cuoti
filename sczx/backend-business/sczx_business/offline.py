"""Student-only packages and narrowly scoped compare-and-swap draft synchronization."""
import copy,hashlib,json
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select
from .database import get_db
from .models import Account,StudentRecord,LearningTask,ClassMember,HelpRecord,Attempt,Classroom
from .offline_models import OfflineOperation
from .teaching import accessible_task,owned_class,cutoff,now,iso
router=APIRouter(prefix='/api/offline')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def student(request,db):
    from .main import current_user
    u=current_user(request,db)
    if u.role!='student':raise HTTPException(403,'离线学习仅供学生使用。')
    return u
def revision(rec):return digest({'drafts':rec.drafts or {},'observation':rec.observation or ''})
def version(task):return digest({'lessonId':task.lesson_id,'snapshot':task.snapshot,'questions':task.questions})
def allowed(task,rec,db,u,member_active=None):
    if not (member_active if member_active is not None else db.get(ClassMember,(task.classroom_id,u.id))):return '已移出班级，仅保留本机副本。'
    if task.snapshot.get('withdrawnAt'):return '教师已撤回任务。'
    if task.source in ('exam','live-class'):return '考试与实时课堂须在线使用。'
    if rec.completed or rec.submitted_at:return '任务已提交，不能覆盖原始记录。'
    if cutoff(task.due_date) and now()>cutoff(task.due_date):return '已超过服务器规定的截止时间。'
    return ''
def safe_question(q,index):return {**{k:copy.deepcopy(q[k]) for k in ['id','kind','prompt','equation','imageUrl','imageAlt','knowledgeIds'] if k in q},'id':str(q.get('id') or index),'index':index}
def safe_blocks(task):
    # Teaching text is public; keys such as notes, rubric and reference answers never leave here.
    blocks=[]
    for b in task.snapshot.get('blocks',[]):
        row={k:copy.deepcopy(b[k]) for k in ['id','title','type','content','imageUrl','imageAlt','questionIds'] if k in b}
        # Interactive configs can contain hidden solutions. Offline reader keeps text/images only.
        blocks.append(row)
    return blocks
@router.get('/tasks')
def tasks(request:Request,db=Depends(get_db)):
    u=student(request,db);result=[]
    for rec,t in db.execute(select(StudentRecord,LearningTask).join(LearningTask,LearningTask.id==StudentRecord.task_id).where(StudentRecord.student_id==u.id)):
        if t.source in ('exam','live-class') or not db.get(ClassMember,(t.classroom_id,u.id)) or t.snapshot.get('withdrawnAt'):continue
        result.append({'id':t.id,'title':t.title,'lessonId':t.lesson_id,'versionId':version(t),'readOnly':bool(allowed(t,rec,db,u))})
    return result
@router.get('/packages/{task_id}')
def package(task_id:str,request:Request,db=Depends(get_db)):
    u=student(request,db);t=accessible_task(db,u,task_id);rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==task_id,StudentRecord.student_id==u.id))
    if t.source in ('exam','live-class') or t.snapshot.get('withdrawnAt') or not db.get(ClassMember,(t.classroom_id,u.id)):raise HTTPException(403,'此任务不能下载供离线学习。')
    ls=t.snapshot.get('lessonSnapshot') or {};qs=[safe_question(q,i) for i,q in enumerate(t.questions)]
    drafts={'questions':{}}
    for q in qs:
        d=(rec.drafts or {}).get('questions',{}).get(q['id'],{})
        drafts['questions'][q['id']]={k:copy.deepcopy(d[k]) for k in ['answer','reason','helped'] if k in d}
    drafts['lessonPosition']=copy.deepcopy((rec.drafts or {}).get('lessonPosition',{}))
    result={'schema':1,'userId':u.id,'taskId':t.id,'lessonId':t.lesson_id,'title':t.title,'publishedVersionId':ls.get('versionId') or t.snapshot.get('paperVersionId') or '历史固定任务','versionId':version(t),'goal':t.snapshot.get('goal',''),'blocks':safe_blocks(t),'questions':qs,'knowledgeIds':ls.get('knowledgeIds',[]),'downloadedAt':iso(now()),'offlineUntil':iso(now()+timedelta(hours=72)),'baseRevision':revision(rec),'drafts':drafts,'readOnly':bool(allowed(t,rec,db,u))}
    result['contentHash']=digest({k:v for k,v in result.items() if k not in ['drafts','baseRevision','downloadedAt','offlineUntil']})
    return result
class DraftOperation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    operationId:str=Field(min_length=8,max_length=64)
    userId:str=Field(max_length=40)
    taskId:str=Field(max_length=40)
    questionId:str=Field(max_length=80)
    versionId:str=Field(min_length=64,max_length=64)
    baseRevision:str=Field(min_length=64,max_length=64)
    modifiedAt:str=Field(max_length=50)
    answer:str=Field(default='',max_length=12000)
    reason:str=Field(default='',max_length=20000)
    helped:bool=False
    position:str=Field(default='',max_length=80)
def conflict(code,message,rec=None,retry=False):
    raise HTTPException(409,{'code':code,'message':message,'serverDrafts':copy.deepcopy(rec.drafts or {}) if rec else {},'serverRevision':revision(rec) if rec else None,'allowRetry':retry})
@router.post('/sync')
def sync(body:DraftOperation,request:Request,db=Depends(get_db)):
    u=student(request,db)
    if body.userId!=u.id:raise HTTPException(403,'当前在线账号与本机草稿不同，请重新登录原账号。')
    # Serialize one user's receipts and current draft mutation with ordinary writers.
    db.scalar(select(Account).where(Account.id==u.id).with_for_update())
    rh=digest(body.model_dump());old=db.scalar(select(OfflineOperation).where(OfflineOperation.owner_id==u.id,OfflineOperation.operation_id==body.operationId).with_for_update())
    if old:
        if old.request_hash!=rh:conflict('operation_changed','同一操作ID的内容发生变化。')
        return old.result
    t=db.get(LearningTask,body.taskId)
    if t:
        db.scalar(select(Classroom).where(Classroom.id==t.classroom_id).with_for_update());db.refresh(t)
    rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==body.taskId,StudentRecord.student_id==u.id).with_for_update())
    if not rec:conflict('revoked','任务已撤回或不再分配给当前账号。')
    t=accessible_task(db,u,body.taskId)
    member_active=bool(db.scalar(select(ClassMember).where(ClassMember.classroom_id==t.classroom_id,ClassMember.student_id==u.id).with_for_update()))
    reason=allowed(t,rec,db,u,member_active)
    if reason:conflict('invalid',reason,rec)
    if version(t)!=body.versionId:conflict('version','内容版本已经变化，请下载新版本；原本机草稿保留。',rec)
    if revision(rec)!=body.baseRevision:conflict('revision','服务器草稿有新修改，请对比后决定。',rec,True)
    drafts=copy.deepcopy(rec.drafts or {})
    if body.questionId=='@position':
        if body.position and body.position not in {str(b.get('id')) for b in t.snapshot.get('blocks',[])}:raise HTTPException(422,'学习位置不属于当前课时。')
        drafts['lessonPosition']={'blockId':body.position}
    else:
        index=next((i for i,q in enumerate(t.questions) if str(q.get('id') or i)==body.questionId),None)
        if index is None:raise HTTPException(422,'题目不属于此固定版本。')
        previous=drafts.setdefault('questions',{}).get(body.questionId,{})
        used=bool(previous.get('helped') or body.helped or db.scalar(select(Attempt.id).where(Attempt.record_id==rec.id,Attempt.question==index,Attempt.helped==True).with_for_update()) or db.scalar(select(HelpRecord.id).where(HelpRecord.record_id==rec.id,HelpRecord.question==index).with_for_update()))
        drafts['questions'][body.questionId]={**previous,'answer':body.answer,'reason':body.reason,'helped':used}
    rec.drafts=drafts
    result={'operationId':body.operationId,'status':'synced','revision':revision(rec),'serverTime':iso(now()),'formalSubmission':False}
    db.add(OfflineOperation(owner_id=u.id,operation_id=body.operationId,request_hash=rh,result=result));db.commit();return result

@router.post('/tasks/{ident}/withdraw')
def withdraw(ident:str,request:Request,db=Depends(get_db)):
    from .main import current_user
    u=current_user(request,db);t=accessible_task(db,u,ident);owned_class(db,u,t.classroom_id,True);db.refresh(t)
    t.snapshot={**t.snapshot,'withdrawnAt':t.snapshot.get('withdrawnAt') or iso(now())};db.commit();return {'withdrawn':True}
