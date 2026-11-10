"""Persistent scoped tutoring regressions. Controlled providers are not real-model evidence."""
import asyncio,copy,json,os,secrets,subprocess,sys,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import httpx
from sqlalchemy import select,func
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account,StudentRecord,ModelJob,ModelRun,ClassMember,KnowledgePoint,HelpRecord,FileAsset
from sczx_business.main import app
from sczx_business.model_jobs import execute
from sczx_business.model_provider import ModelError
from sczx_business.tutoring import validate_result,model_input
from test_teaching_mysql import create_accounts,fixture

class ControlledGuidance:
    def __init__(self,mode='success'):self.calls=0;self.mode=mode;self.entered=asyncio.Event();self.release=asyncio.Event();self.inputs=[]
    async def call(self,capability,data,**kwargs):
        self.calls+=1;self.inputs.append(data);self.entered.set()
        if self.mode=='wait':await self.release.wait()
        if self.mode=='timeout':raise ModelError('受控超时',retryable=True)
        representation='balance' if data['history'] and data['history'][-1]['representation']!='balance' else 'numeric'
        result={'title':'比较两边的共同变化','hint':'把等式两边看作数量相同的两组，先指出要消去哪一部分。','steps':['用不同例子比较：a + 2 = 9，两边同时减去2。'],'question':'你准备在两边同时做什么？','mathClaims':[{'left':'9-2','right':'7'}],'strategy':data['strategy'],'representation':representation,'nextStrategy':'foundation','prerequisiteId':data['context']['prerequisites'][0]['id'] if data['strategy']=='foundation' and data['context']['prerequisites'] else '', 'usedCaseVersionIds':[]}
        if self.mode=='leak':result['hint']='x = 8'
        if self.mode=='claim_leak':result['mathClaims']=[{'left':'x-3=5','right':'x=8'}]
        if self.mode=='math':result['mathClaims']=[{'left':'2+2','right':'5'}]
        return result,'controlled','controlled'

@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class TutoringMySQLTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        assert engine.url.database.startswith('sczx_test_')
        subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True)
        cls.password=secrets.token_urlsafe(24);create_accounts(cls.password,'tutor-')
    async def asyncSetUp(self):
        self.fx=fixture('tutor-'+uuid.uuid4().hex[:8],'tutor-');self.task=self.fx['tasks'][0];self.room=self.fx['classes'][0];self.record=None
        with SessionLocal.begin() as db:
            self.record=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='tutor-s0')).id
            kp=db.get(KnowledgePoint,self.fx['lesson'].replace('-lesson','-kp'));kp.prerequisites=[self.fx['lesson'].replace('-lesson','-base')];db.add(KnowledgePoint(id=kp.prerequisites[0],name='相等关系',prerequisites=[],aliases=[]))
        self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test');await self.login('s0')
    async def asyncTearDown(self):await self.c.aclose()
    async def login(self,name):
        self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':'tutor-'+name,'password':self.password});self.assertEqual(r.status_code,200,r.text)
    async def create(self,**overrides):
        data={'guidance':True,'strategy':'hint','prompt':'为什么两边要共同变化？','question':0,'blockId':'eq-practice',**overrides}
        r=await self.c.post('/api/ai/jobs',json={'capability':'text','recordId':self.record,'requestKey':uuid.uuid4().hex,'data':data});self.assertEqual(r.status_code,201,r.text);return r.json()
    def begin(self,ident):
        with SessionLocal.begin() as db:
            job=db.get(ModelJob,ident);job.status='running';job.attempt_number+=1;rid='run-'+uuid.uuid4().hex;db.add(ModelRun(id=rid,job_id=ident,number=job.attempt_number));return rid
    async def run_job(self,job,provider=None):
        provider=provider or ControlledGuidance();rid=self.begin(job['id'])
        with patch('sczx_business.model_jobs.provider',provider):await execute(job['id'],rid)
        r=await self.c.get('/api/ai/jobs/'+job['id']);self.assertEqual(r.status_code,200);return r.json(),provider
    async def test_removed_retry_new_and_queued_execution_blocked_history_retained(self):
        job=await self.create()
        with SessionLocal.begin() as db:db.get(ModelJob,job['id']).status='failed'
        await self.login('t1');r=await self.c.delete('/api/teaching/classes/'+self.room+'/members/tutor-s0');self.assertEqual(r.status_code,200)
        await self.login('s0');self.assertEqual((await self.c.post('/api/ai/jobs/'+job['id']+'/retry')).status_code,403)
        for cap in ['text','ocr']:
            r=await self.c.post('/api/ai/jobs',json={'capability':cap,'recordId':self.record,'requestKey':uuid.uuid4().hex,'data':{'prompt':'继续','guidance':True}});self.assertEqual(r.status_code,403)
        self.assertEqual((await self.c.get('/api/ai/jobs/'+job['id'])).status_code,200)
        provider=ControlledGuidance()
        with self.assertRaises(ModelError):await self.run_job(job,provider)
        self.assertEqual(provider.calls,0)
    async def test_removal_during_generation_does_not_write_guidance(self):
        job=await self.create();provider=ControlledGuidance('wait');rid=self.begin(job['id'])
        with patch('sczx_business.model_jobs.provider',provider):
            running=asyncio.create_task(execute(job['id'],rid));await provider.entered.wait();await self.login('t1');await self.c.delete('/api/teaching/classes/'+self.room+'/members/tutor-s0');provider.release.set()
            with self.assertRaises(ModelError):await running
        with SessionLocal() as db:self.assertIsNone(db.get(ModelJob,job['id']).result);self.assertEqual(db.get(HelpRecord,'help-'+job['id'][4:]).kind,'指导请求')
    async def test_canonical_context_is_bounded_and_excludes_internal_fields(self):
        invalid=await self.c.post('/api/ai/jobs',json={'capability':'text','recordId':self.record,'requestKey':uuid.uuid4().hex,'data':{'prompt':'问'*3001,'question':0}});self.assertEqual(invalid.status_code,422)
        job=await self.create(context={'teacherNote':'不应该使用'},history=[{'secret':'别的学生'}],_validation={'answer':'外部伪造'})
        self.assertNotIn('_validation',job['input']);self.assertNotIn('不应该使用',json.dumps(job,ensure_ascii=False));self.assertEqual(job['input']['context']['question']['id'],'eq-practice-add');self.assertNotIn('answer',job['input']['context']['question']);self.assertEqual(job['input']['scope']['taskId'],self.task)
        result,provider=await self.run_job(job);self.assertNotIn('_validation',provider.inputs[0]);self.assertEqual(result['result']['workflow']['modelCalls'],1)
    async def test_strategy_chain_parent_scope_and_four_turn_bound(self):
        parent=None
        for choice in ['hint','example','rephrase','foundation','hint','continue']:
            job=await self.create(strategy=choice,parentJobId=parent,prompt='我仍不明白数量相同的含义，请先检查相等关系。');result,_=await self.run_job(job);parent=result['id'];self.assertLessEqual(result['result']['workflow']['historyTurns'],4)
        self.assertEqual(result['strategy'],'foundation');self.assertTrue(result['result']['prerequisites'])
        for overrides in [{'parentJobId':parent,'question':1},{'parentJobId':parent,'blockId':'eq-balance','question':None}]:
            r=await self.c.post('/api/ai/jobs',json={'capability':'text','recordId':self.record,'requestKey':uuid.uuid4().hex,'data':{'guidance':True,'strategy':'hint','prompt':'继续',**overrides}});self.assertEqual(r.status_code,422)
        await self.login('s1');r=await self.c.get('/api/ai/jobs/'+parent);self.assertEqual(r.status_code,404)
    async def test_self_attempt_no_model_or_help_reset(self):
        first,_=await self.run_job(await self.create());job=await self.create(strategy='try',parentJobId=first['id']);result,provider=await self.run_job(job);self.assertEqual(provider.calls,0);self.assertEqual(result['result']['workflow']['modelCalls'],0)
        r=await self.c.post('/api/records/'+self.task+'/attempts',json={'question':0,'answer':'8','reason':'两边同时加3','helped':False});self.assertEqual(r.status_code,201)
        with SessionLocal() as db:
            from sczx_business.models import Attempt
            self.assertTrue(db.scalar(select(Attempt).where(Attempt.record_id==self.record)).helped);self.assertEqual(db.scalar(select(func.count()).select_from(HelpRecord).where(HelpRecord.record_id==self.record)),1)
    async def test_invalid_math_and_original_answer_blocked_after_one_repair(self):
        for mode in ['math','leak','claim_leak']:
            provider=ControlledGuidance(mode);job=await self.create(prompt='检查'+mode)
            with self.assertRaises(ModelError):await self.run_job(job,provider)
            self.assertEqual(provider.calls,2)
            with SessionLocal() as db:self.assertIsNone(db.get(ModelJob,job['id']).result)
    async def test_failed_manual_retry_stop_and_duplicate_request(self):
        job=await self.create();provider=ControlledGuidance('timeout')
        with self.assertRaises(ModelError):await self.run_job(job,provider)
        with SessionLocal.begin() as db:row=db.get(ModelJob,job['id']);row.status='failed';row.active_hash=None
        r=await self.c.post('/api/ai/jobs/'+job['id']+'/retry');self.assertEqual(r.status_code,200);r=await self.c.post('/api/ai/jobs/'+job['id']+'/stop');self.assertEqual(r.status_code,200);self.assertEqual(r.json()['status'],'cancelled');self.assertEqual((await self.c.get('/api/ai/jobs/'+job['id'])).status_code,200)
    async def test_ocr_scope_confirmation_and_text_fallback(self):
        ident='job-'+uuid.uuid4().hex;fileid='file-'+uuid.uuid4().hex
        with SessionLocal.begin() as db:
            db.add(FileAsset(id=fileid,owner_id='tutor-s0',original_name='原题.png',content_type='image/png',size=1,storage_key=uuid.uuid4().hex));db.flush();db.add(ModelJob(id=ident,owner_id='tutor-s0',record_id=self.record,file_id=fileid,capability='ocr',request_key=uuid.uuid4().hex,input_hash=uuid.uuid4().hex,input={'question':0,'blockId':'eq-practice'},status='succeeded',result={'text':'x-3=5','equation':'x-3=5','uncertainties':['减号模糊']}))
        data={'guidance':True,'strategy':'hint','prompt':'先提示','question':0,'blockId':'eq-practice','ocrJobId':ident,'recognizedText':'学生修正：x - 3 = 5','confirmed':False}
        r=await self.c.post('/api/ai/jobs',json={'capability':'text','recordId':self.record,'requestKey':uuid.uuid4().hex,'data':data});self.assertEqual(r.status_code,422)
        data['confirmed']=True;data['confirmedEquation']='3z = 18';r=await self.c.post('/api/ai/jobs',json={'capability':'text','recordId':self.record,'requestKey':uuid.uuid4().hex,'data':data});self.assertEqual(r.status_code,201,r.text);self.assertEqual(r.json()['recognizedText'],data['recognizedText']);self.assertEqual(r.json()['fileId'],fileid);self.assertEqual(r.json()['input']['context']['question']['equation'],'3z = 18');self.assertEqual(r.json()['input']['context']['focus'],'confirmed_image');self.assertEqual(r.json()['input']['scope']['questionId'],'eq-practice-add')
        data['question']=1;r=await self.c.post('/api/ai/jobs',json={'capability':'text','recordId':self.record,'requestKey':uuid.uuid4().hex,'data':data});self.assertEqual(r.status_code,422)
        await self.create(prompt='不用题图，直接文字提问')
    async def test_replay_after_context_change_keeps_first_job_and_help_record(self):
        key=uuid.uuid4().hex;payload={'capability':'text','recordId':self.record,'requestKey':key,'data':{'guidance':True,'strategy':'hint','prompt':'请先提示','question':0,'blockId':'eq-practice'}}
        first=await self.c.post('/api/ai/jobs',json=payload);self.assertEqual(first.status_code,201)
        with SessionLocal.begin() as db:
            rec=db.get(StudentRecord,self.record);rec.observation='保存了更新的学生解释'
        second=await self.c.post('/api/ai/jobs',json=payload);self.assertEqual(second.status_code,201);self.assertEqual(first.json()['id'],second.json()['id'])
        payload['data']['prompt']='完全不同的问题';self.assertEqual((await self.c.post('/api/ai/jobs',json=payload)).status_code,409)
        with SessionLocal() as db:self.assertEqual(db.scalar(select(func.count()).select_from(HelpRecord).where(HelpRecord.record_id==self.record)),1)
    async def test_legacy_student_client_cannot_bypass_guidance_policy(self):
        r=await self.c.post('/api/ai/jobs',json={'capability':'text','recordId':self.record,'requestKey':uuid.uuid4().hex,'data':{'prompt':'请给我原题答案','question':0,'context':{'answer':'8','teacherNote':'伪造内部说明'}}});self.assertEqual(r.status_code,201,r.text)
        self.assertTrue(r.json()['input']['guidance']);result,provider=await self.run_job(r.json());self.assertNotIn('伪造内部说明',json.dumps(provider.inputs,ensure_ascii=False));self.assertEqual(result['result']['strategy'],'hint')
