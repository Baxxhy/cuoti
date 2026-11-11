import os,sys,subprocess,uuid,secrets,unittest,copy
from pathlib import Path
import httpx
from sqlalchemy import select
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account,Course,CourseUnit,Lesson,LessonContent,LessonVersion,StudentRecord,ClassMember,LearningTask
from sczx_business.main import app
from test_teaching_mysql import create_accounts,fixture
from sczx_business.security import hash_password
@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class UnitMySQLTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  assert engine.url.database.startswith('sczx_test_');subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True);cls.password=secrets.token_urlsafe(24);create_accounts(cls.password,'unit-test-')
  with SessionLocal.begin() as db:db.add(Account(id='unit-test-admin',username='unit-test-admin',display_name='单元测试管理员',role='admin',password_hash=hash_password(cls.password)))
 async def asyncSetUp(self):
  self.fx=fixture('u-'+uuid.uuid4().hex[:6],'unit-test-');self.course=self.fx['lesson'].replace('-lesson','-course');self.unit=self.course+'-unit';self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test')
  with SessionLocal.begin() as db:db.add(CourseUnit(id=self.unit,course_id=self.course,title='单元验收',position=1));db.flush();db.get(Lesson,self.fx['lesson']).unit_id=self.unit
  await self.login('admin')
 async def asyncTearDown(self):await self.c.aclose()
 async def login(self,who):
  self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':'unit-test-'+who,'password':self.password});self.assertEqual(r.status_code,200,r.text)
 async def call(self,method,path,body=None,status=200):
  r=await self.c.request(method,'/api'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
 async def test_known_conditions_block_review_and_publication(self):
  data=copy.deepcopy(self.fx['data']);data['blocks'][0]['content']='两边同时加上、减去、乘上或除以同一个数。';await self.call('PUT','/curriculum/lessons/'+self.fx['lesson'],{'data':data});await self.call('POST','/curriculum/lessons/'+self.fx['lesson']+'/review',status=422);await self.call('POST','/curriculum/lessons/'+self.fx['lesson']+'/publish',status=422)
 async def test_review_is_recorded_and_old_version_immutable(self):
  old=await self.call('GET','/curriculum/lessons/'+self.fx['lesson']+'?versionId='+self.fx['data'].get('versionId','no-version'),status=404)
  data=copy.deepcopy(self.fx['data']);await self.call('PUT','/curriculum/lessons/'+self.fx['lesson'],{'data':data});await self.call('POST','/curriculum/lessons/'+self.fx['lesson']+'/publish',status=422);await self.call('POST','/curriculum/lessons/'+self.fx['lesson']+'/review');out=await self.call('POST','/curriculum/lessons/'+self.fx['lesson']+'/publish');self.assertEqual(out['published']['reviewRecord']['actorId'],'unit-test-admin');self.assertEqual(len(out['versions']),2)
  with SessionLocal() as db:self.assertNotIn('reviewRecord',db.scalar(select(LessonVersion).where(LessonVersion.lesson_id==self.fx['lesson'],LessonVersion.number==1)).data)
 async def test_progress_uses_real_latest_assignment_and_preserves_readonly(self):
  await self.login('s0');r=await self.call('GET','/units/'+self.unit+'/progress');self.assertEqual(r['total'],1);self.assertEqual(r['assigned'],1);tid=r['lessons'][0]['taskId']
  with SessionLocal.begin() as db:db.scalar(select(StudentRecord).where(StudentRecord.task_id==tid,StudentRecord.student_id=='unit-test-s0')).completed=True
  self.assertEqual((await self.call('GET','/units/'+self.unit+'/progress'))['completed'],1)
  with SessionLocal.begin() as db:db.delete(db.get(ClassMember,(self.fx['classes'][0],'unit-test-s0')))
  r=await self.call('GET','/units/'+self.unit+'/progress');self.assertTrue(r['lessons'][0]['readOnly']);self.assertEqual(r['completed'],1)
 async def test_order_validates_real_ids_and_repeated_or_invalid_values(self):
  for order in [[self.fx['lesson'],self.fx['lesson']],['absent'],[{}]]:await self.call('PUT','/curriculum/courses/'+self.course,{'title':'单元','metadata':{'unitPlans':{self.unit:order}}},422)
  await self.call('PUT','/curriculum/courses/'+self.course,{'title':'单元','metadata':{'unitPlans':{self.unit:[self.fx['lesson']]}}});await self.login('s0');r=await self.call('GET','/units/'+self.unit+'/progress');self.assertEqual(r['lessons'][0]['lessonId'],self.fx['lesson'])
 async def test_exam_live_and_group_records_do_not_replace_curriculum_progress(self):
  from datetime import datetime,timedelta
  await self.login('s0');original=(await self.call('GET','/units/'+self.unit+'/progress'))['lessons'][0]['taskId']
  with SessionLocal.begin() as db:
   parent=db.get(LearningTask,original)
   for index,source in enumerate(['exam','live-class','group']):
    ident='derived-'+uuid.uuid4().hex
    db.add(LearningTask(id=ident,classroom_id=parent.classroom_id,teacher_id=parent.teacher_id,lesson_id=parent.lesson_id,title=source,snapshot={},questions=[],due_date='',source=source,published_at=datetime.utcnow()+timedelta(minutes=index+1)));db.flush()
    db.add(StudentRecord(id='rec-'+uuid.uuid4().hex,task_id=ident,student_id='unit-test-s0',completed=source!='group'))
  result=await self.call('GET','/units/'+self.unit+'/progress');self.assertEqual(result['lessons'][0]['taskId'],original);self.assertEqual(result['completed'],0)
  with SessionLocal.begin() as db:db.scalar(select(StudentRecord).where(StudentRecord.task_id==original,StudentRecord.student_id=='unit-test-s0')).completed=True
  self.assertEqual((await self.call('GET','/units/'+self.unit+'/progress'))['completed'],1)
 async def test_other_student_and_teacher_do_not_gain_records(self):
  await self.login('s10');r=await self.call('GET','/units/'+self.unit+'/progress');self.assertEqual(r['assigned'],0);self.assertTrue(all(not x['taskId'] for x in r['lessons']));await self.login('t2');await self.call('GET','/units/'+self.unit+'/progress',status=404)
