"""Real isolated MySQL: non-equation course publication and cross-subject teacher/student roundtrip."""
import copy,os,secrets,subprocess,sys,unittest,uuid
from pathlib import Path
import httpx
from sqlalchemy import select
from sczx_business.main import app
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account,KnowledgePoint,ModelJob,StudentRecord,WrongQuestion
from sczx_business.security import hash_password
from test_teaching_mysql import create_accounts

@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class MultiSubjectMySQLTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  assert engine.url.database.startswith('sczx_test_');subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True);cls.prefix='subjects-'+uuid.uuid4().hex[:6]+'-';cls.password=secrets.token_urlsafe(20);create_accounts(cls.password,cls.prefix)
  with SessionLocal.begin() as db:db.add(Account(id=cls.prefix+'admin',username=cls.prefix+'admin',display_name='全科验收管理员',role='admin',password_hash=hash_password(cls.password)))
 async def asyncSetUp(self):self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test')
 async def asyncTearDown(self):await self.c.aclose()
 async def login(self,role):
  self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':self.prefix+role,'password':self.password});self.assertEqual(r.status_code,200,r.text)
 async def call(self,method,path,body=None,status=200):
  r=await self.c.request(method,path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
 async def lesson(self,subject,q,grade='高一'):
  await self.login('admin');course=await self.call('POST','/api/curriculum/courses',{'title':subject+'验收课程','grade':grade,'subject':subject},201);unit=await self.call('POST','/api/curriculum/units',{'courseId':course['id'],'title':'自编单元'},201);lesson=await self.call('POST','/api/curriculum/lessons',{'unitId':unit['id'],'title':'材料与表达'},201);self.assertEqual(lesson['draft']['subject'],subject);self.assertEqual(lesson['draft']['grade'],grade)
  data=lesson['draft'];data.update(goal='依据材料准确表达',source='项目自编跨学科工程验收，不作为真实教材',blocks=[{'id':'read','type':'explanation','title':'阅读材料','content':'本课为跨学科自编验证内容。','required':True},{'id':'check','type':'check','title':'独立作答','content':'根据题目独立作答。','required':True,'questionIds':['q1']}],questions=[{'id':'q1','kind':'check',**q}]);await self.call('PUT','/api/curriculum/lessons/'+lesson['id'],{'data':data});await self.call('POST','/api/curriculum/lessons/'+lesson['id']+'/review',{});await self.call('POST','/api/curriculum/lessons/'+lesson['id']+'/publish',{});return lesson['id'],unit['id'],data
 async def test_subjective_and_objective_tasks_keep_subject_context_and_feedback(self):
  for subject,q,answer,expected in [('语文',{'prompt':'用材料支持你的看法','answer':'陈述观点并引用材料','responseType':'reading','gradingMode':'manual'},'我引用材料中的描述作为依据。','unverified'),('英语',{'prompt':'Choose the plural of book.','answer':'B','responseType':'single_choice','gradingMode':'exact','options':[{'id':'A','text':'book'},{'id':'B','text':'books'}]},'B','verified')]:
   ident,unit,data=await self.lesson(subject,q);await self.login('t1');room=await self.call('POST','/api/classrooms',{'name':subject+'验收班','grade':'高一','subject':subject},201);await self.call('POST','/api/classrooms/'+room['id']+'/members',{'studentId':self.prefix+'s0'},201)
   platform=await self.call('GET','/api/platform?lessonId='+ident);draft=platform['lessonDraft'];self.assertEqual(draft['lessonSnapshot']['subject'],subject)
   published=await self.call('POST','/api/tasks/publish',{'classroomId':room['id'],'lessonId':ident,'lessonDraft':draft,'idempotencyKey':uuid.uuid4().hex},201);tid=published['taskId'];await self.login('s0');platform=await self.call('GET','/api/platform?lessonId='+ident);task=next(t for t in platform['tasks'] if t['id']==tid);self.assertEqual(task['snapshot']['lessonSnapshot']['subject'],subject);self.assertNotIn('answer',task['questions'][0]);self.assertEqual(task['questions'][0].get('options',[]),q.get('options',[]))
   hinted=await self.call('POST','/api/curriculum/tasks/'+tid+'/questions/0/hint',{});self.assertNotIn('等式两边',hinted['hint'])
   result=await self.call('POST','/api/records/'+tid+'/attempts',{'question':0,'answer':answer,'reason':'依据题目作答'},201);self.assertEqual(result['verification']['status'],expected)
   platform=await self.call('GET','/api/platform?lessonId='+ident);platform['records'][tid]['drafts'].setdefault('blocks',{})['read']={'completed':True};await self.call('PUT','/api/platform',{'data':platform});await self.call('POST','/api/records/'+tid+'/submit',{})
   with SessionLocal() as db:record=db.scalar(select(StudentRecord).where(StudentRecord.task_id==tid));rid=record.id;self.assertFalse(db.scalar(select(WrongQuestion.id).where(WrongQuestion.record_id==rid)))
   await self.login('t1');await self.call('PUT','/api/records/'+rid+'/feedback',{'feedback':'已阅读作答，继续结合材料说明依据。'});await self.login('s0');platform=await self.call('GET','/api/platform?lessonId='+ident);self.assertIn('已阅读',platform['records'][tid]['feedback'])
 async def test_every_registered_subject_accepts_non_equation_content(self):
  from sczx_business.education import catalog
  for item in catalog()['subjects']:
   ident,unit,data=await self.lesson(item['value'],{'prompt':'说明本课学习过程与依据','answer':'依据教师给出的评价要点说明','responseType':'short_answer','gradingMode':'manual'},'八年级' if 'junior' in item['stages'] else '高一');self.assertTrue(ident)
