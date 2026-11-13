"""Isolated real persistence/API chain. Optional real Codex run is separately labelled."""
import copy,json,os,secrets,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import httpx
from sqlalchemy import select
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account,FileAsset,SourceMaterial,MaterialUnit,StudentRecord,ModelJob,ModelRun,CaseVersion,LearningTask,Attempt
from sczx_business.security import hash_password
from sczx_business.main import app
from sczx_business.library import reference
from sczx_business.model_jobs import execute
from test_teaching_mysql import create_accounts,fixture
from test_tutoring_mysql import ControlledGuidance
from test_agent_mysql import ControlledPlanProvider

class ExperienceGuidance(ControlledGuidance):
    async def call(self,capability,data,**kwargs):
        result,model,provider=await super().call(capability,data,**kwargs)
        chosen=data['context']['experienceDecision']['selected']
        result['usedCaseVersionIds']=[x['versionId'] for x in chosen]
        if chosen:result['steps']=[chosen[0]['method']]
        return result,model,provider

@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class ExperienceMySQLTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertTrue(engine.url.database.startswith('sczx_test_'))
        self.prefix='ix'+uuid.uuid4().hex[:6]+'-';self.password=secrets.token_urlsafe(24);create_accounts(self.password,self.prefix)
        self.admin=self.prefix+'a';self.fx=fixture(self.prefix.rstrip('-'),self.prefix)
        with SessionLocal.begin() as db:
            db.add(Account(id=self.admin,username=self.admin,display_name='工程验收管理员',role='admin',password_hash=hash_password(self.password)));db.flush()
            self.file=self.prefix+'file';db.add(FileAsset(id=self.file,owner_id=self.admin,original_name='团队自编验收文本.txt',content_type='text/plain',size=1,storage_key=self.file));db.flush()
            self.material=self.prefix+'material';db.add(SourceMaterial(id=self.material,owner_id=self.admin,file_id=self.file,title='团队自编共同运算案例',metadata_json={'author':'项目工程夹具','sourceNote':'自编工程验收，不代表真实名师经验'}));db.flush()
            self.unit=self.prefix+'unit';db.add(MaterialUnit(id=self.unit,material_id=self.material,position=1,label='第1段',kind='text',text='先让学生列出等式两边的数量，再比较同时减去相同数量后的变化。',original_text='先让学生列出等式两边的数量，再比较同时减去相同数量后的变化。',details={}));db.flush()
            self.ref=reference(db,db.get(MaterialUnit,self.unit))
            self.record=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.fx['tasks'][0],StudentRecord.student_id==self.prefix+'s0')).id
            self.oldtask=copy.deepcopy(db.get(LearningTask,self.fx['tasks'][0]).snapshot)
        self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test');await self.login('a')
    async def asyncTearDown(self):await self.c.aclose()
    async def login(self,name):
        self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':self.prefix+name,'password':self.password});self.assertEqual(r.status_code,200,r.text)
    async def req(self,method,path,body=None,status=200):
        r=await self.c.request(method,'/api'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
    async def run_job(self,job,provider):
        with SessionLocal.begin() as db:
            row=db.get(ModelJob,job['id']);row.status='running';row.attempt_number+=1;rid='run-'+uuid.uuid4().hex;db.add(ModelRun(id=rid,job_id=row.id,number=row.attempt_number))
        with patch('sczx_business.model_jobs.provider',provider):await execute(job['id'],rid)
        return await self.req('GET','/ai/jobs/'+job['id'])
    async def publish(self):
        case=await self.req('POST','/library/cases',{'unitIds':[self.unit],'title':'等式两边共同变化'},201);self.case=case['id']
        self.data={**case['draft'],'title':'等式两边共同变化','content':self.ref['quote'],'grade':'七年级','subject':'数学','knowledgeIds':[self.fx['lesson'].replace('-lesson','-kp')],'provenance':{'kind':'team','author':'项目自编夹具','evidence':'本轮团队自编材料','authorization':'internal','authorizationEvidence':'仅供本地工程验收'},'experience':{'difficulty':'不明白等式两边为什么要共同变化','diagnosis':'让学生描述等式两边的变化','strategy':'先列两组相等数量，再让学生分别拿走同样数量，比较剩余数量','steps':'列数量；同时拿走；比较剩余','effectCheck':'使用另一组数量独立解释'}}
        await self.req('PUT','/library/cases/'+self.case+'/draft',{'data':self.data});await self.req('POST','/library/cases/'+self.case+'/review');value=await self.req('GET','/library/cases/'+self.case)
        # Unchanged save retains server review; a client cannot replace the reviewer stamp.
        reviewed=copy.deepcopy(value['draft']);reviewed.pop('reviewed');reviewed.pop('updatedAt');reviewed['experienceReview']={'reviewerId':'forged'}
        saved=await self.req('PUT','/library/cases/'+self.case+'/draft',{'data':reviewed});self.assertTrue(saved['draft']['reviewed']);self.assertEqual(saved['draft']['experienceReview']['reviewerId'],self.admin)
        return (await self.req('POST','/library/cases/'+self.case+'/publish'))['published']
    async def test_source_review_teacher_preparation_student_guidance_version_chain(self):
        published=await self.publish();version=published['versionId']
        await self.login('s0');await self.req('POST','/library/cases/'+self.case+'/review',status=403)
        job=await self.req('POST','/ai/jobs',{'capability':'text','recordId':self.record,'requestKey':uuid.uuid4().hex,'data':{'guidance':True,'strategy':'hint','prompt':'不明白等式两边为什么要共同变化','question':0,'blockId':'eq-practice'}},201)
        selected=job['input']['context']['experienceDecision']['selected'];self.assertIn(version,[x['versionId'] for x in selected]);self.assertEqual(selected[0]['provenance']['kind'],'team')
        if os.getenv('SCZX_INNOVATION_REAL')=='1':
            from sczx_business.model_provider import ModelProvider
            provider=ModelProvider()
        else:provider=ExperienceGuidance()
        try:result=await self.run_job(job,provider)
        finally:
            if hasattr(provider,'close'):await provider.close()
        self.assertEqual(result['status'],'succeeded');self.assertIn(version,result['result']['usedCaseVersionIds']);self.assertTrue(result['result']['difficultyAssessment']['observations'])
        independent=await self.req('POST','/ai/jobs',{'capability':'text','recordId':self.record,'requestKey':uuid.uuid4().hex,'data':{'guidance':True,'strategy':'try','prompt':'我想自己试试','question':0,'blockId':'eq-practice','parentJobId':job['id']}},201)
        attempt_provider=ExperienceGuidance();independent=await self.run_job(independent,attempt_provider);self.assertEqual(attempt_provider.calls,0);self.assertEqual(independent['result']['experienceDecision']['selected'],[])
        await self.login('t1');prep=await self.req('POST','/ai/jobs',{'capability':'lesson_agent','requestKey':uuid.uuid4().hex,'data':{'lessonId':self.fx['lesson'],'task':'不明白等式两边为什么要共同变化，设计引导活动'}},201)
        plan=await self.run_job(prep,ControlledPlanProvider());self.assertIn(version,[x['versionId'] for x in plan['result']['experienceDecision']['selected']])
        state=await self.req('GET','/ai/agent/draft-state?lessonId='+self.fx['lesson']);await self.req('POST','/ai/agent/'+prep['id']+'/confirm',{'expectedDraftHash':state['draftHash'],'confirmed':True})
        await self.login('a');await self.req('POST','/library/cases/'+self.case+'/revise');new={**self.data,'content':self.data['content']+'修订说明'};await self.req('PUT','/library/cases/'+self.case+'/draft',{'data':new});await self.req('POST','/library/cases/'+self.case+'/publish',status=422);await self.req('POST','/library/cases/'+self.case+'/review');second=(await self.req('POST','/library/cases/'+self.case+'/publish'))['published'];self.assertEqual(second['version'],2)
        with SessionLocal() as db:
            self.assertEqual(db.get(CaseVersion,version).data['content'],published['content']);self.assertEqual(db.get(LearningTask,self.fx['tasks'][0]).snapshot,self.oldtask);self.assertEqual(db.get(ModelJob,job['id']).input['context']['experienceDecision']['selected'][0]['versionId'],version)
        if os.getenv('SCZX_INNOVATION_LOGIN_FILE'):
            private={'prefix':self.prefix,'password':self.password,'lesson':self.fx['lesson'],'record':self.record,'task':self.fx['tasks'][0],'case':self.case,'studentJob':job['id'],'teacherJob':prep['id']}
            Path(os.environ['SCZX_INNOVATION_LOGIN_FILE']).write_text(json.dumps(private));os.chmod(os.environ['SCZX_INNOVATION_LOGIN_FILE'],0o600)
        if os.getenv('SCZX_INNOVATION_EVIDENCE'):
            out={'mode':'real Codex student guidance; controlled teacher model' if os.getenv('SCZX_INNOVATION_REAL')=='1' else 'real MySQL/API; controlled model outputs','publishedCase':published,'studentJob':result,'teacherJob':plan,'newVersion':second,'assertions':['admin review required','unchanged save preserves server stamp','student cannot review','selected experience reaches model and output','teacher plan explicit confirmation','old case/task/job unchanged']}
            Path(os.environ['SCZX_INNOVATION_EVIDENCE']).write_text(json.dumps(out,ensure_ascii=False,indent=2))
    async def test_history_evidence_changes_next_strategy_and_helped_excluded(self):
        other=self.fx['tasks'][1]
        with SessionLocal.begin() as db:
            record=db.scalar(select(StudentRecord).where(StudentRecord.task_id==other,StudentRecord.student_id==self.prefix+'s0'))
            for i in range(2):db.add(Attempt(id=self.prefix+'attempt'+str(i),record_id=record.id,question=i,answer='0',reason='独立尝试未解出',helped=False,correct=False,verification={'status':'verified'}))
        await self.login('s0')
        body={'capability':'text','recordId':self.record,'requestKey':uuid.uuid4().hex,'data':{'guidance':True,'strategy':'continue','prompt':'请继续引导','question':0,'blockId':'eq-practice'}}
        job=await self.req('POST','/ai/jobs',body,201);self.assertEqual(job['strategy'],'foundation');self.assertEqual(len(job['input']['context']['difficultyAssessment']['historyEvidence']),2)
        with SessionLocal.begin() as db:
            for row in db.scalars(select(Attempt).where(Attempt.id.in_([self.prefix+'attempt0',self.prefix+'attempt1']))):row.helped=True
        body['requestKey']=uuid.uuid4().hex;job=await self.req('POST','/ai/jobs',body,201);self.assertEqual(job['strategy'],'hint')
