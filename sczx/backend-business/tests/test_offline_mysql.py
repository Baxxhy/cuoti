import os,sys,uuid,json,secrets,subprocess,unittest,asyncio
from pathlib import Path
from datetime import timedelta
import httpx
from sqlalchemy import select,func
from sczx_business.main import app
from sczx_business.database import engine,SessionLocal
from sczx_business.models import LearningTask,StudentRecord,ClassMember,HelpRecord,Attempt
from sczx_business.offline_models import OfflineOperation
from sczx_business.teaching import now,iso
from test_teaching_mysql import create_accounts,fixture
@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class OfflineTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  assert engine.url.database.startswith('sczx_test_');subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True);cls.password=secrets.token_urlsafe(24);create_accounts(cls.password,'offline-test-')
 async def asyncSetUp(self):
  self.fx=fixture('off-'+uuid.uuid4().hex[:6],'offline-test-');self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test');await self.login('s0');self.task=self.fx['tasks'][1];self.pkg=await self.call('GET','/offline/packages/'+self.task)
 async def asyncTearDown(self):await self.c.aclose()
 async def login(self,name):
  self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':'offline-test-'+name,'password':self.password});self.assertEqual(r.status_code,200)
 async def call(self,method,path,body=None,status=200):
  r=await self.c.request(method,'/api'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
 def body(self):return {'operationId':str(uuid.uuid4()),'userId':'offline-test-s0','taskId':self.task,'questionId':self.pkg['questions'][0]['id'],'versionId':self.pkg['versionId'],'baseRevision':self.pkg['baseRevision'],'modifiedAt':'2099-01-01T00:00:00Z','answer':'8','reason':'两边同时加3','helped':False}
 async def test_package_allowlist_no_answers_other_students_or_private_notes(self):
  with SessionLocal.begin() as db:
   t=db.get(LearningTask,self.task);t.snapshot={**t.snapshot,'teacherNotes':'SECRET-TEACHER','gradingRules':'SECRET-RUBRIC'};qs=list(t.questions);qs[0]={**qs[0],'rubric':'SECRET-ANSWER','solution':'SECRET-SOLUTION'};t.questions=qs
  p=await self.call('GET','/offline/packages/'+self.task);raw=json.dumps(p);self.assertNotIn('SECRET',raw);self.assertNotIn('studentName',raw);self.assertNotIn('answer',p['questions'][0]);self.assertEqual(p['userId'],'offline-test-s0');self.assertEqual(len(p['versionId']),64)
 async def test_draft_sync_does_not_submit_grade_or_change_teacher_feedback(self):
  body=self.body();r=await self.call('POST','/offline/sync',body);self.assertFalse(r['formalSubmission']);p=await self.call('GET','/offline/packages/'+self.task);self.assertEqual(p['drafts']['questions'][body['questionId']]['answer'],'8');self.assertNotEqual(p['baseRevision'],body['baseRevision'])
  with SessionLocal() as db:
   rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='offline-test-s0'));self.assertFalse(rec.completed);self.assertIsNone(rec.submitted_at);self.assertEqual(db.scalar(select(func.count()).select_from(Attempt).where(Attempt.record_id==rec.id)),0)
 async def test_same_operation_id_retry_and_changed_payload(self):
  b=self.body();r=await self.call('POST','/offline/sync',b);self.assertEqual(await self.call('POST','/offline/sync',b),r);await self.call('POST','/offline/sync',{**b,'answer':'999'},409)
 async def test_concurrent_same_operation_only_one_write(self):
  b=self.body();rs=await asyncio.gather(self.c.post('/api/offline/sync',json=b),self.c.post('/api/offline/sync',json=b));self.assertEqual([r.status_code for r in rs],[200,200]);self.assertEqual(rs[0].json(),rs[1].json())
  with SessionLocal() as db:self.assertEqual(db.scalar(select(func.count()).select_from(OfflineOperation).where(OfflineOperation.owner_id==b['userId'],OfflineOperation.operation_id==b['operationId'])),1)
 async def test_server_edit_conflicts_and_explicit_new_revision_can_retry(self):
  with SessionLocal.begin() as db:
   r=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='offline-test-s0'));r.drafts={'questions':{self.pkg['questions'][0]['id']:{'answer':'SERVER-NEW','reason':'服务器新解释'}}}
  b=self.body();err=await self.call('POST','/offline/sync',b,409);d=err['detail'];self.assertTrue(d['allowRetry']);self.assertEqual(d['serverDrafts']['questions'][b['questionId']]['answer'],'SERVER-NEW');await self.call('POST','/offline/sync',{**b,'operationId':str(uuid.uuid4()),'baseRevision':d['serverRevision']})
 async def test_withdrawn_task_rejects_sync_and_online_write(self):
  b=self.body();await self.login('t1');await self.call('POST','/offline/tasks/'+self.task+'/withdraw',{});await self.login('s0');await self.call('POST','/offline/sync',b,409);await self.call('POST','/records/'+self.task+'/attempts',{'question':0,'answer':'8','reason':'共同加3'},409)
 async def test_removed_member_rejects_sync(self):
  with SessionLocal.begin() as db:db.delete(db.get(ClassMember,(self.fx['classes'][0],'offline-test-s0')))
  await self.call('POST','/offline/sync',self.body(),409)
 async def test_completed_record_immutable(self):
  with SessionLocal.begin() as db:
   r=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='offline-test-s0'));r.completed=True;r.submitted_at=now()
  await self.call('POST','/offline/sync',self.body(),409)
 async def test_server_deadline_not_local_clock(self):
  with SessionLocal.begin() as db:db.get(LearningTask,self.task).due_date=iso(now()-timedelta(hours=1))
  await self.call('POST','/offline/sync',self.body(),409)
 async def test_changed_content_version_rejects(self):
  with SessionLocal.begin() as db:
   t=db.get(LearningTask,self.task);t.snapshot={**t.snapshot,'goal':'新固定版本'}
  err=await self.call('POST','/offline/sync',self.body(),409);self.assertEqual(err['detail']['code'],'version')
 async def test_cross_identity_and_unknown_question_rejects(self):
  b=self.body();await self.login('s1');await self.call('POST','/offline/sync',b,403);await self.login('s0');await self.call('POST','/offline/sync',{**b,'questionId':'other-task-question'},422);await self.login('t1');await self.call('GET','/offline/tasks',status=403)
 async def test_help_cannot_be_reset_and_only_allowed_fields(self):
  with SessionLocal.begin() as db:
   rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='offline-test-s0'));db.add(HelpRecord(id='help-'+uuid.uuid4().hex,record_id=rec.id,question=0,kind='提示',message='先共同加3'))
  b=self.body();await self.call('POST','/offline/sync',b);p=await self.call('GET','/offline/packages/'+self.task);self.assertTrue(p['drafts']['questions'][b['questionId']]['helped']);await self.call('POST','/offline/sync',{**b,'completed':True},422)
 async def test_position_scoped_and_other_records_unchanged(self):
  b=self.body();b.update(questionId='@position',position=self.pkg['blocks'][0]['id']);await self.call('POST','/offline/sync',b);p=await self.call('GET','/offline/packages/'+self.task);self.assertEqual(p['drafts']['lessonPosition']['blockId'],b['position']);self.assertNotIn(b['questionId'],p['drafts']['questions'])
 async def test_exam_and_live_class_never_download(self):
  with SessionLocal.begin() as db:db.get(LearningTask,self.task).source='exam'
  await self.call('GET','/offline/packages/'+self.task,status=403);await self.call('POST','/offline/sync',self.body(),409)
 async def test_assigned_snapshot_image_access_without_publishing_private_file(self):
  import base64
  await self.login('t1');image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aA1kAAAAASUVORK5CYII=');r=await self.c.post('/api/files',files={'file':('test.png',image,'image/png')});self.assertEqual(r.status_code,201);url=r.json()['url']
  with SessionLocal.begin() as db:
   import copy
   t=db.get(LearningTask,self.task);snap=copy.deepcopy(t.snapshot);snap['blocks'][0]['imageUrl']=url;t.snapshot=snap
  await self.login('s0');r=await self.c.get(url);self.assertEqual(r.status_code,200);self.assertEqual(r.content,image);await self.login('s6');self.assertEqual((await self.c.get(url)).status_code,403)
