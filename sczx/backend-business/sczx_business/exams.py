"""Teacher-owned bank and immutable papers; server-controlled exam and grading lifecycle."""
import copy,hashlib,io,json,uuid,re
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,Request,HTTPException
from fastapi.responses import Response
from sqlalchemy import select,func
from .database import get_db
from .models import Account,KnowledgePoint,CourseUnit,Lesson,ClassMember,LearningTask,StudentRecord,Attempt,WrongQuestion,ModelJob
from .exam_models import BankQuestion,QuestionVersion,ExamPaper,PaperVersion,ClassExam,ExamSubmission,ExamGradeAudit
from .exam_schemas import BankInput
from .teaching import user_for,owned_class,iso
from .curriculum import assess_question
from .math_conditions import inspect_conditions
router=APIRouter(prefix='/api/exams')
def now():return datetime.now(timezone.utc).replace(tzinfo=None)
def uid(p):return p+'-'+uuid.uuid4().hex[:32]
def fail(message,status=422):raise HTTPException(status,message)
def teacher(request,db):
 u=user_for(request,db)
 if u.role!='teacher':fail('请使用教师账号。',403)
 return u
def own(db,model,ident,u):
 row=db.scalar(select(model).where(model.id==ident).with_for_update())
 if not row or row.owner_id!=u.id:fail('没有找到有权限的记录。',404)
 return row
def expected(row,body):
 if body.get('revision')!=row.revision:fail('内容已更新，请重新读取；本次输入保留。',409)
def checked_question(db,raw):
 try:d=BankInput.model_validate(raw).model_dump()
 except Exception:fail('题目信息不完整或格式无效。')
 if not db.get(CourseUnit,d['unitId']) or any(not db.get(KnowledgePoint,k) for k in d['knowledgeIds']):fail('请选择真实单元和知识点。')
 d['requiresTeacherReview']=d['requiresTeacherReview'] or d['kind']!='calculation'
 from .math_tools import solve_text_equation,compare_equivalence
 solved,valid=solve_text_equation(d['equation'])
 if valid:
  equal,checked=compare_equivalence(solved.split('=',1)[1],d['answer']);d['referenceVerification']={'status':'verified' if checked and equal else 'inconsistent' if checked else 'unverified'}
 else:d['referenceVerification']={'status':'unverified'};d['requiresTeacherReview']=True
 d['verification']=assess_question(d['answer'],d)
 d['conditionCheck']=inspect_conditions(d)
 return d
def bank_json(db,row):
 versions=db.scalars(select(QuestionVersion).where(QuestionVersion.question_id==row.id).order_by(QuestionVersion.number.desc())).all()
 return {'id':row.id,'revision':row.revision,'reviewed':row.reviewed,'draft':row.draft,'versions':[{'id':v.id,'number':v.number,'data':v.data} for v in versions]}
@router.get('/bank')
def bank(request:Request,db=Depends(get_db)):
 u=teacher(request,db);return [bank_json(db,r) for r in db.scalars(select(BankQuestion).where(BankQuestion.owner_id==u.id).order_by(BankQuestion.id))]
@router.post('/bank',status_code=201)
def create_question(body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);row=BankQuestion(id=uid('bq'),owner_id=u.id,draft=checked_question(db,body.get('data')),reviewed=False,revision=1);db.add(row);db.commit();return bank_json(db,row)
@router.put('/bank/{ident}')
def edit_question(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);row=own(db,BankQuestion,ident,u);expected(row,body);row.draft=checked_question(db,body.get('data'));row.revision+=1;row.reviewed=False;db.commit();return bank_json(db,row)
@router.post('/bank/{ident}/review')
def review_question(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);row=own(db,BankQuestion,ident,u);expected(row,body);d=checked_question(db,{k:v for k,v in row.draft.items() if k in BankInput.model_fields})
 if d['conditionCheck']['issues'] or d['referenceVerification']['status']=='inconsistent':fail('请修订数学内容后再审核。')
 if not body.get('confirmed'):fail('请确认已核对题干、条件及参考答案。')
 if row.draft.get('courseSource'):d['courseSource']=row.draft['courseSource']
 d['reviewRecord']={'actorId':u.id,'at':iso(now()),'scope':'题干、条件、解答人工核对'};n=db.scalar(select(func.max(QuestionVersion.number)).where(QuestionVersion.question_id==ident)) or 0
 v=QuestionVersion(id=uid('qv'),question_id=ident,number=n+1,data=d);db.add(v);row.reviewed=True;row.revision+=1;db.commit();return bank_json(db,row)
@router.post('/bank/import',status_code=201)
def import_course(body:dict,request:Request,db=Depends(get_db)):
 from .curriculum import published_lesson
 u=teacher(request,db);lesson=published_lesson(db,str(body.get('lessonId','')),body.get('versionId'))
 if not lesson:fail('请选择已发布课时。')
 ids=[]
 for q in lesson['questions']:
  d=checked_question(db,{'prompt':q['prompt'],'equation':q.get('equation',''),'answer':str(q['answer']),'explanation':q.get('explanation') or '依据课时原解答核对。','knowledgeIds':q.get('knowledgeIds') or lesson['knowledgeIds'],'unitId':lesson['unitId'],'kind':'application' if q.get('requiresTeacherReview') else 'calculation','source':'课时 '+lesson['lessonId']+' / '+lesson['versionId']+' / '+q['id']})
  d['courseSource']={'lessonId':lesson['lessonId'],'versionId':lesson['versionId'],'questionId':q['id']};r=BankQuestion(id=uid('bq'),owner_id=u.id,draft=d,reviewed=False,revision=1);db.add(r);ids.append(r.id)
 db.commit();return {'ids':ids,'status':'待审核'}
def paper_json(db,row):
 versions=db.scalars(select(PaperVersion).where(PaperVersion.paper_id==row.id).order_by(PaperVersion.number.desc())).all();return {'id':row.id,'revision':row.revision,'reviewed':row.reviewed,'draft':row.draft,'versions':[{'id':v.id,'number':v.number} for v in versions]}
def paper_data(db,u,body):
 title=str(body.get('title','')).strip();entries=body.get('entries');unit=body.get('unitId','unit-equation')
 if not title or len(title)>200 or not db.get(CourseUnit,unit) or not isinstance(entries,list) or not 1<=len(entries)<=100:fail('请填写试卷名称并选择1—100题。')
 rows=[];seen=set()
 for e in entries:
  if not isinstance(e,dict):fail('题目条目格式无效。')
  v=db.get(QuestionVersion,e.get('versionId'));q=db.get(BankQuestion,v.question_id) if v else None;p=e.get('points')
  if not q or q.owner_id!=u.id or v.id in seen or isinstance(p,bool) or not isinstance(p,int) or not 1<=p<=100:fail('题目版本或分值无效，题目不得重复。')
  if v.data['unitId']!=unit:fail('试卷题目必须属于选定单元。')
  seen.add(v.id);rows.append({'versionId':v.id,'questionId':q.id,'points':p,'question':copy.deepcopy(v.data)})
 return {'title':title,'unitId':unit,'entries':rows,'total':sum(e['points'] for e in rows)}
@router.get('/papers')
def papers(request:Request,db=Depends(get_db)):
 u=teacher(request,db);return [paper_json(db,p) for p in db.scalars(select(ExamPaper).where(ExamPaper.owner_id==u.id))]
@router.post('/papers',status_code=201)
def new_paper(body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);r=ExamPaper(id=uid('paper'),owner_id=u.id,draft=paper_data(db,u,body),revision=1,reviewed=False);db.add(r);db.commit();return paper_json(db,r)
@router.put('/papers/{ident}')
def edit_paper(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);r=own(db,ExamPaper,ident,u);expected(r,body);r.draft=paper_data(db,u,body);r.revision+=1;r.reviewed=False;db.commit();return paper_json(db,r)
@router.post('/assemble')
def assemble(body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);count=body.get('count');total=body.get('total');kids=body.get('knowledgeIds',[]);unit=body.get('unitId')
 if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=100 or isinstance(total,bool) or not isinstance(total,int) or not count<=total<=count*100:fail('题数及总分无效。')
 if not isinstance(kids,list) or not 1<=len(kids)<=16 or any(not isinstance(k,str) or not db.get(KnowledgePoint,k) for k in kids):fail('请选择知识点。')
 candidates=[]
 for q in db.scalars(select(BankQuestion).where(BankQuestion.owner_id==u.id).order_by(BankQuestion.id)):
  v=db.scalar(select(QuestionVersion).where(QuestionVersion.question_id==q.id).order_by(QuestionVersion.number.desc()).limit(1))
  if v and v.data['unitId']==unit and set(v.data['knowledgeIds'])&set(kids) and (not body.get('kind') or v.data['kind']==body['kind']) and (not body.get('difficulty') or v.data['difficulty']==body['difficulty']):candidates.append(v)
 if len(candidates)<count:return {'sufficient':False,'available':len(candidates),'missing':count-len(candidates),'entries':[]}
 # Cover each requested knowledge point before filling remaining slots.
 selected=[]
 for k in kids:
  if any(k in v.data['knowledgeIds'] for v in selected):continue
  v=next((v for v in candidates if v not in selected and k in v.data['knowledgeIds']),None)
  if not v or len(selected)==count:return {'sufficient':False,'missingKnowledge':[k],'entries':[]}
  selected.append(v)
 selected+=(v for v in candidates if v not in selected);selected=selected[:count]
 return {'sufficient':True,'total':total,'entries':[{'versionId':v.id,'points':total//count+(i<total%count),'question':v.data} for i,v in enumerate(selected)]}
@router.post('/papers/{ident}/review')
def review_paper(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);r=own(db,ExamPaper,ident,u);expected(r,body)
 if not body.get('confirmed'):fail('请核对学生预览及分值后确认。')
 d=copy.deepcopy(r.draft);d['reviewRecord']={'actorId':u.id,'at':iso(now())};n=db.scalar(select(func.max(PaperVersion.number)).where(PaperVersion.paper_id==ident)) or 0;v=PaperVersion(id=uid('pv'),paper_id=ident,number=n+1,data=d);db.add(v);r.reviewed=True;r.revision+=1;db.commit();return paper_json(db,r)
def parse_time(value):
 try:
  d=datetime.fromisoformat(value.replace('Z','+00:00'))
  if d.tzinfo is None:fail('考试时间必须带时区。')
  return d.astimezone(timezone.utc).replace(tzinfo=None,microsecond=0)
 except (ValueError,AttributeError):fail('考试时间无效。')
@router.post('',status_code=201)
def publish_exam(body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);room=owned_class(db,u,body.get('classId'),True);v=db.get(PaperVersion,body.get('versionId'));paper=own(db,ExamPaper,v.paper_id,u) if v else None
 if not paper:fail('请先审核试卷。')
 key=str(body.get('requestKey',''))
 if not 8<=len(key)<=80:fail('发布请求标识无效。')
 key=hashlib.sha256((u.id+key).encode()).hexdigest();old=db.scalar(select(ClassExam).where(ClassExam.request_key==key))
 starts=parse_time(body.get('startsAt'));ends=parse_time(body.get('endsAt'));minutes=body.get('minutes')
 if isinstance(minutes,bool) or not isinstance(minutes,int) or not 1<=minutes<=240 or starts>=ends:fail('考试时间范围及限时无效。')
 if old:
  if (old.version_id,old.classroom_id,old.starts_at,old.ends_at,old.minutes)!=(v.id,room.id,starts,ends,minutes):fail('请求标识已用于其他发布内容。',409)
  return {'id':old.id,'created':False}
 members=list(db.scalars(select(ClassMember.student_id).where(ClassMember.classroom_id==room.id)))
 if not members:fail('班级没有学生。')
 r=ClassExam(id=uid('exam'),owner_id=u.id,classroom_id=room.id,version_id=v.id,starts_at=starts,ends_at=ends,minutes=minutes,request_key=key);db.add(r);db.flush()
 for sid in members:db.add(ExamSubmission(id=uid('sub'),exam_id=r.id,student_id=sid,answers={},automatic={},grades={},revision=0))
 db.commit();return {'id':r.id,'created':True}
def exam_access(db,u,ident,lock=False):
 e=db.scalar(select(ClassExam).where(ClassExam.id==ident).with_for_update()) if lock else db.get(ClassExam,ident)
 if not e:fail('考试不存在。',404)
 s=db.scalar(select(ExamSubmission).where(ExamSubmission.exam_id==ident,ExamSubmission.student_id==u.id).with_for_update()) if u.role=='student' else None
 if not (u.role=='teacher' and e.owner_id==u.id) and not s:fail('没有找到本人的考试。',404)
 return e,s
def expired(e,s):return now()>=min(e.ends_at,s.started_at+timedelta(minutes=e.minutes)) if s.started_at else now()>=e.ends_at
def student_paper(d):
 return {'title':d['title'],'total':d['total'],'entries':[{'versionId':x['versionId'],'points':x['points'],'question':{k:x['question'].get(k) for k in ['prompt','equation','kind','knowledgeIds']}} for x in d['entries']]}
def submission_json(db,s,e,teacher_view=False):
 shown=teacher_view or e.results_at is not None
 return {'id':s.id,'studentId':s.student_id,'studentName':db.get(Account,s.student_id).display_name,'revision':s.revision,'answers':s.answers,'startedAt':iso(s.started_at),'submittedAt':iso(s.submitted_at),'deadline':iso(min(e.ends_at,s.started_at+timedelta(minutes=e.minutes))) if s.started_at else iso(e.ends_at),**({'automatic':s.automatic,'grades':s.grades,'total':sum(v['score'] for v in s.grades.values()),'audits':[{'id':a.id,'actorId':a.actor_id,'data':a.data,'at':iso(a.created_at)} for a in db.scalars(select(ExamGradeAudit).where(ExamGradeAudit.submission_id==s.id))]} if shown else {})}
def exam_json(db,u,e,s=None):
 v=db.get(PaperVersion,e.version_id);full=u.role=='teacher' or e.results_at is not None
 result={'id':e.id,'classId':e.classroom_id,'versionId':v.id,'title':v.data['title'],'startsAt':iso(e.starts_at),'endsAt':iso(e.ends_at),'minutes':e.minutes,'serverTime':iso(now()),'resultsAt':iso(e.results_at)}
 if u.role=='teacher':result.update(paper=v.data,submissions=[submission_json(db,r,e,True) for r in db.scalars(select(ExamSubmission).where(ExamSubmission.exam_id==e.id))])
 elif s:
  result['submission']=submission_json(db,s,e)
  if s.started_at or e.results_at:result['paper']=v.data if full else student_paper(v.data)
 return result
@router.get('')
def exam_list(request:Request,db=Depends(get_db)):
 u=user_for(request,db);query=select(ClassExam).where(ClassExam.owner_id==u.id) if u.role=='teacher' else select(ClassExam).join(ExamSubmission).where(ExamSubmission.student_id==u.id) if u.role=='student' else select(ClassExam).where(False)
 return [{k:v for k,v in exam_json(db,u,e,db.scalar(select(ExamSubmission).where(ExamSubmission.exam_id==e.id,ExamSubmission.student_id==u.id))).items() if k not in ('paper','submissions','submission')} for e in db.scalars(query.order_by(ClassExam.starts_at.desc()))]
@router.get('/{ident}')
def detail(ident:str,request:Request,db=Depends(get_db)):
 u=user_for(request,db);e,s=exam_access(db,u,ident);return exam_json(db,u,e,s)
@router.post('/{ident}/start')
def start(ident:str,request:Request,db=Depends(get_db)):
 u=user_for(request,db);e,s=exam_access(db,u,ident,True)
 if not s:fail('请使用学生账号。',403)
 if s.submitted_at:return exam_json(db,u,e,s)
 if not s.started_at:
  if not e.starts_at<=now()<e.ends_at:fail('考试尚未开始或已截止。',409)
  if not db.get(ClassMember,(e.classroom_id,u.id)):fail('已移出班级，不能开始考试。',403)
  s.started_at=now();db.commit()
 return exam_json(db,u,e,s)
def save_answers(s,body,entries):
 expected(s,body);answers=body.get('answers')
 if not isinstance(answers,dict) or any(k not in {e['versionId'] for e in entries} for k in answers):fail('答案题目不属于本试卷。')
 safe={}
 for k,a in answers.items():
  if not isinstance(a,dict) or any(not isinstance(a.get(f,''),str) or len(a.get(f,''))>6000 for f in ['answer','reason']):fail('答案格式无效。')
  safe[k]={f:a.get(f,'') for f in ['answer','reason']}
 s.answers=safe;s.revision+=1
def finalize(db,s,e):
 if s.submitted_at:return
 entries=db.get(PaperVersion,e.version_id).data['entries'];automatic={};grades={}
 for row in entries:
  key=row['versionId'];q=row['question'];a=s.answers.get(key,{}).get('answer','');ver=assess_question(a,q) if a.strip() else {'status':'inconsistent','correct':False,'message':'未作答'};automatic[key]=ver
  if ver['status']!='unverified':grades[key]={'score':row['points'] if ver['correct'] else 0,'comment':ver.get('message',''),'source':'program'}
 s.automatic=automatic;s.grades=grades;s.submitted_at=now();s.revision+=1
@router.put('/{ident}/answers')
def save_draft(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=user_for(request,db);e,s=exam_access(db,u,ident,True)
 if not s or not s.started_at:fail('请先开始考试。',409)
 if not db.get(ClassMember,(e.classroom_id,u.id)):fail('已移出班级，答卷只读。',403)
 if s.submitted_at:fail('已提交答卷只读。',409)
 if expired(e,s):finalize(db,s,e);db.commit();fail('考试时间已到，已按服务器保存的草稿交卷。',409)
 save_answers(s,body,db.get(PaperVersion,e.version_id).data['entries']);db.commit();return exam_json(db,u,e,s)
@router.post('/{ident}/submit')
def submit(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=user_for(request,db);e,s=exam_access(db,u,ident,True)
 if not s or not s.started_at:fail('请先开始考试。',409)
 if not s.submitted_at:
  if not db.get(ClassMember,(e.classroom_id,u.id)):fail('已移出班级，答卷只读。',403)
  if not expired(e,s):save_answers(s,body,db.get(PaperVersion,e.version_id).data['entries'])
  finalize(db,s,e);db.commit()
 return exam_json(db,u,e,s)
@router.put('/{ident}/submissions/{sid}/grades')
def mark(ident:str,sid:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);e,_=exam_access(db,u,ident,True);s=db.get(ExamSubmission,sid)
 if not s or s.exam_id!=e.id:fail('答卷不存在。',404)
 if e.results_at:fail('成绩已发布，当前版本不可改写。',409)
 if not s.submitted_at and s.started_at and expired(e,s):finalize(db,s,e)
 if not s.submitted_at:fail('学生尚未提交。',409)
 expected(s,body);grades=copy.deepcopy(s.grades);updates=body.get('grades',{});entries={x['versionId']:x for x in db.get(PaperVersion,e.version_id).data['entries']}
 if not isinstance(updates,dict) or not updates:fail('请填写批阅意见和分数。')
 for k,g in updates.items():
  if not isinstance(g,dict):fail('批阅格式无效。')
  score=g.get('score');comment=g.get('comment','')
  if k not in entries or isinstance(score,bool) or not isinstance(score,int) or not 0<=score<=entries[k]['points'] or not isinstance(comment,str) or not comment.strip() or len(comment)>6000:fail('分数必须在本题范围内，并填写批阅依据。')
  grades[k]={'score':score,'comment':comment,'source':'teacher','actorId':u.id}
 db.add(ExamGradeAudit(id=uid('mark'),submission_id=s.id,actor_id=u.id,data={'before':s.grades,'after':grades,'revision':s.revision}));s.grades=grades;s.revision+=1;db.commit();return submission_json(db,s,e,True)
@router.post('/{ident}/results')
def release_results(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);e,_=exam_access(db,u,ident,True)
 if e.results_at:return {'published':True,'at':iso(e.results_at)}
 if not body.get('confirmed'):fail('发布后学生将看到成绩、解答和讲评；请确认。')
 v=db.get(PaperVersion,e.version_id);entries=v.data['entries'];subs=list(db.scalars(select(ExamSubmission).where(ExamSubmission.exam_id==e.id).with_for_update()))
 for s in subs:
  if not s.submitted_at and now()>=e.ends_at:finalize(db,s,e)
  if not s.submitted_at or len(s.grades)!=len(entries):fail('仍有未交卷或待人工批阅题目。',409)
 # Only now expose an existing teaching-task review projection for memory and wrong remediation.
 lesson=db.scalar(select(Lesson).where(Lesson.unit_id==v.data['unitId']).order_by(Lesson.position))
 if not lesson:fail('单元没有可关联课时。')
 questions=[{**x['question'],'id':x['versionId'],'kind':'check'} for x in entries];task=LearningTask(id=uid('task'),teacher_id=u.id,classroom_id=e.classroom_id,lesson_id=lesson.id,title='考试讲评 · '+v.data['title'],snapshot={'examId':e.id,'examVersionId':v.id,'lessonSnapshot':{'unitId':v.data['unitId'],'title':v.data['title'],'knowledgeIds':list({k for x in entries for k in x['question']['knowledgeIds']})},'goal':'对照原始答卷与讲评完成订正','blocks':[]},questions=questions,source='exam',due_date='',published_at=now());db.add(task);db.flush()
 for s in subs:
  rec=StudentRecord(id=uid('record'),student_id=s.student_id,task_id=task.id,completed=True,submitted_at=s.submitted_at,drafts={},observation='考试原始作答；批阅意见单独保留',feedback='；'.join(g['comment'] for g in s.grades.values()),feedback_at=now(),source='exam');db.add(rec);db.flush()
  for i,x in enumerate(entries):
   key=x['versionId'];a=s.answers.get(key,{});auto=s.automatic[key];attempt=Attempt(id=uid('attempt'),record_id=rec.id,question=i,answer=a.get('answer',''),reason=a.get('reason',''),helped=False,correct=auto['correct'],verification=auto);db.add(attempt);db.flush()
   if s.grades[key]['score']<x['points']:db.add(WrongQuestion(id=uid('wrong'),owner_id=s.student_id,record_id=rec.id,attempt_id=attempt.id,prompt=x['question'].get('equation') or x['question']['prompt'],answer=a.get('answer',''),reason=a.get('reason',''),details={'version':'dynamic_v1','source':'exam','examId':e.id,'submissionId':s.id,'paperVersionId':v.id,'questionVersionId':key,'equation':x['question'].get('equation',''),'originalPrompt':x['question']['prompt'],'knowledgeIds':x['question']['knowledgeIds'],'grade':s.grades[key],'causeConfirmed':False}))
 e.results_at=now();e.review_task_id=task.id;db.commit();return {'published':True,'at':iso(e.results_at),'reviewTaskId':task.id}
@router.get('/{ident}/export/{mode}')
def export_exam(ident:str,mode:str,request:Request,submissionId:str|None=None,db=Depends(get_db)):
 from .docx_export import template
 u=user_for(request,db);e,s=exam_access(db,u,ident);paper=db.get(PaperVersion,e.version_id).data
 if mode not in ['student','teacher','submission','grades','learning']:fail('导出类型无效。')
 if u.role!='teacher' and mode in ['teacher','grades']:fail('请使用教师账号。',403)
 if u.role=='student' and not e.results_at and (mode!='submission' or not s.submitted_at):fail('当前阶段不能导出试卷或记录。',403)
 doc=template();doc.add_heading(paper['title'],0)
 if mode=='grades':
  if not e.results_at:fail('请先确认发布成绩。',409)
  table=doc.add_table(rows=1,cols=3);table.style='Table Grid'
  for c,t in zip(table.rows[0].cells,['学生','答卷','总分']):c.text=t
  for r in db.scalars(select(ExamSubmission).where(ExamSubmission.exam_id==ident)):
   for c,t in zip(table.add_row().cells,[db.get(Account,r.student_id).display_name,r.id,str(sum(g['score'] for g in r.grades.values()))]):c.text=t
 else:
  if mode in ['submission','learning']:
   if u.role=='teacher':
    s=db.get(ExamSubmission,submissionId)
    if not s or s.exam_id!=ident:fail('请选择本场考试的答卷。',404)
   if not s.submitted_at:fail('请先提交答卷。',409)
  for i,row in enumerate(paper['entries']):
   q=row['question'];key=row['versionId'];doc.add_heading(str(i+1)+'. '+q['prompt']+'（'+str(row['points'])+'分）',1);doc.add_paragraph(q.get('equation',''))
   if mode=='teacher':doc.add_paragraph('参考答案：'+q['answer']);doc.add_paragraph('解析：'+(candidate_explanation(q['explanation']) if q.get('candidateJobId') or re.match(r'^AI候选[，,；;]',q.get('source','')) else q['explanation']))
   elif mode in ['submission','learning']:
    a=s.answers.get(key,{});doc.add_paragraph('原答案：'+a.get('answer',''));doc.add_paragraph('原解释：'+a.get('reason',''))
    if u.role=='teacher' or e.results_at:doc.add_paragraph('得分：'+str(s.grades.get(key,{}).get('score','待批阅')));doc.add_paragraph('讲评：'+s.grades.get(key,{}).get('comment',''))
 doc.add_paragraph('试卷固定版本：'+e.version_id);b=io.BytesIO();doc.save(b);return Response(b.getvalue(),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':'attachment; filename="exam-'+mode+'.docx"'})

def candidate_explanation(value):
 return re.sub(r'\s*本题为待教师审核的候选题[。.]?\s*$','',re.sub(r'\\+n(?![A-Za-z])','\n',value)).strip()

# Candidate stays in the existing ModelJob; adoption is an explicit bank draft creation.
@router.post('/bank/candidate/{job_id}',status_code=201)
def adopt_candidate(job_id:str,request:Request,db=Depends(get_db)):
 u=teacher(request,db);j=db.get(ModelJob,job_id)
 if not j or j.owner_id!=u.id or not j.input.get('examCandidate') or j.status!='succeeded':fail('候选任务不可采用。',404)
 old=db.scalar(select(BankQuestion).where(BankQuestion.id=='bq-'+j.id[4:36]))
 if old:return bank_json(db,old)
 d=checked_question(db,{**{k:j.result[k] for k in ['prompt','equation','answer','explanation']},'explanation':candidate_explanation(j.result['explanation']),**{k:j.input[k] for k in ['unitId','knowledgeIds','kind','difficulty']},'source':'AI生成；ModelJob '+j.id});d['candidateJobId']=j.id;r=BankQuestion(id='bq-'+j.id[4:36],owner_id=u.id,draft=d,reviewed=False,revision=1);db.add(r);db.commit();return bank_json(db,r)

@router.get('/learning-records/export')
def export_learning_records(request:Request,studentId:str|None=None,classId:str|None=None,db=Depends(get_db)):
 from .learning_memory import authorized
 from .models import HelpRecord,RepairAttempt
 from .docx_export import template
 u=user_for(request,db);sid,scope=authorized(db,u,studentId,classId);query=select(StudentRecord,LearningTask).join(LearningTask,StudentRecord.task_id==LearningTask.id).where(StudentRecord.student_id==sid)
 if scope is not None:query=query.where(LearningTask.classroom_id.in_(scope))
 doc=template();doc.add_heading('学习记录',0);doc.add_paragraph(db.get(Account,sid).display_name)
 for rec,task in db.execute(query.order_by(LearningTask.published_at,LearningTask.id)):
  doc.add_heading(task.title,1);doc.add_paragraph('任务：'+task.id+'；来源：'+task.source)
  for a in db.scalars(select(Attempt).where(Attempt.record_id==rec.id).order_by(Attempt.created_at,Attempt.id)):
   q=task.questions[a.question] if 0<=a.question<len(task.questions) else {};doc.add_heading(q.get('prompt','')+' '+q.get('equation',''),2);doc.add_paragraph('原答案：'+a.answer);doc.add_paragraph('原解释：'+a.reason);doc.add_paragraph('程序核验：'+str((a.verification or {}).get('status','unverified'))+'；'+('获得帮助' if a.helped else '独立作答'))
  for h in db.scalars(select(HelpRecord).where(HelpRecord.record_id==rec.id)):doc.add_paragraph('求助：'+h.kind+' '+h.message)
  for w in db.scalars(select(WrongQuestion).where(WrongQuestion.record_id==rec.id)):
   doc.add_heading('错题补救：'+w.prompt,2)
   for a in db.scalars(select(RepairAttempt).where(RepairAttempt.wrong_id==w.id).order_by(RepairAttempt.created_at)):doc.add_paragraph(str((a.details or {}).get('equation',''))+'；原答案：'+a.answer+'；核验：'+str((a.verification or {}).get('status','unverified')))
  if rec.feedback:doc.add_paragraph('教师反馈：'+rec.feedback)
 b=io.BytesIO();doc.save(b);return Response(b.getvalue(),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':'attachment; filename="learning-records.docx"'})
