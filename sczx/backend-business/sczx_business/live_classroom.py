"""Bounded polling transport; classroom state and original submissions are authoritative in MySQL."""
import copy
from fastapi import APIRouter,Depends,Request
from sqlalchemy import select,func
from .database import get_db
from .models import Account,ClassMember,LearningTask,StudentRecord,Attempt,WrongQuestion
from .classroom_models import LiveClass,LivePresence,LiveActivity,LiveAnswer
from .teaching import user_for,owned_class,iso,now,assign
from .exams import teacher,fail,uid,expected
from .curriculum import published_lesson,student_content,assess_question
router=APIRouter(prefix='/api/live')
def access(db,u,ident):
 r=db.scalar(select(LiveClass).where(LiveClass.id==ident).with_for_update())
 if not r or not (u.role=='teacher' and r.owner_id==u.id or u.role=='student' and (db.get(ClassMember,(r.classroom_id,u.id)) or r.status=='ended' and db.get(LivePresence,(r.id,u.id)))):fail('没有找到有权限的课堂。',404)
 return r
def serialize(db,u,r):
 activities=list(db.scalars(select(LiveActivity).where(LiveActivity.session_id==r.id).order_by(LiveActivity.position)));presences=list(db.scalars(select(LivePresence).where(LivePresence.session_id==r.id)));is_teacher=u.role=='teacher';items=[]
 for a in activities:
  rows=list(db.scalars(select(LiveAnswer).where(LiveAnswer.activity_id==a.id)));submitted=[x for x in rows if x.submitted_at];own=next((x for x in rows if x.student_id==u.id),None)
  item={'id':a.id,'position':a.position,'question':a.question if is_teacher else student_content({'questions':[a.question]})['questions'][0],'feedback':a.feedback}
  def answer(x):return {'id':x.id,'studentId':x.student_id,'studentName':db.get(Account,x.student_id).display_name,'answer':x.answer,'reason':x.reason,'revision':x.revision,'submittedAt':iso(x.submitted_at),**({'verification':x.verification} if is_teacher or a.feedback or r.status=='ended' else {})}
  if is_teacher:item.update(answers=[answer(x) for x in rows],stats={'submitted':len(submitted),'correct':sum(x.verification.get('correct',False) for x in submitted),'incorrect':sum(x.verification.get('status')=='inconsistent' for x in submitted),'unverified':sum(x.verification.get('status')=='unverified' for x in submitted)})
  else:item['answer']=answer(own) if own else None
  items.append(item)
 return {'id':r.id,'classId':r.classroom_id,'lessonId':r.lesson_id,'title':r.snapshot['title'],'versionId':r.snapshot['versionId'],'status':r.status,'revision':r.revision,'currentId':r.current_id,'taskId':r.task_id,'joined':len(presences) if is_teacher else bool(db.get(LivePresence,(r.id,u.id))),'members':[{'id':p.student_id,'name':db.get(Account,p.student_id).display_name} for p in presences] if is_teacher else [],'activities':items,'pollSeconds':3,**({'availableQuestions':[{'index':i,'prompt':q['prompt'],'equation':q.get('equation','')} for i,q in enumerate(r.snapshot['questions'])]} if is_teacher else {})}
@router.get('')
def listing(request:Request,db=Depends(get_db)):
 u=user_for(request,db);query=select(LiveClass)
 if u.role=='teacher':query=query.where(LiveClass.owner_id==u.id)
 elif u.role=='student':query=query.where((LiveClass.classroom_id.in_(select(ClassMember.classroom_id).where(ClassMember.student_id==u.id)))|(LiveClass.id.in_(select(LivePresence.session_id).where(LivePresence.student_id==u.id))))
 else:return []
 return [{'id':r.id,'title':r.snapshot['title'],'classId':r.classroom_id,'status':r.status} for r in db.scalars(query.order_by(LiveClass.created_at.desc()))]
@router.post('',status_code=201)
def create(body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);room=owned_class(db,u,body.get('classId'),True);lesson=published_lesson(db,body.get('lessonId'))
 if not lesson:fail('请选择已发布课时。')
 if db.scalar(select(LiveClass.id).where(LiveClass.classroom_id==room.id,LiveClass.status=='active')):fail('本班已有进行中的课堂。',409)
 r=LiveClass(id=uid('live'),owner_id=u.id,classroom_id=room.id,lesson_id=lesson['lessonId'],snapshot=copy.deepcopy(lesson),status='active',revision=0);db.add(r);db.commit();return serialize(db,u,r)
@router.get('/{ident}')
def detail(ident:str,request:Request,db=Depends(get_db)):
 u=user_for(request,db);return serialize(db,u,access(db,u,ident))
@router.post('/{ident}/join')
def join(ident:str,request:Request,db=Depends(get_db)):
 u=user_for(request,db);r=access(db,u,ident)
 if u.role!='student' or r.status!='active':fail('当前不能加入课堂。',409)
 if not db.get(LivePresence,(r.id,u.id)):db.add(LivePresence(session_id=r.id,student_id=u.id))
 db.commit();return serialize(db,u,r)
@router.post('/{ident}/push')
def push(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);r=access(db,u,ident);expected(r,body)
 if r.status!='active':fail('课堂已结束。',409)
 index=body.get('question')
 if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(r.snapshot['questions']):fail('请选择当前固定课时中的题目。')
 a=LiveActivity(id=uid('act'),session_id=r.id,position=r.revision+1,question=copy.deepcopy(r.snapshot['questions'][index]),feedback='');db.add(a);r.current_id=a.id;r.revision+=1;db.commit();return serialize(db,u,r)
@router.put('/{ident}/activities/{aid}/answer')
def answer(ident:str,aid:str,body:dict,request:Request,db=Depends(get_db)):
 u=user_for(request,db);r=access(db,u,ident);a=db.get(LiveActivity,aid)
 if u.role!='student' or not db.get(LivePresence,(r.id,u.id)):fail('请先加入课堂。',403)
 if not a or a.session_id!=r.id:fail('活动不存在。',404)
 x=db.scalar(select(LiveAnswer).where(LiveAnswer.activity_id==aid,LiveAnswer.student_id==u.id).with_for_update())
 if x and x.submitted_at:
  if body.get('submit') and body.get('answer')==x.answer and body.get('reason','')==x.reason:return serialize(db,u,r)
  fail('正式回答已提交，只读保留。',409)
 if r.status!='active' or r.current_id!=aid:fail('课堂已结束或活动已切换，输入保留。',409)
 if body.get('revision')!=(x.revision if x else 0):fail('草稿已更新，请重新读取。',409)
 text=body.get('answer','');reason=body.get('reason','')
 if not isinstance(text,str) or not isinstance(reason,str) or len(text)>6000 or len(reason)>6000 or body.get('submit') and not text.strip():fail('请填写有效答案。')
 if not x:x=LiveAnswer(id=uid('liveans'),activity_id=aid,student_id=u.id,revision=0);db.add(x)
 x.answer=text;x.reason=reason;x.revision+=1
 if body.get('submit'):x.submitted_at=now();x.verification=assess_question(text,a.question)
 db.commit();return serialize(db,u,r)
@router.put('/{ident}/activities/{aid}/feedback')
def feedback(ident:str,aid:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);r=access(db,u,ident);a=db.get(LiveActivity,aid)
 if not a or a.session_id!=r.id:fail('活动不存在。',404)
 if r.status!='active':fail('课堂已结束，讲评只读。',409)
 text=str(body.get('text','')).strip()
 if not text or len(text)>6000:fail('请填写讲评。')
 a.feedback=text;db.commit();return serialize(db,u,r)
@router.post('/{ident}/end')
def end(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);r=access(db,u,ident)
 if r.status=='ended':return serialize(db,u,r)
 expected(r,body);activities=list(db.scalars(select(LiveActivity).where(LiveActivity.session_id==r.id).order_by(LiveActivity.position)));questions=[{**a.question,'id':a.id,'kind':'check'} for a in activities];snapshot=copy.deepcopy(r.snapshot);snapshot.update(blocks=[],liveClassId=r.id,lessonSnapshot=r.snapshot)
 t=LearningTask(id=uid('task'),teacher_id=u.id,classroom_id=r.classroom_id,lesson_id=r.lesson_id,title='课堂记录 · '+r.snapshot['title'],snapshot=snapshot,questions=questions,source='live-class',due_date='',published_at=now());db.add(t);db.flush()
 for p in db.scalars(select(LivePresence).where(LivePresence.session_id==r.id)):
  rec,_=assign(db,t,p.student_id);rec.completed=False;rec.submitted_at=None;rec.feedback='；'.join(a.feedback for a in activities if a.feedback)
  for i,a in enumerate(activities):
   x=db.scalar(select(LiveAnswer).where(LiveAnswer.activity_id==a.id,LiveAnswer.student_id==p.student_id))
   if not x or not x.submitted_at:continue
   rec.completed=True;rec.submitted_at=now()
   attempt=Attempt(id=uid('attempt'),record_id=rec.id,question=i,answer=x.answer,reason=x.reason,correct=x.verification['correct'],helped=False,verification=x.verification);db.add(attempt);db.flush()
   if x.verification['status']=='inconsistent':db.add(WrongQuestion(id=uid('wrong'),owner_id=p.student_id,record_id=rec.id,attempt_id=attempt.id,prompt=a.question.get('equation') or a.question['prompt'],answer=x.answer,reason=x.reason,details={'source':'live-class','liveClassId':r.id,'activityId':a.id,'equation':a.question.get('equation',''),'knowledgeIds':a.question.get('knowledgeIds',[])}))
 r.status='ended';r.revision+=1;r.task_id=t.id;db.commit();return serialize(db,u,r)
