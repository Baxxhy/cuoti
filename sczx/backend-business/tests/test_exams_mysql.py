"""Exam integration on isolated MySQL: snapshots, deadlines, leakage and immutable originals."""
import copy,json,os,secrets,subprocess,sys,unittest,uuid,io,zipfile
from pathlib import Path
from datetime import timedelta
import httpx
from sqlalchemy import select,func
from sczx_business.main import app
from sczx_business.database import engine,SessionLocal
from sczx_business.models import CourseUnit,Lesson,StudentRecord,ModelJob,WrongQuestion
from sczx_business.exam_models import ClassExam,ExamSubmission,QuestionVersion,ExamGradeAudit
from sczx_business.teaching import now,iso
from sczx_business.equation_tool import replay
from test_teaching_mysql import fixture,create_accounts
class EquationMathTests(unittest.TestCase):
 def test_nonzero_reversible_steps_and_no_arbitrary_code(self):
  r=replay('2x+6=10',[{'operation':'subtract','value':'6'},{'operation':'divide','value':'2'}]);self.assertEqual(r['equation'],'x = 2')
  for a in [{'operation':'divide','value':'0'},{'operation':'multiply','value':'0'},{'operation':'add','value':'x'},{'operation':'eval','value':'1'},{'operation':'add','value':'__import__("os")'}]:
   with self.subTest(a=a),self.assertRaises(Exception):replay('2x=4',[a])
@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class ExamTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  assert engine.url.database.startswith('sczx_test_');subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True);cls.password=secrets.token_urlsafe(24);create_accounts(cls.password,'exam-test-')
 async def asyncSetUp(self):
  self.fx=fixture('e-'+uuid.uuid4().hex[:6],'exam-test-');self.unit=self.fx['lesson']+'-unit'
  with SessionLocal.begin() as db:db.add(CourseUnit(id=self.unit,course_id=self.fx['lesson'].replace('-lesson','-course'),title='考试单元',position=1));db.flush();db.get(Lesson,self.fx['lesson']).unit_id=self.unit
  self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test');await self.login('t1');self.q={'prompt':'解方程并代回核对','equation':'2x+6=10','answer':'2','explanation':'两边先减6，再除以非零数2。','knowledgeIds':[self.fx['data']['knowledgeIds'][0]],'unitId':self.unit,'source':'自编验收'}
 async def asyncTearDown(self):await self.c.aclose()
 async def login(self,n):
  self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':'exam-test-'+n,'password':self.password});self.assertEqual(r.status_code,200)
 async def call(self,method,path,body=None,status=200):
  r=await self.c.request(method,'/api/exams'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
 async def question(self,application=False):
  q=await self.call('POST','/bank',{'data':{**self.q,**({'kind':'application'} if application else {})}},201);return await self.call('POST','/bank/'+q['id']+'/review',{'revision':q['revision'],'confirmed':True})
 async def paper_exam(self,application=False,start=None,end=None):
  q=await self.question(application);v=q['versions'][0]['id'];p=await self.call('POST','/papers',{'title':'自编检查','unitId':self.unit,'entries':[{'versionId':v,'points':10}]},201);p=await self.call('POST','/papers/'+p['id']+'/review',{'revision':p['revision'],'confirmed':True});body={'versionId':p['versions'][0]['id'],'classId':self.fx['classes'][0],'startsAt':iso(start or now()-timedelta(minutes=1)),'endsAt':iso(end or now()+timedelta(minutes=30)),'minutes':20,'requestKey':uuid.uuid4().hex};e=await self.call('POST','',body,201);return q,p,e['id'],body
 async def student_submit(self,e,answer='2'):
  await self.login('s0');d=await self.call('POST','/'+e+'/start',{});key=d['paper']['entries'][0]['versionId'];d=await self.call('POST','/'+e+'/submit',{'revision':d['submission']['revision'],'answers':{key:{'answer':answer,'reason':'我先减6再除以2。'}}});return key,d
 async def test_bank_versions_and_reference_rejection(self):
  q=await self.question();old=copy.deepcopy(q['versions'][0]);new={**self.q,'answer':'3'};q=await self.call('PUT','/bank/'+q['id'],{'revision':q['revision'],'data':new});await self.call('POST','/bank/'+q['id']+'/review',{'revision':q['revision'],'confirmed':True},422);self.assertEqual(q['versions'][0],old);await self.login('t2');await self.call('PUT','/bank/'+q['id'],{'revision':q['revision'],'data':self.q},404)
 async def test_course_import_and_unreviewed_cannot_enter_paper(self):
  r=await self.call('POST','/bank/import',{'lessonId':self.fx['lesson']},201);self.assertEqual(len(r['ids']),6);rows=await self.call('GET','/bank');q=next(q for q in rows if q['id']==r['ids'][0]);self.assertFalse(q['reviewed']);self.assertEqual(q['draft']['courseSource']['lessonId'],self.fx['lesson']);await self.call('POST','/papers',{'title':'未审','unitId':self.unit,'entries':[{'versionId':q['id'],'points':10}]},422)
 async def test_constraints_report_shortage_and_do_not_pad(self):
  await self.question();r=await self.call('POST','/assemble',{'unitId':self.unit,'knowledgeIds':[self.fx['data']['knowledgeIds'][0]],'count':3,'total':30});self.assertFalse(r['sufficient']);self.assertEqual(r['missing'],2);r=await self.call('POST','/assemble',{'unitId':self.unit,'knowledgeIds':[self.fx['data']['knowledgeIds'][0]],'count':1,'total':10});self.assertTrue(r['sufficient']);self.assertEqual(sum(e['points'] for e in r['entries']),10)
 async def test_answer_secrecy_drafts_revision_submit_idempotency(self):
  q,p,e,body=await self.paper_exam();await self.call('POST','',body,201);await self.login('s0');d=await self.call('GET','/'+e);self.assertNotIn('paper',d);d=await self.call('POST','/'+e+'/start',{});self.assertNotIn('answer',d['paper']['entries'][0]['question']);self.assertNotIn('grades',d['submission']);k=q['versions'][0]['id'];answers={k:{'answer':'2','reason':'原始解释'}};d=await self.call('PUT','/'+e+'/answers',{'revision':0,'answers':answers});await self.call('PUT','/'+e+'/answers',{'revision':0,'answers':answers},409);d=await self.call('POST','/'+e+'/submit',{'revision':d['submission']['revision'],'answers':answers});self.assertNotIn('automatic',d['submission']);d2=await self.call('POST','/'+e+'/submit',{'revision':0,'answers':{}});self.assertEqual(d2['submission']['answers'],answers);await self.call('PUT','/'+e+'/answers',{'revision':d['submission']['revision'],'answers':{}},409)
 async def test_future_start_and_cross_student_class_permissions(self):
  q,p,e,b=await self.paper_exam(start=now()+timedelta(minutes=10));await self.login('s0');await self.call('POST','/'+e+'/start',{},409);await self.login('s6');await self.call('GET','/'+e,status=404);await self.login('t2');await self.call('GET','/'+e,status=404)
 async def test_server_deadline_submits_only_saved_answers(self):
  q,p,e,b=await self.paper_exam();await self.login('s0');d=await self.call('POST','/'+e+'/start',{});k=q['versions'][0]['id'];await self.call('PUT','/'+e+'/answers',{'revision':0,'answers':{k:{'answer':'0','reason':'保存的原错'}}})
  with SessionLocal.begin() as db:s=db.scalar(select(ExamSubmission).where(ExamSubmission.exam_id==e,ExamSubmission.student_id=='exam-test-s0'));s.started_at=now()-timedelta(hours=1)
  await self.call('PUT','/'+e+'/answers',{'revision':1,'answers':{k:{'answer':'2'}}},409);d=await self.call('GET','/'+e);self.assertEqual(d['submission']['answers'][k]['answer'],'0');self.assertTrue(d['submission']['submittedAt'])
 async def test_application_manual_grading_audit_release_wrong_and_unchanged_original(self):
  q,p,e,b=await self.paper_exam(True);k,d=await self.student_submit(e);sid=d['submission']['id'];await self.login('t1');d=await self.call('GET','/'+e);s=next(s for s in d['submissions'] if s['id']==sid);self.assertEqual(s['automatic'][k]['status'],'unverified');self.assertNotIn(k,s['grades']);original=copy.deepcopy(s['answers']);await self.call('POST','/'+e+'/results',{'confirmed':True},409);marked=await self.call('PUT','/'+e+'/submissions/'+sid+'/grades',{'revision':s['revision'],'grades':{k:{'score':4,'comment':'数值正确，未充分说明建模。'}}});self.assertEqual(marked['total'],4);self.assertEqual(len(marked['audits']),1)
  with SessionLocal.begin() as db:
   rows=db.scalars(select(ExamSubmission).where(ExamSubmission.exam_id==e)).all()
   for row in rows:
    if row.id!=sid:row.answers={};row.automatic={k:{'correct':False,'status':'inconsistent'}};row.grades={k:{'score':0,'comment':'未作答','source':'program'}};row.submitted_at=now()
  await self.call('POST','/'+e+'/results',{'confirmed':True});await self.call('POST','/'+e+'/results',{'confirmed':True});await self.call('PUT','/'+e+'/submissions/'+sid+'/grades',{'revision':marked['revision'],'grades':{k:{'score':10,'comment':'覆盖'}}},409);await self.login('s0');d=await self.call('GET','/'+e);self.assertEqual(d['submission']['total'],4);self.assertEqual(d['submission']['answers'],original);self.assertEqual(d['paper']['entries'][0]['question']['answer'],'2')
  with SessionLocal() as db:w=db.scalar(select(WrongQuestion).where(WrongQuestion.owner_id=='exam-test-s0',WrongQuestion.details['examId'].as_string()==e));self.assertEqual(w.details['questionVersionId'],k);self.assertEqual(w.answer,'2')
 async def test_exports_black_font_student_secrecy(self):
  q,p,e,b=await self.paper_exam();r=await self.c.get('/api/exams/'+e+'/export/student');self.assertEqual(r.status_code,200)
  with zipfile.ZipFile(io.BytesIO(r.content)) as z:xml=z.read('word/document.xml').decode();styles=z.read('word/styles.xml').decode();self.assertNotIn('参考答案',xml);self.assertIn('宋体',styles);self.assertIn('Times New Roman',styles);self.assertIn('000000',styles)
  await self.login('s0');self.assertEqual((await self.c.get('/api/exams/'+e+'/export/teacher')).status_code,403);self.assertEqual((await self.c.get('/api/exams/'+e+'/export/student')).status_code,403)
 async def test_equation_replay_restore_undo_and_other_student(self):
  await self.login('s0')
  with SessionLocal() as db:r=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.fx['tasks'][0],StudentRecord.student_id=='exam-test-s0'));rid=r.id
  path='/api/equation-tools/'+rid+'/0';d=(await self.c.get(path)).json();self.assertEqual(d['revision'],0);r=await self.c.put(path,json={'revision':0,'actions':[{'operation':'add','value':'3'}],'explanation':'两边同时加3。'});self.assertEqual(r.status_code,200,r.text);d=r.json();self.assertEqual((await self.c.get(path)).json(),d);r=await self.c.put(path,json={'revision':d['revision'],'actions':[{'operation':'divide','value':'0'}]});self.assertEqual(r.status_code,422);r=await self.c.put(path,json={'revision':d['revision'],'actions':[],'explanation':'撤销后保持原式'});self.assertEqual(r.status_code,200);await self.login('s1');self.assertEqual((await self.c.get(path)).status_code,404)
 async def test_exam_snapshot_survives_question_and_paper_edits(self):
  q,p,e,b=await self.paper_exam();version=q['versions'][0]['id'];old=copy.deepcopy((await self.call('GET','/'+e))['paper']);q=await self.call('PUT','/bank/'+q['id'],{'revision':q['revision'],'data':{**self.q,'prompt':'新修订题','equation':'x+4=9','answer':'5'}});q=await self.call('POST','/bank/'+q['id']+'/review',{'revision':q['revision'],'confirmed':True});self.assertEqual(q['versions'][1]['id'],version);p=await self.call('PUT','/papers/'+p['id'],{'revision':p['revision'],'title':'新草稿','unitId':self.unit,'entries':[{'versionId':q['versions'][0]['id'],'points':20}]});self.assertFalse(p['reviewed']);self.assertEqual((await self.call('GET','/'+e))['paper'],old)
 async def test_grading_out_of_range_and_stale_revision_do_not_overwrite(self):
  q,p,e,b=await self.paper_exam();k,d=await self.student_submit(e,'0');sid=d['submission']['id'];await self.login('t1');d=await self.call('GET','/'+e);s=next(s for s in d['submissions'] if s['id']==sid);await self.call('PUT','/'+e+'/submissions/'+sid+'/grades',{'revision':s['revision'],'grades':{k:{'score':11,'comment':'超过分值'}}},422);marked=await self.call('PUT','/'+e+'/submissions/'+sid+'/grades',{'revision':s['revision'],'grades':{k:{'score':2,'comment':'过程部分正确'}}});await self.call('PUT','/'+e+'/submissions/'+sid+'/grades',{'revision':s['revision'],'grades':{k:{'score':8,'comment':'并发覆盖'}}},409);self.assertEqual(marked['automatic'][k]['correct'],False);self.assertEqual(marked['answers'][k]['answer'],'0');self.assertEqual(marked['total'],2)
 async def test_candidate_job_is_owned_and_not_implicitly_approved(self):
  from sczx_business.job_access import validate_retry
  jid='job-'+uuid.uuid4().hex
  with SessionLocal.begin() as db:db.add(ModelJob(id=jid,owner_id='exam-test-t1',capability='text',request_key=uuid.uuid4().hex,input_hash=uuid.uuid4().hex,input={'examCandidate':True,'unitId':self.unit,'knowledgeIds':self.q['knowledgeIds'],'kind':'calculation','difficulty':'easy'},status='succeeded',result={'prompt':self.q['prompt'],'equation':self.q['equation'],'answer':self.q['answer'],'explanation':self.q['explanation']}))
  with SessionLocal() as db:validate_retry(db,db.get(ModelJob,jid))
  q=await self.call('POST','/bank/candidate/'+jid,{},201);self.assertFalse(q['reviewed']);self.assertFalse(q['versions']);again=await self.call('POST','/bank/candidate/'+jid,{},201);self.assertEqual(q['id'],again['id']);await self.login('t2');await self.call('POST','/bank/candidate/'+jid,{},404)
 async def test_learning_record_export_scope(self):
  await self.login('s0');r=await self.c.get('/api/exams/learning-records/export');self.assertEqual(r.status_code,200)
  with zipfile.ZipFile(io.BytesIO(r.content)) as z:xml=z.read('word/document.xml').decode();self.assertIn(self.fx['tasks'][0],xml);self.assertNotIn(self.fx['tasks'][4],xml)
  r=await self.c.get('/api/exams/learning-records/export?studentId=exam-test-s1');self.assertEqual(r.status_code,404);await self.login('t2');r=await self.c.get('/api/exams/learning-records/export?studentId=exam-test-s0&classId='+self.fx['classes'][0]);self.assertEqual(r.status_code,404)
