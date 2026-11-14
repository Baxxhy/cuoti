"""Real MySQL library import, idempotence, permissions and 57 exact-scope retrieval probes."""
import copy,json,os,secrets,subprocess,sys,unittest,uuid
from pathlib import Path
import httpx
from sqlalchemy import select,func
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account,TeachingCase,CaseVersion,CaseDraftContent
from sczx_business.security import hash_password
from sczx_business.curated_resources import import_resources,load_bundle,coverage
from sczx_business.retrieval import retrieve,published_documents,knowledge_documents
from sczx_business.experience_policy import diagnose,match_experiences
from sczx_business.main import app

@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class CuratedMySQLTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  assert engine.url.database.startswith('sczx_test_')
  subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True)
  cls.prefix='cur'+uuid.uuid4().hex[:6];cls.password=secrets.token_urlsafe(24)
  with SessionLocal.begin() as db:
   for suffix,role in [('a','admin'),('t','teacher'),('s','student')]:db.add(Account(id=cls.prefix+suffix,username=cls.prefix+suffix,display_name='资源工程验收'+role,role=role,password_hash=hash_password(cls.password)))
   db.flush();cls.imported=import_resources(db,cls.prefix+'a',apply=True)
 async def asyncSetUp(self):self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test')
 async def asyncTearDown(self):await self.c.aclose()
 async def login(self,suffix):
  self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':self.prefix+suffix,'password':self.password});self.assertEqual(r.status_code,200)
 async def test_coverage_and_existing_role_permissions(self):
  await self.login('a');r=await self.c.get('/api/library/experience-coverage');self.assertEqual(r.status_code,200);self.assertEqual(len(r.json()['subjects']),19);self.assertTrue(all(x['publishedSummaries']==3 for x in r.json()['subjects']))
  for role in ['s','t']:
   await self.login(role);self.assertEqual((await self.c.get('/api/library/experience-coverage')).status_code,403)
 async def test_idempotence_preview_and_teacher_edit_are_preserved(self):
  row=load_bundle()[0]['entries'][0]
  with SessionLocal.begin() as db:
   version=db.get(CaseVersion,'resver-'+row['id'][4:]);before=copy.deepcopy(version.data)
   if not db.get(CaseDraftContent,row['id']):db.add(CaseDraftContent(case_id=row['id'],data={**copy.deepcopy(before),'title':'教师未发布的个性修改'},reviewed=False))
   preview=import_resources(db,self.prefix+'a',apply=False);again=import_resources(db,self.prefix+'a',apply=True)
   self.assertEqual(len(preview['created']),0);self.assertEqual(len(again['skipped']),57);self.assertEqual(db.get(CaseDraftContent,row['id']).data['title'],'教师未发布的个性修改');self.assertEqual(db.get(CaseVersion,version.id).data,before)
 async def test_all_57_match_only_their_reviewed_subject_grade_and_knowledge(self):
  results=[]
  with SessionLocal() as db:
   docs=published_documents(db);points=knowledge_documents(db)
   for row in load_bundle()[0]['entries']:
    query=row['experience']['difficulty'];spec={'query':query,'filters':{'subject':row['subject'],'grade':row['grade'],'knowledgeIds':[row['knowledgeId']]},'limit':8}
    found=retrieve(spec,docs,points);decision=match_experiences(found['items'],diagnose(row['subject'],query),row['subject'],row['grade'],[row['knowledgeId']]);self.assertEqual([x['id'] for x in decision['selected']],[row['id']])
    negatives=[]
    for subject,grade,kp in [('英语' if row['subject']!='英语' else '数学',row['grade'],row['knowledgeId']),(row['subject'],'高三' if row['grade']!='高三' else '七年级',row['knowledgeId']),(row['subject'],row['grade'],next(x['knowledgeId'] for x in load_bundle()[0]['entries'] if x['subject']==row['subject'] and x['knowledgeId']!=row['knowledgeId']))]:
     bad=match_experiences(found['items'],diagnose(subject,query),subject,grade,[kp]);self.assertTrue(bad['fallback']);negatives.append(not bad['selected'])
    results.append({'id':row['id'],'subject':row['subject'],'selected':decision['selected'],'negativeProbesPassed':negatives})
   counts=coverage(db)
  if os.getenv('SCZX_RESOURCE_EVIDENCE'):Path(os.environ['SCZX_RESOURCE_EVIDENCE']).write_text(json.dumps({'import':self.imported,'coverage':counts,'retrievalProbes':results,'successes':len(results),'total':57,'wrongMatches':0,'negativeTotal':171},ensure_ascii=False,indent=2))
 async def test_summary_is_downloadable_and_never_pretends_to_be_original_pdf(self):
  row=load_bundle()[0]['entries'][0];await self.login('s')
  r=await self.c.get('/api/files/resfile-'+row['id'][4:]);self.assertEqual(r.status_code,200,r.text);self.assertIn('非来源原文',r.text);self.assertNotEqual(r.content[:4],b'%PDF')
  unit=(await self.c.get('/api/library/units/resunit-'+row['id'][4:])).json();self.assertTrue(unit['metadata']['curatedSummary']);self.assertFalse(unit['metadata']['rights']['originalRedistributionApproved'])

 async def test_standalone_wrong_guidance_uses_reviewed_english_resource_and_actual_answer(self):
  row=next(r for r in load_bundle()[0]['entries'] if r['subject']=='英语' and r['topic']=='一般过去时')
  await self.login('s')
  wrong=await self.c.post('/api/wrongs',json={'prompt':'I goed to school yesterday. 请检查时态。','answer':'I goed to school yesterday.','reason':'以为所有过去式都加ed','subject':row['subject'],'grade':row['grade'],'knowledgeIds':[row['knowledgeId']],'requestKey':uuid.uuid4().hex})
  self.assertEqual(wrong.status_code,201,wrong.text)
  job=await self.c.post('/api/ai/jobs',json={'capability':'text','requestKey':uuid.uuid4().hex,'data':{'wrongId':wrong.json()['id'],'mode':'guidance','strategy':'hint','prompt':row['experience']['difficulty']}})
  self.assertEqual(job.status_code,201,job.text)
  context=job.json()['input']['context']
  self.assertEqual(context['originalAnswer'],'I goed to school yesterday.')
  self.assertEqual([x['id'] for x in context['experienceDecision']['selected']],[row['id']])

 async def test_no_matching_knowledge_falls_back_and_existing_job_records_resource_gap(self):
  await self.login('s')
  wrong=await self.c.post('/api/wrongs',json={'prompt':'请引导比较英语两段修辞表达。','answer':'还不能确定','subject':'英语','grade':'高三','knowledgeIds':[],'requestKey':uuid.uuid4().hex})
  self.assertEqual(wrong.status_code,201,wrong.text)
  job=await self.c.post('/api/ai/jobs',json={'capability':'text','requestKey':uuid.uuid4().hex,'data':{'wrongId':wrong.json()['id'],'mode':'guidance','strategy':'hint','prompt':'请引导修辞分析'}})
  self.assertEqual(job.status_code,201,job.text);self.assertTrue(job.json()['input']['context']['experienceDecision']['fallback'])
  with SessionLocal() as db:self.assertIn(job.json()['id'],[g['jobId'] for g in coverage(db)['recentGaps']])

 async def test_independent_case_plan_without_course_uses_existing_job_and_private_editable_result(self):
  from sczx_business.models import LessonDraft,ModelJob,ModelRun
  from sczx_business.model_jobs import execute
  from unittest.mock import patch
  from accept_resource_chain import ControlledResourceProvider
  row=next(r for r in load_bundle()[0]['entries'] if r['topic']=='一般过去时')
  await self.login('t')
  with SessionLocal() as db:before=db.scalar(select(func.count()).select_from(LessonDraft))
  r=await self.c.post('/api/ai/jobs',json={'capability':'lesson_agent','requestKey':uuid.uuid4().hex,'data':{'caseId':row['id'],'caseVersionId':'resver-'+row['id'][4:],'task':row['experience']['difficulty']}})
  self.assertEqual(r.status_code,201,r.text);job=r.json();self.assertTrue(job['input']['independent']);self.assertEqual(job['input']['lesson']['subject'],'英语')
  rid=uuid.uuid4().hex
  with SessionLocal.begin() as db:
   stored=db.get(ModelJob,job['id']);stored.status='running';stored.attempt_number=1;db.add(ModelRun(id=rid,job_id=job['id'],number=1))
  with patch('sczx_business.model_jobs.provider',ControlledResourceProvider()):await execute(job['id'],rid)
  detail=(await self.c.get('/api/ai/jobs/'+job['id'])).json();self.assertEqual(detail['status'],'succeeded',detail.get('error'))
  plan=detail['result']['editable'];plan['goal']='教师独立修改后的目标'
  saved=await self.c.put('/api/ai/agent/'+job['id']+'/draft',json=plan);self.assertEqual(saved.status_code,200,saved.text)
  self.assertEqual((await self.c.get('/api/ai/jobs/'+job['id'])).json()['result']['editable']['goal'],plan['goal'])
  with SessionLocal() as db:self.assertEqual(db.scalar(select(func.count()).select_from(LessonDraft)),before)
  await self.login('s');self.assertEqual((await self.c.get('/api/ai/jobs/'+job['id'])).status_code,404)
