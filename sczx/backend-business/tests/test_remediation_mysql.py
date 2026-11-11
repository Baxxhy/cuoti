import copy,os,secrets,subprocess,sys,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import httpx
from sqlalchemy import select
from sczx_business.database import engine,SessionLocal
from sczx_business.main import app
from sczx_business.models import WrongQuestion,RepairAttempt,StudentRecord,ModelJob,ModelRun,ClassMember
from sczx_business.remediation import validate
from sczx_business.model_jobs import execute
from test_teaching_mysql import fixture,create_accounts
@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class RemediationMySQLTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  assert engine.url.database.startswith('sczx_test_');subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True);cls.password=secrets.token_urlsafe(24);create_accounts(cls.password,'repair-')
 async def asyncSetUp(self):
  self.fx=fixture('r-'+uuid.uuid4().hex[:8],'repair-');self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test');await self.login('s0')
 async def asyncTearDown(self):await self.c.aclose()
 async def login(self,name):
  self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':'repair-'+name,'password':self.password});self.assertEqual(r.status_code,200)
 async def wrong(self,**kw):
  r=await self.c.post('/api/wrongs',json={'prompt':'3x=18','equation':'3x=18','answer':'5','requestKey':uuid.uuid4().hex,**kw});self.assertEqual(r.status_code,201,r.text);return r.json()
 async def job(self,w,mode='variant',**data):
  r=await self.c.post('/api/ai/jobs',json={'capability':'text','recordId':w['recordId'],'requestKey':uuid.uuid4().hex,'data':{'wrongId':w['id'],'mode':mode,**data}});self.assertEqual(r.status_code,201,r.text);return r.json()
 def succeed(self,j,equation='4x=20',expected='5'):
  with SessionLocal.begin() as db:
   row=db.get(ModelJob,j['id']);row.result=validate({'variant':{'prompt':'求解','equation':equation,'expected':expected,'rationale':'相同乘除结构，不同数值'},'mathClaims':[]},row.input);row.status='succeeded';row.active_hash=None
 async def test_independent_dedup_roles_and_refresh(self):
  key=uuid.uuid4().hex;w=await self.wrong(requestKey=key);self.assertIsNone(w['taskId']);self.assertEqual(w['source'],'manual');self.assertEqual((await self.wrong(requestKey=key))['id'],w['id'])
  await self.login('s1');self.assertEqual((await self.c.get('/api/wrongs/'+w['id'])).status_code,404)
  await self.login('t1');self.assertNotIn(w['id'],[x['id'] for x in (await self.c.get('/api/wrongs')).json()]);self.assertEqual((await self.c.get('/api/wrongs/'+w['id'])).status_code,404)
  await self.login('s0');self.assertEqual((await self.c.get('/api/wrongs/'+w['id'])).json()['answer'],'5')
 async def test_actual_dynamic_scoring_replay_help_and_foreign_job(self):
  w=await self.wrong();
  with SessionLocal.begin() as db:db.get(WrongQuestion,w['id']).details={**db.get(WrongQuestion,w['id']).details,'planJobId':'controlled-plan'}
  j=await self.job(w);self.succeed(j);body={'variantJobId':j['id'],'answer':'5','reason':'两边除以4','requestKey':uuid.uuid4().hex};r=await self.c.post('/api/wrongs/'+w['id']+'/attempts',json=body);self.assertEqual(r.status_code,201,r.text);a=r.json();self.assertEqual(a['verification']['status'],'verified_correct');self.assertEqual((await self.c.post('/api/wrongs/'+w['id']+'/attempts',json=body)).json()['id'],a['id'])
  other=await self.wrong();self.assertEqual((await self.c.post('/api/wrongs/'+other['id']+'/attempts',json=body)).status_code,422)
  j2=await self.job(w,phase='retest');self.succeed(j2,'5x=45','9');await self.job(w,'guidance',variantJobId=j2['id'],strategy='hint',prompt='我不知道怎么解')
  r=await self.c.post('/api/wrongs/'+w['id']+'/attempts',json={'variantJobId':j2['id'],'answer':'9','requestKey':uuid.uuid4().hex});self.assertTrue(r.json()['details']['helped']);self.assertEqual((await self.c.get('/api/wrongs/'+w['id'])).json()['status'],'retest_failed')
 async def test_legacy_snapshot_and_removed_course(self):
  task=self.fx['tasks'][0]
  with SessionLocal.begin() as db:
   rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==task,StudentRecord.student_id=='repair-s0'));wid='wrong-'+uuid.uuid4().hex;db.add(WrongQuestion(id=wid,record_id=rec.id,prompt='x-3=5',answer='2'));db.flush();rid='repair-'+uuid.uuid4().hex;db.add(RepairAttempt(id=rid,wrong_id=wid,answer='7',correct=True,verification={'status':'verified','correct':True}));record=rec.id
  w=(await self.c.get('/api/wrongs/'+wid)).json();self.assertEqual(w['status'],'pending');self.assertEqual(w['repairs'][0]['details']['version'],'legacy_fixed')
  await self.login('t2');self.assertEqual((await self.c.get('/api/wrongs/'+wid)).status_code,404)
  await self.login('t1');self.assertEqual((await self.c.get('/api/wrongs/'+wid)).status_code,200)
  with SessionLocal.begin() as db:db.delete(db.get(ClassMember,(self.fx['classes'][0],'repair-s0')))
  await self.login('s0');self.assertEqual((await self.c.get('/api/wrongs/'+wid)).status_code,200);self.assertEqual((await self.c.put('/api/wrongs/'+wid,json={'cause':'计算错误'})).status_code,403)
  with SessionLocal() as db:self.assertTrue(db.get(RepairAttempt,rid).correct)
 async def test_image_requires_confirmed_owned_ocr_and_crop(self):
  # Store actual PNG through the existing upload service, not a Data URL.
  import base64
  raw=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aE0sAAAAASUVORK5CYII=')
  f=(await self.c.post('/api/files',files={'file':('test.png',raw,'image/png')})).json()
  r=await self.c.post('/api/wrongs',json={'prompt':'x-3=5','fileId':f['id'],'requestKey':uuid.uuid4().hex});self.assertEqual(r.status_code,422)
  j=(await self.c.post('/api/ai/jobs',json={'capability':'ocr','fileId':f['id'],'requestKey':uuid.uuid4().hex,'data':{'wrongCapture':True}})).json()
  with SessionLocal.begin() as db:row=db.get(ModelJob,j['id']);row.status='succeeded';row.active_hash=None;row.result={'text':'x+3=5','equation':'x+3=5','studentAnswer':'','uncertainties':[]}
  w=await self.wrong(prompt='x-3=5',equation='x-3=5',fileId=f['id'],ocrJobId=j['id'],confirmed=True)
  await self.login('s0');self.assertEqual((await self.c.get('/api/wrongs/'+w['id'])).json()['details']['confirmedText'],'x-3=5');self.assertEqual((await self.c.get(w['image'])).content,raw)
  await self.login('t1');self.assertEqual((await self.c.get(w['image'])).status_code,403)
 async def test_course_unknown_answer_teacher_review_preserves_program_result(self):
  with SessionLocal.begin() as db:
   rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.fx['tasks'][0],StudentRecord.student_id=='repair-s0'));wid='wrong-'+uuid.uuid4().hex;db.add(WrongQuestion(id=wid,record_id=rec.id,owner_id='repair-s0',prompt='3x=18',answer='15'))
  w=(await self.c.get('/api/wrongs/'+wid)).json();j=await self.job(w);self.succeed(j)
  a=(await self.c.post('/api/wrongs/'+wid+'/attempts',json={'variantJobId':j['id'],'answer':'条件尚未确定','requestKey':uuid.uuid4().hex})).json();self.assertEqual(a['verification']['status'],'unverified');self.assertFalse(a['correct'])
  await self.login('t1');r=await self.c.post('/api/wrongs/'+wid+'/review',json={'attemptId':a['id'],'correct':False,'note':'请补充计算过程'});self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['verification']['status'],'unverified');self.assertFalse(r.json()['details']['teacherReview']['correct'])
 async def test_course_wrong_retains_uploaded_question_source(self):
  f=(await self.c.post('/api/files',files={'file':('course.png',b'course-image-fixture','image/png')})).json();task=self.fx['tasks'][0]
  from sczx_business.models import HelpRecord
  with SessionLocal.begin() as db:
   rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==task,StudentRecord.student_id=='repair-s0'));db.add(HelpRecord(id='help-'+uuid.uuid4().hex,record_id=rec.id,question=0,kind='题图',message='',file_id=f['id']))
  r=await self.c.post('/api/records/'+task+'/attempts',json={'question':0,'answer':'999'});self.assertEqual(r.status_code,201)
  wrongs=(await self.c.get('/api/wrongs')).json();w=next(x for x in wrongs if x['attemptId']==r.json()['id']);self.assertEqual(w['image'],f['url']);self.assertEqual(w['source'],'course')
  await self.login('t1');self.assertEqual((await self.c.get(w['image'])).status_code,200)

 async def test_concurrent_repair_replay_returns_one_immutable_attempt(self):
  import asyncio
  w=await self.wrong();j=await self.job(w);self.succeed(j)
  body={'variantJobId':j['id'],'answer':'5','requestKey':uuid.uuid4().hex}
  responses=await asyncio.gather(*[self.c.post('/api/wrongs/'+w['id']+'/attempts',json=body) for _ in range(2)])
  self.assertTrue(all(r.status_code==201 for r in responses),[r.text for r in responses]);self.assertEqual(responses[0].json()['id'],responses[1].json()['id'])
  rows=(await self.c.get('/api/wrongs/'+w['id'])).json()['repairs'];self.assertEqual(len(rows),1)

 async def test_variant_guidance_rebuilds_current_equation_and_does_not_send_expected_answer(self):
  import json
  from sczx_business.tutoring import model_input,validate_result
  from sczx_business.model_provider import ModelError
  w=await self.wrong(prompt='x+7=12',equation='x+7=12',answer='99',reason='原题曾经误算')
  variant=await self.job(w);self.succeed(variant,'x+5=13','8')
  guidance=await self.job(w,'guidance',variantJobId=variant['id'],strategy='hint',context={'question':{'equation':'x+7=12','expected':'99'}},originalAnswer='伪造新题答案',originalReason='伪造新题理由')
  with SessionLocal() as db:data=copy.deepcopy(db.get(ModelJob,guidance['id']).input)
  self.assertEqual(data['variantJobId'],variant['id']);self.assertEqual(data['context']['question']['equation'],'x+5=13');self.assertEqual(data['_validation']['equation'],'x+5=13')
  self.assertEqual(data['context']['originalQuestion'],{'prompt':'x+7=12','equation':'x+7=12'})
  self.assertEqual(data['context']['originalAnswer'],'');self.assertEqual(data['context']['originalReason'],'')
  public=model_input(data);self.assertNotIn('expected',json.dumps(public));self.assertNotIn('伪造',json.dumps(public,ensure_ascii=False));self.assertNotIn('99',json.dumps(public))
  # Leaking this variant's answer must be checked against x+5=13, not the old x+7=12.
  leaked={'title':'新题指导','hint':'x=8','steps':['两边进行共同运算'],'question':'现在知道怎么做了吗？','strategy':'hint','representation':'question','usedCaseVersionIds':[],'mathClaims':[]}
  with self.assertRaises(ModelError):validate_result(leaked,data)

 async def test_variant_guidance_rejects_foreign_wrong_unready_unverified_and_wrong_capability(self):
  w=await self.wrong(prompt='x+7=12',equation='x+7=12');variant=await self.job(w);self.succeed(variant,'x+5=13','8')
  other=await self.wrong();other_variant=await self.job(other);self.succeed(other_variant)
  async def refused(jid):
   response=await self.c.post('/api/ai/jobs',json={'capability':'text','recordId':w['recordId'],'requestKey':uuid.uuid4().hex,'data':{'wrongId':w['id'],'mode':'guidance','variantJobId':jid,'strategy':'hint'}})
   self.assertEqual(response.status_code,422,response.text)
  await refused(other_variant['id']);await refused('missing-variant')
  with SessionLocal() as db:original=copy.deepcopy(db.get(ModelJob,variant['id']).result)
  for changed in ['foreign','running','unverified','capability','mode']:
   with self.subTest(changed=changed):
    with SessionLocal.begin() as db:
     row=db.get(ModelJob,variant['id']);row.owner_id='repair-s1' if changed=='foreign' else 'repair-s0';row.status='running' if changed=='running' else 'succeeded';row.capability='ocr' if changed=='capability' else 'text';row.input={**row.input,'mode':'analysis' if changed=='mode' else 'variant'};row.result={**original,'variantVerification':{'status':'unverified'}} if changed=='unverified' else copy.deepcopy(original)
    await refused(variant['id'])

 async def test_guidance_history_keeps_original_question_and_each_variant_separate(self):
  w=await self.wrong();first=await self.job(w);self.succeed(first)
  second=await self.job(w);self.succeed(second,'5x=45','9')
  original=await self.job(w,'guidance',prompt='原题追问')
  original_analysis=await self.job(w,'analysis')
  first_guidance=await self.job(w,'guidance',variantJobId=first['id'],prompt='第一道新题追问')
  for j in [original,original_analysis,first_guidance]:
   with SessionLocal.begin() as db:
    row=db.get(ModelJob,j['id']);row.status='succeeded';row.active_hash=None;row.result={'hint':'请比较两边的共同运算','question':'下一步是什么？','representation':'question'}
  same=await self.job(w,'guidance',variantJobId=first['id'],parentJobId=first_guidance['id'],prompt='同一题继续追问')
  with SessionLocal() as db:
   data=db.get(ModelJob,same['id']).input;self.assertEqual(len(data['history']),1);self.assertEqual(data['history'][0]['student'],'第一道新题追问')
  for mode,variant_id,parent_id in [('guidance',first['id'],original['id']),('guidance',first['id'],original_analysis['id']),('guidance',second['id'],first_guidance['id']),('guidance',None,first_guidance['id']),('analysis',None,first_guidance['id']),('variant',first['id'],None),('analysis',first['id'],None)]:
   with self.subTest(mode=mode,variant=variant_id,parent=parent_id):
    response=await self.c.post('/api/ai/jobs',json={'capability':'text','recordId':w['recordId'],'requestKey':uuid.uuid4().hex,'data':{'wrongId':w['id'],'mode':mode,'variantJobId':variant_id,'parentJobId':parent_id,'prompt':'不能混合上下文'}})
    self.assertEqual(response.status_code,422,response.text)
  # Legacy original-question guidance still continues its own original thread.
  original_next=await self.job(w,'guidance',parentJobId=original['id'],prompt='原题继续追问')
  with SessionLocal() as db:
   data=db.get(ModelJob,original_next['id']).input;self.assertEqual(data['context']['question']['equation'],'3x=18');self.assertEqual(data['history'][0]['student'],'原题追问')

 async def test_guidance_marks_only_its_exact_variant_as_helped(self):
  w=await self.wrong();first=await self.job(w);self.succeed(first)
  second=await self.job(w);self.succeed(second,'5x=45','9')
  await self.job(w,'guidance',variantJobId=first['id'],prompt='第一道新题求助')
  await self.job(w,'guidance',prompt='原题求助')
  plain=await self.c.post('/api/wrongs/'+w['id']+'/attempts',json={'variantJobId':second['id'],'answer':'9','helped':False,'requestKey':uuid.uuid4().hex})
  self.assertEqual(plain.status_code,201,plain.text);self.assertFalse(plain.json()['details']['helped'])
  helped=await self.c.post('/api/wrongs/'+w['id']+'/attempts',json={'variantJobId':first['id'],'answer':'5','helped':False,'requestKey':uuid.uuid4().hex})
  self.assertEqual(helped.status_code,201,helped.text);self.assertTrue(helped.json()['details']['helped'])

 async def test_legacy_unscoped_help_remains_conservatively_helped(self):
  w=await self.wrong();variant=await self.job(w);self.succeed(variant)
  legacy=await self.job(w,'guidance',prompt='旧版本求助')
  with SessionLocal.begin() as db:
   row=db.get(ModelJob,legacy['id']);value=copy.deepcopy(row.input);value.pop('variantJobId',None);row.input=value
  answer=await self.c.post('/api/wrongs/'+w['id']+'/attempts',json={'variantJobId':variant['id'],'answer':'5','requestKey':uuid.uuid4().hex})
  self.assertEqual(answer.status_code,201,answer.text);self.assertTrue(answer.json()['details']['helped'])
