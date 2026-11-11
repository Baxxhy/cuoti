"""Adjustable teaching groups, evidence snapshots and existing learning tasks."""
import copy
from fastapi import APIRouter,Request,Depends
from sqlalchemy import select
from .database import get_db
from .models import Account,ClassMember,KnowledgePoint,Lesson,LearningTask,StudentRecord,Attempt
from .exam_models import PaperVersion,ExamPaper
from .classroom_models import TeachingGroupPlan
from .teaching import owned_class,assign,now
from .exams import teacher,own,expected,uid,fail
from . import learning_memory as memory
router=APIRouter(prefix='/api/groups')
def evidence(db,u,room,kid):
 if not db.get(KnowledgePoint,kid):fail('请选择真实知识点。')
 result={}
 for sid in db.scalars(select(ClassMember.student_id).where(ClassMember.classroom_id==room)):
  facts=memory.collect(db,sid,u.id,{room})[0];facts=[x for x in facts if kid in x.get('knowledgeIds',[])];state=memory.calculate(facts);label='补基础' if state['status']=='strengthen' else '拓展' if state['status']=='independent' else '证据不足' if state['status'] in ('none','insufficient') else '巩固'
  result[sid]={'studentId':sid,'name':db.get(Account,sid).display_name,'suggestion':label,'state':state,'evidenceIds':[x['eventId'] for x in facts]}
 return result
def view(db,u,p):
 tasks=list(db.scalars(select(LearningTask).where(LearningTask.source=='group',LearningTask.teacher_id==u.id)));published=[]
 for task in tasks:
  if task.snapshot.get('groupPlanId')!=p.id:continue
  records=list(db.scalars(select(StudentRecord).where(StudentRecord.task_id==task.id)));events=[]
  for r in records:events+=memory.collect(db,r.student_id,u.id,{p.classroom_id})[0]
  events=[x for x in events if x.get('taskId')==task.id and x['sourceType']=='attempt'];passed={x['studentId'] for x in events if x['verification']=='verified_correct' and not x.get('helped')}
  published.append({'id':task.id,'title':task.title,'assigned':len(records),'submitted':sum(r.completed for r in records),'independentCorrectStudents':len(passed),'evidence':events})
 return {'id':p.id,'classId':p.classroom_id,'knowledgeId':p.knowledge_id,'revision':p.revision,'published':p.published,'groups':p.groups,'evidence':p.evidence,'tasks':published}
@router.get('/suggestions')
def suggestions(request:Request,classId:str,knowledgeId:str,db=Depends(get_db)):
 u=teacher(request,db);owned_class(db,u,classId);return {'students':list(evidence(db,u,classId,knowledgeId).values()),'requiresTeacherConfirmation':True}
@router.get('')
def listing(request:Request,db=Depends(get_db)):
 u=teacher(request,db);return [view(db,u,p) for p in db.scalars(select(TeachingGroupPlan).where(TeachingGroupPlan.owner_id==u.id))]
def groups(db,u,room,kid,values):
 if not isinstance(values,list) or not 1<=len(values)<=8:fail('请选择1—8个教学小组。')
 members=set(db.scalars(select(ClassMember.student_id).where(ClassMember.classroom_id==room)));seen=set();safe=[]
 for g in values:
  if not isinstance(g,dict) or g.get('label') not in ('补基础','巩固','拓展','证据不足'):fail('请选择可调整的教学安排名称。')
  ids=g.get('studentIds');v=db.get(PaperVersion,g.get('versionId'));p=db.get(ExamPaper,v.paper_id) if v else None
  if not p or p.owner_id!=u.id or not isinstance(ids,list) or not ids or any(not isinstance(s,str) or s not in members or s in seen for s in ids):fail('小组成员或已审核试卷版本无效。')
  if len(set(ids))!=len(ids):fail('同一学生不能重复分组。')
  if any(kid not in e['question'].get('knowledgeIds',[]) for e in v.data['entries']):fail('分层练习必须关联当前知识点。')
  seen.update(ids);safe.append({'label':g['label'],'studentIds':ids,'versionId':v.id})
 return safe
@router.post('',status_code=201)
def create(body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);room=owned_class(db,u,body.get('classId'),True);ev=evidence(db,u,room.id,body.get('knowledgeId'));gs=groups(db,u,room.id,body['knowledgeId'],body.get('groups'));p=TeachingGroupPlan(id=uid('group'),owner_id=u.id,classroom_id=room.id,knowledge_id=body['knowledgeId'],groups=gs,evidence=ev,revision=0,published=False);db.add(p);db.commit();return view(db,u,p)
@router.put('/{ident}')
def edit(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);p=own(db,TeachingGroupPlan,ident,u);expected(p,body)
 if p.published:fail('已发布安排保持不变，请新建安排调整。',409)
 p.groups=groups(db,u,p.classroom_id,p.knowledge_id,body.get('groups'));p.evidence=evidence(db,u,p.classroom_id,p.knowledge_id);p.revision+=1;db.commit();return view(db,u,p)
@router.post('/{ident}/publish')
def publish(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);p=own(db,TeachingGroupPlan,ident,u);owned_class(db,u,p.classroom_id,True)
 if p.published:return view(db,u,p)
 expected(p,body)
 if not body.get('confirmed'):fail('请确认调整后的成员与每组练习。')
 safe=groups(db,u,p.classroom_id,p.knowledge_id,p.groups)
 for g in safe:
  v=db.get(PaperVersion,g['versionId']);lesson=db.scalar(select(Lesson).where(Lesson.unit_id==v.data['unitId']).order_by(Lesson.position))
  if not lesson:fail('单元课时不存在。')
  questions=[{**e['question'],'id':e['versionId'],'kind':'check'} for e in v.data['entries']];t=LearningTask(id=uid('task'),teacher_id=u.id,classroom_id=p.classroom_id,lesson_id=lesson.id,title=g['label']+'练习 · '+v.data['title'],source='group',snapshot={'groupPlanId':p.id,'paperVersionId':v.id,'groupLabel':g['label'],'goal':'依据原作答安排本次练习','blocks':[],'lessonSnapshot':{'unitId':v.data['unitId'],'title':v.data['title'],'knowledgeIds':[p.knowledge_id]}},questions=questions,due_date='',published_at=now());db.add(t);db.flush()
  for sid in g['studentIds']:assign(db,t,sid)
 p.published=True;p.revision+=1;db.commit();return view(db,u,p)
