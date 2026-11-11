"""Step18 real MySQL: teacher/student classroom, groups and explicit community sharing."""
import os,sys,subprocess,secrets,unittest,uuid,copy,asyncio
from pathlib import Path
import httpx
from sqlalchemy import select
from sczx_business.main import app
from sczx_business.database import engine,SessionLocal
from sczx_business.models import CourseUnit,Lesson,CaseVersion,TeachingCase,LessonDraft,LessonDraftVersion,LearningTask,StudentRecord,Attempt
from sczx_business.classroom_models import LiveAnswer,LiveActivity
from sczx_business.exam_models import ExamPaper,PaperVersion
from sczx_business.lesson_seed import first_lesson
from test_teaching_mysql import create_accounts,fixture
@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class ClassroomTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  assert engine.url.database.startswith('sczx_test_');subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True);cls.password=secrets.token_urlsafe(24);create_accounts(cls.password,'class-test-')
 async def asyncSetUp(self):
  self.fx=fixture('cl-'+uuid.uuid4().hex[:6],'class-test-');self.kid=self.fx['data']['knowledgeIds'][0];self.unit=self.fx['lesson']+'-unit'
  with SessionLocal.begin() as db:db.add(CourseUnit(id=self.unit,course_id=self.fx['lesson'].replace('-lesson','-course'),title='课堂验收',position=1));db.flush();db.get(Lesson,self.fx['lesson']).unit_id=self.unit
  self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test');await self.login('t1')
 async def asyncTearDown(self):await self.c.aclose()
 async def login(self,n):
  self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':'class-test-'+n,'password':self.password});self.assertEqual(r.status_code,200)
 async def call(self,method,path,body=None,status=200):
  r=await self.c.request(method,'/api'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
 async def live(self):
  s=await self.call('POST','/live',{'classId':self.fx['classes'][0],'lessonId':self.fx['lesson']},201);return await self.call('POST','/live/'+s['id']+'/push',{'revision':s['revision'],'question':0})
 async def test_live_source_permission_and_no_answer_leak(self):
  s=await self.live();self.assertEqual(s['versionId'],self.fx['lesson'].replace('-lesson','-version'));await self.login('t2');await self.call('GET','/live/'+s['id'],status=404);await self.login('s6');await self.call('GET','/live/'+s['id'],status=404);await self.login('s0');r=await self.call('POST','/live/'+s['id']+'/join',{});self.assertTrue(r['joined']);self.assertNotIn('answer',r['activities'][0]['question']);self.assertNotIn('answers',r['activities'][0])
 async def test_draft_restore_submit_idempotency_stats_feedback_end_and_growth(self):
  s=await self.live();aid=s['currentId'];await self.login('s0');await self.call('POST','/live/'+s['id']+'/join',{});body={'revision':0,'answer':'0','reason':'原错，先猜0','submit':False};r=await self.call('PUT','/live/'+s['id']+'/activities/'+aid+'/answer',body);self.assertEqual(r['activities'][0]['answer']['answer'],'0');body.update(revision=1,submit=True);r=await self.call('PUT','/live/'+s['id']+'/activities/'+aid+'/answer',body);self.assertNotIn('verification',r['activities'][0]['answer']);await self.call('PUT','/live/'+s['id']+'/activities/'+aid+'/answer',body);await self.login('t1');r=await self.call('GET','/live/'+s['id']);self.assertEqual(r['activities'][0]['stats']['submitted'],1);self.assertEqual(r['activities'][0]['stats']['incorrect'],1);r=await self.call('PUT','/live/'+s['id']+'/activities/'+aid+'/feedback',{'text':'两边同时加3，再代回核对。'});r=await self.call('POST','/live/'+s['id']+'/end',{'revision':r['revision']});task=r['taskId'];await self.call('POST','/live/'+s['id']+'/end',{'revision':0});await self.login('s0');await self.call('PUT','/live/'+s['id']+'/activities/'+aid+'/answer',{'revision':2,'answer':'8','submit':True},409);memory=await self.call('GET','/memory');self.assertTrue(any(e.get('taskId')==task for k in memory['items'] for e in k['evidence']))
 async def test_old_activity_cannot_accept_late_answer_after_push(self):
  s=await self.live();old=s['currentId'];s=await self.call('POST','/live/'+s['id']+'/push',{'revision':s['revision'],'question':1});await self.login('s0');await self.call('POST','/live/'+s['id']+'/join',{});await self.call('PUT','/live/'+s['id']+'/activities/'+old+'/answer',{'revision':0,'answer':'8','submit':True},409)
 async def test_concurrent_duplicate_answers_count_once(self):
  s=await self.live();await self.login('s0');await self.call('POST','/live/'+s['id']+'/join',{});path='/api/live/'+s['id']+'/activities/'+s['currentId']+'/answer';body={'revision':0,'answer':'8','reason':'两边加3','submit':True};r=await asyncio.gather(self.c.put(path,json=body),self.c.put(path,json=body));self.assertEqual([x.status_code for x in r],[200,200]);await self.login('t1');r=await self.call('GET','/live/'+s['id']);self.assertEqual(r['activities'][0]['stats']['submitted'],1)
 def paper(self):
  pid='paper-'+uuid.uuid4().hex[:20];vid='pv-'+uuid.uuid4().hex[:20];q=self.fx['data']['questions'][0]
  with SessionLocal.begin() as db:db.add(ExamPaper(id=pid,owner_id='class-test-t1',draft={},revision=1,reviewed=True));db.flush();db.add(PaperVersion(id=vid,paper_id=pid,number=1,data={'title':'本次分层练习','unitId':self.unit,'entries':[{'versionId':vid+'q','points':10,'question':q}],'total':10}))
  return vid
 async def test_group_evidence_manual_adjust_publish_targets_and_new_attempt(self):
  ev=await self.call('GET','/groups/suggestions?classId='+self.fx['classes'][0]+'&knowledgeId='+self.kid);self.assertTrue(all(s['suggestion']=='证据不足' for s in ev['students']));vid=self.paper();g=await self.call('POST','/groups',{'classId':self.fx['classes'][0],'knowledgeId':self.kid,'groups':[{'label':'巩固','studentIds':['class-test-s0'],'versionId':vid}]},201);g=await self.call('PUT','/groups/'+g['id'],{'revision':0,'groups':[{'label':'拓展','studentIds':['class-test-s0'],'versionId':vid},{'label':'巩固','studentIds':['class-test-s1'],'versionId':vid}]});await self.call('POST','/groups/'+g['id']+'/publish',{'revision':g['revision'],'confirmed':False},422);g=await self.call('POST','/groups/'+g['id']+'/publish',{'revision':g['revision'],'confirmed':True});self.assertEqual(len(g['tasks']),2);task=next(t['id'] for t in g['tasks'] if t['title'].startswith('拓展'));await self.login('s2');platform=await self.call('GET','/platform');self.assertNotIn(task,{t['id'] for t in platform['tasks']});await self.login('s0');await self.call('POST','/records/'+task+'/attempts',{'question':0,'answer':'8','reason':'共同加3'},201);await self.login('t1');gid=g['id'];g=next(item for item in await self.call('GET','/groups') if item['id']==gid);self.assertTrue(any(t['independentCorrectStudents']==1 for t in g['tasks']));await self.login('t2');await self.call('PUT','/groups/'+g['id'],{'revision':1,'groups':[]},404)
 async def test_group_rejects_other_class_duplicate_members_and_unreviewed_paper(self):
  v=self.paper()
  for ids in [['class-test-s6'],['class-test-s0','class-test-s0']]:await self.call('POST','/groups',{'classId':self.fx['classes'][0],'knowledgeId':self.kid,'groups':[{'label':'巩固','studentIds':ids,'versionId':v}]},422)
 def source(self,published=True):
  cid='case-'+uuid.uuid4().hex[:20];vid='cv-'+uuid.uuid4().hex[:20];data={'title':'自编共同运算案例','content':'出示x−3=5，两边同时加3。','source':'项目自编','author':'原作者','knowledgeIds':[self.kid]}
  with SessionLocal.begin() as db:db.add(TeachingCase(id=cid,title=data['title'],content=data['content'],source=data['source'],status='published' if published else 'draft'));db.flush();db.add(CaseVersion(id=vid,case_id=cid,number=1,data=data))
  return cid,vid
 async def test_share_bookmark_discussion_adapt_provenance_and_withdraw(self):
  cid,vid=self.source();s=await self.call('POST','/community',{'kind':'case','sourceId':cid,'versionId':vid,'confirmed':True},201);original=copy.deepcopy(s['snapshot']);await self.login('t2');s=await self.call('PUT','/community/'+s['id']+'/bookmark',{'selected':True});self.assertTrue(s['bookmarked']);s=await self.call('PUT','/community/'+s['id']+'/bookmark',{'selected':False});self.assertFalse(s['bookmarked']);s=await self.call('POST','/community/'+s['id']+'/events',{'kind':'discussion','text':'保留共同加3的依据。'},201);eid=s['events'][-1]['id'];await self.call('POST','/community/'+s['id']+'/events/'+eid+'/withdraw',{});adapt=await self.call('POST','/community/'+s['id']+'/adapt',{'lessonId':self.fx['lesson']},201);self.assertEqual(adapt['sourceVersionId'],vid);self.assertEqual(adapt['sourceAuthor'],'原作者');await self.call('POST','/community/'+s['id']+'/adapt',{'lessonId':self.fx['lesson']},409);s=await self.call('POST','/community/'+s['id']+'/events',{'kind':'feedback','text':'尚未课堂试用，先记录备课想法。'},201);self.assertEqual(s['snapshot'],original);await self.login('t1');s=await self.call('GET','/community/'+s['id']);self.assertTrue(any(e['kind']=='adaptation' for e in s['events']));await self.call('POST','/community/'+s['id']+'/withdraw',{});await self.login('t2');await self.call('GET','/community/'+s['id'],status=404)
 async def test_no_unpublished_case_or_foreign_private_plan_share(self):
  cid,vid=self.source(False);await self.call('POST','/community',{'kind':'case','sourceId':cid,'versionId':vid,'confirmed':True},422);await self.call('POST','/community',{'kind':'plan','sourceId':'foreign','versionId':'private','confirmed':True},404);await self.login('s0');await self.call('GET','/community',status=403)
