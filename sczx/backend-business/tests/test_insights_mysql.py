"""Step15: actual MySQL projections, preserved facts, scoped operations."""
import os,sys,subprocess,secrets,uuid,copy,asyncio,unittest
from pathlib import Path
from datetime import datetime,timedelta
import httpx
from sqlalchemy import select,text
from sczx_business.database import engine,SessionLocal
from sczx_business.models import *
from sczx_business.main import app
from sczx_business.insights import class_report,period
from sczx_business import learning_memory as memory
from test_teaching_mysql import create_accounts,fixture

@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class InsightsTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  assert engine.url.database.startswith('sczx_test_')
  subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True)
  cls.password=secrets.token_urlsafe(24);create_accounts(cls.password,'insights-')
  from sczx_business.security import hash_password
  with SessionLocal.begin() as db:db.add(Account(id='insights-admin',username='insights-admin',display_name='管理验收',role='admin',password_hash=hash_password(cls.password)))
 async def asyncSetUp(self):
  self.fx=fixture('i-'+uuid.uuid4().hex[:8],'insights-');self.task=self.fx['tasks'][0];self.room=self.fx['classes'][0];self.kp=self.fx['lesson'].replace('-lesson','-kp')
  self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test');await self.login('t1')
  with SessionLocal() as db:self.rid=db.scalar(select(StudentRecord.id).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='insights-s0'))
 async def asyncTearDown(self):await self.c.aclose()
 async def login(self,who):
  self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':'insights-'+who,'password':self.password});self.assertEqual(r.status_code,200,r.text)
 async def call(self,method,path,body=None,status=200):
  r=await self.c.request(method,'/api'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
 def attempt(self,correct=False,question=2,sid='s0',helped=False,verification=None,at=None,task=None):
  with SessionLocal.begin() as db:
   rid=db.scalar(select(StudentRecord.id).where(StudentRecord.task_id== (task or self.task),StudentRecord.student_id=='insights-'+sid));a=Attempt(id='attempt-'+uuid.uuid4().hex,record_id=rid,question=question,answer='8' if correct else '2',reason='保持原始解释',correct=correct,helped=helped,verification=verification or {'status':'verified' if correct else 'inconsistent'},created_at=at or datetime(2026,11,11,10,0)+timedelta(seconds=uuid.uuid4().int%600));db.add(a);return a.id
 async def report(self,extra=''):return await self.call('GET','/insights?classId='+self.room+extra)
 async def test_retries_count_unique_and_latest(self):
  self.attempt(at=datetime(2026,11,11,10));self.attempt(True,at=datetime(2026,11,11,10,1));self.attempt(True,at=datetime(2026,11,11,10,2));r=await self.report();self.assertEqual(r['stats']['attempts'],3);self.assertEqual(r['stats']['answeredQuestions'],1);self.assertEqual(r['stats']['independentCorrectQuestions'],1);self.assertEqual(r['stats']['independentCorrectStudents'],1)
  q=next(q for q in r['questions'] if q['taskId']==self.task and q['index']==2);self.assertEqual(q['students'],1);self.assertEqual(q['attempts'],3)
  p=await self.call('GET','/platform');task=next(t for t in p['tasks'] if t['id']==self.task);self.assertEqual(task['summary']['metrics'],r['stats']|{} if False else next(s for s in r['students'] if s['id']=='insights-s0')['metrics'])
 async def test_helped_unknown_and_manual_never_auto_correct(self):
  self.attempt(True,helped=True);self.attempt(True,question=3,verification={'status':'unverified'});r=await self.report();self.assertEqual(r['stats']['independentCorrectQuestions'],0);self.assertGreater(r['stats']['unverifiedQuestions'],0);self.assertTrue(r['reviewQueue'])
 async def test_time_range_and_sql_session_timezone_consistent(self):
  self.attempt(at=datetime(2020,11,11,8));self.attempt(question=3,at=datetime(2020,11,12,8));r=await self.report('&start=2020-11-11&end=2020-11-11');self.assertEqual(r['stats']['attempts'],1)
  with SessionLocal() as db:
   actor=db.get(Account,'insights-t1');a=class_report(db,actor,self.room,start='2020-11-11',end='2020-11-11');db.execute(text("SET time_zone='+00:00'"));b=class_report(db,actor,self.room,start='2020-11-11',end='2020-11-11');self.assertEqual(a['stats'],b['stats']);db.execute(text("SET time_zone='+08:00'"))
  await self.call('GET','/insights?classId='+self.room+'&start=2026-12-01&end=2026-11-01',status=422)
 async def test_class_scoping_cross_student_and_removed(self):
  self.attempt();await self.call('GET','/insights?classId='+self.fx['classes'][2],status=404)
  await self.call('GET','/insights?classId='+self.room+'&taskId='+self.fx['tasks'][2],status=404)
  with SessionLocal.begin() as db:db.delete(db.get(ClassMember,(self.room,'insights-s0')))
  r=await self.report();self.assertEqual(r['stats']['attempts'],0);self.assertNotIn('insights-s0',{s['id'] for s in r['students']});self.assertGreater(r['stats']['inactiveRecords'],0)
  await self.login('s1');await self.call('GET','/insights?classId='+self.room,status=404)
 def intervention(self,**kw):return {'kind':'learning','content':'先观察两边共同变化，再完成新的独立检查','knowledgeId':self.kp,'studentIds':['insights-s0'],'requestKey':uuid.uuid4().hex,'target':{'taskId':self.task,'kind':'check'},**kw}
 async def test_intervention_delivery_submission_not_retest_and_new_answer(self):
  body=self.intervention();result=await self.call('POST','/teaching/tasks/'+self.task+'/supplements',body,201);sid=result['id'];await self.login('s0');await self.call('POST','/teaching/supplements/'+sid+'/start',{});await self.call('POST','/teaching/supplements/'+sid+'/submit',{'response':'已阅读并写下两边同时加3'})
  rows=await self.call('GET','/teaching/tasks/'+self.task+'/supplements');o=next(r for r in rows if r['id']==sid)['recipients'][0]['outcome'];self.assertFalse(o['independentPassed']);self.attempt(True);rows=await self.call('GET','/teaching/tasks/'+self.task+'/supplements');o=next(r for r in rows if r['id']==sid)['recipients'][0]['outcome'];self.assertTrue(o['independentPassed'])
 async def test_intervention_repeated_old_question_not_new_retest(self):
  self.attempt();body=self.intervention(kind='retest');sid=(await self.call('POST','/teaching/tasks/'+self.task+'/supplements',body,201))['id'];self.attempt(True);rows=await self.call('GET','/teaching/tasks/'+self.task+'/supplements');o=next(r for r in rows if r['id']==sid)['recipients'][0]['outcome'];self.assertFalse(o['independentPassed']);self.assertEqual(o['newAttempts'],1)
 async def test_difficulty_requires_evidence_and_confirmation_targets(self):
  await self.call('POST','/teaching/tasks/'+self.task+'/supplements',self.intervention(difficultyOnly=True),422);self.attempt();await self.call('POST','/teaching/tasks/'+self.task+'/supplements',self.intervention(difficultyOnly=True),201)
 async def test_intervention_concurrent_idempotent_reject_changed_payload(self):
  body=self.intervention();path='/api/teaching/tasks/'+self.task+'/supplements';rr=await asyncio.gather(*[self.c.post(path,json=body) for _ in range(2)]);self.assertTrue(all(r.status_code==201 for r in rr),[r.text for r in rr]);self.assertEqual(rr[0].json()['id'],rr[1].json()['id']);await self.call('POST',path[4:],{**body,'content':'另一安排'},409)
 async def test_targets_personal_wrong_other_student_and_other_class_rejected(self):
  await self.call('POST','/teaching/tasks/'+self.task+'/supplements',self.intervention(target={'taskId':self.fx['tasks'][2],'kind':'learn'}),422)
  with SessionLocal.begin() as db:db.add(WrongQuestion(id='w-'+self.task,owner_id='insights-s0',prompt='个人错题',answer='2',details={}))
  await self.call('POST','/teaching/tasks/'+self.task+'/supplements',self.intervention(target={'wrongId':'w-'+self.task}),422)
 async def test_append_review_preserves_original_verification(self):
  aid=self.attempt(verification={'status':'unverified'});m=await self.call('GET','/memory?studentId=insights-s0&classId='+self.room);e=next(e for i in m['items'] for e in i['evidence'] if e['eventId']=='attempt:'+aid);await self.call('POST','/insights/reviews',{'studentId':'insights-s0','classId':self.room,'knowledgeId':self.kp,'evidenceId':e['evidenceId'],'reason':'请补充等式两边的运算过程','decision':'returned','expectedRevision':m['revision'],'requestKey':uuid.uuid4().hex},201)
  with SessionLocal() as db:self.assertEqual(db.get(Attempt,aid).verification,{'status':'unverified'});self.assertEqual(db.get(Attempt,aid).answer,'2')
 async def new_issue(self,who='s0',category='learning'):
  await self.login(who);return await self.call('POST','/support',{'text':'为什么两边都要加3？'+uuid.uuid4().hex[:4],'category':category,'taskId':self.task if category=='learning' else None,'requestKey':uuid.uuid4().hex},201)
 async def test_multi_issues_reply_close_history_and_private(self):
  a=await self.new_issue();b=await self.new_issue();await self.login('t1');rows=await self.call('GET','/support');self.assertTrue({a['id'],b['id']}<={r['id'] for r in rows});body={'status':'replied','content':'试着分别计算等式两边','expectedRevision':a['revision'],'requestKey':uuid.uuid4().hex};r=await self.call('POST','/support/'+a['id']+'/events',body);self.assertEqual(r['status'],'replied');self.assertEqual(len(r['history']),2)
  await self.call('POST','/support/'+a['id']+'/events',{**body,'requestKey':uuid.uuid4().hex},409);await self.login('s1');self.assertNotIn(a['id'],{r['id'] for r in await self.call('GET','/support')});await self.call('POST','/support/'+a['id']+'/events',body,404)
  await self.login('t2');await self.call('POST','/support/'+a['id']+'/events',body,404)
 async def test_admin_only_system_content_and_legacy_read_preserved(self):
  learning=await self.new_issue();system=await self.new_issue(category='system');await self.login('admin');rows=await self.call('GET','/support');self.assertNotIn(learning['id'],{r['id'] for r in rows});self.assertIn(system['id'],{r['id'] for r in rows})
 async def test_stale_platform_cannot_erase_reply_or_state(self):
  a=await self.new_issue();await self.login('t1');await self.call('POST','/support/'+a['id']+'/events',{'status':'replied','content':'历史保护回复','expectedRevision':1,'requestKey':uuid.uuid4().hex});await self.login('s0');await self.call('PUT','/platform',{'data':{'issue':{'id':a['id'],'text':'过期改写','reply':'伪造','resolved':False}}});rows=await self.call('GET','/support');r=next(r for r in rows if r['id']==a['id']);self.assertEqual(r['reply'],'历史保护回复');self.assertEqual(r['text'],a['text'])
 async def test_issue_concurrent_revision_and_creation_replay(self):
  a=await self.new_issue();await self.login('t1');body={'status':'processing','content':'正在核查','expectedRevision':1,'requestKey':uuid.uuid4().hex};path='/api/support/'+a['id']+'/events';rr=await asyncio.gather(*[self.c.post(path,json={**body,'requestKey':uuid.uuid4().hex}) for _ in range(2)]);self.assertEqual(sorted(r.status_code for r in rr),[200,409])
 async def test_all_intervention_types_real_wrong_and_prerequisite_target(self):
  aid=self.attempt()
  with SessionLocal.begin() as db:db.add(WrongQuestion(id='wrong-'+self.task,record_id=self.rid,owner_id='insights-s0',attempt_id=aid,prompt='3z=18',answer='2',details={'knowledgeIds':[self.kp]}))
  for kind in ['note','learning','foundation','retest','correction']:
   body=self.intervention(kind=kind)
   if kind=='correction':body['target']={'wrongId':'wrong-'+self.task}
   r=await self.call('POST','/teaching/tasks/'+self.task+'/supplements',body,201);rows=await self.call('GET','/teaching/tasks/'+self.task+'/supplements');item=next(i for i in rows if i['id']==r['id']);self.assertEqual(item['kind'],kind);self.assertFalse(item['recipients'][0]['outcome']['independentPassed'])
 async def test_model_failure_queue_admin_metadata_and_current_owner_retry(self):
  aid='job-'+uuid.uuid4().hex
  with SessionLocal.begin() as db:db.add(ModelJob(id=aid,owner_id='insights-s0',record_id=self.rid,capability='text',request_key=uuid.uuid4().hex,input_hash=uuid.uuid4().hex*2,input={'prompt':'学生私人原文'},status='failed',error='私人原文错误详情'))
  await self.login('admin');rows=await self.call('GET','/ai/failures');row=next(r for r in rows if r['id']==aid);self.assertFalse(row['canRetry']);self.assertNotIn('私人',row['error']);await self.call('GET','/ai/jobs/'+aid,status=404);await self.call('POST','/ai/jobs/'+aid+'/retry',status=404)
  await self.login('s0');rows=await self.call('GET','/ai/failures');self.assertTrue(next(r for r in rows if r['id']==aid)['canRetry']);await self.call('POST','/ai/jobs/'+aid+'/retry');await self.call('POST','/ai/jobs/'+aid+'/retry',status=409)
 async def test_retry_rejects_withdrawn_case_and_stale_lesson(self):
  ids=[]
  with SessionLocal.begin() as db:
   case=TeachingCase(id='case-'+self.task,title='撤回案例',source='',content='',status='withdrawn');db.add(case)
   for cap,data in [('text',{'caseId':case.id}),('lesson_agent',{'lessonId':self.fx['lesson'],'lesson':{'versionId':'obsolete'}})]:
    ident='job-'+uuid.uuid4().hex;ids.append(ident);db.add(ModelJob(id=ident,owner_id='insights-t1',capability=cap,request_key=uuid.uuid4().hex,input_hash=uuid.uuid4().hex*2,input=data,status='failed',error='test'))
  for ident in ids:await self.call('POST','/ai/jobs/'+ident+'/retry',status=409)
 async def test_dashboard_record_and_class_same_metric_definitions(self):
  self.attempt(True);r=await self.report();dash=await self.call('GET','/teaching/dashboard?classId='+self.room);self.assertEqual(dash['learningMetrics'],r['stats']);p=await self.call('GET','/platform');rec=next(r for r in p['studentRecords'][self.task] if r['studentId']=='insights-s0');self.assertEqual(rec['metrics']['independentCorrectQuestions'],1)
