"""Real MySQL + graph with controlled model boundaries; real-model acceptance is separate."""
import asyncio,copy,os,secrets,subprocess,sys,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import httpx
from sqlalchemy import select
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account,Course,Lesson,LessonContent,LessonVersion,LessonDraft,KnowledgePoint,ModelJob,ModelRun,LearningTask,Classroom
from sczx_business.security import hash_password
from sczx_business.main import app
from sczx_business.lesson_seed import first_lesson
from sczx_business.prepare_agent import run_agent,fingerprint
from sczx_business.model_jobs import execute,recover_interrupted
from sczx_business.model_provider import ModelError

class ControlledPlanProvider:
    def __init__(self,mode='success'):self.mode=mode;self.calls=0;self.entered=asyncio.Event();self.release=asyncio.Event()
    async def call(self,capability,data,**kwargs):
        assert capability=='lesson_plan';self.calls+=1;self.entered.set()
        if self.mode=='timeout':raise ModelError('controlled timeout',retryable=True)
        if self.mode=='invalid':return {'title':'格式错误'},'controlled','controlled'
        if self.mode=='wait':await self.release.wait()
        return {'title':'受控教学备课','goal':data['goal'],'rationale':['通过共同运算比较理解等式性质'],'blocks':[{'id':b['id'],'title':b['title'],'content':'受控生成：'+b['content'],'evidenceIds':[data['evidence'][0]['id']]} for b in data['blocks']],'mathClaims':[{'left':'x+1-1','right':'x'}]},'controlled','controlled'

@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL integration is opt-in')
class AgentMySQLTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        assert engine.url.database.startswith('sczx_test_')
        subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True)
        cls.password=secrets.token_urlsafe(24)
        data=first_lesson();data.update(knowledgeIds=['agent-kp'],prerequisiteIds=[],caseId=None,caseVersionId=None)
        for q in data['questions']:q['knowledgeIds']=['agent-kp']
        cls.lesson=data
        with SessionLocal.begin() as db:
            for role,ident in [('teacher','agent-owner'),('teacher','agent-other'),('student','agent-student')]:db.add(Account(id=ident,username=ident,display_name=ident,role=role,password_hash=hash_password(cls.password)))
            db.add(Course(id='agent-course',title='Agent自编课程',grade='七年级'));db.flush()
            db.add(Lesson(id='agent-lesson',course_id='agent-course',title='等式性质'));db.flush()
            db.add(KnowledgePoint(id='agent-kp',name='等式性质（Agent验收）',prerequisites=[],aliases=[]))
            db.add(LessonContent(lesson_id='agent-lesson',draft=None,status='published',reviewed=True))
            db.add(LessonVersion(id='agent-version',lesson_id='agent-lesson',number=1,data=data))
            db.add(LessonVersion(id='agent-old-version',lesson_id='agent-lesson',number=0,data={**data,'goal':'旧版本目标'}))
            db.add(LessonDraft(id='agent-old-draft',teacher_id='agent-owner',lesson_id='agent-lesson',goal='旧备课目标',student_base='保留学生基础',due_date='2026-11-30',blocks=copy.deepcopy(data['blocks']),questions=copy.deepcopy(data['questions']),lesson_snapshot={**data,'versionId':'agent-version'}))
            db.add(Classroom(id='agent-class',teacher_id='agent-owner',name='Agent自编验收班',grade='七年级'));db.flush()
            db.add(LearningTask(id='agent-old-task',classroom_id='agent-class',teacher_id='agent-owner',lesson_id='agent-lesson',title='原任务',snapshot={'goal':'原目标','blocks':copy.deepcopy(data['blocks'])},questions=copy.deepcopy(data['questions']),due_date='2026-11-30'))
    async def asyncSetUp(self):
        self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url='http://test');await self.login('agent-owner')
    async def asyncTearDown(self):await self.c.aclose()
    async def login(self,name):
        r=await self.c.post('/api/auth/login',json={'username':name,'password':self.password});r.raise_for_status()
    async def new_job(self):
        r=await self.c.post('/api/ai/jobs',json={'capability':'lesson_agent','requestKey':str(uuid.uuid4()),'data':{'lessonId':'agent-lesson','task':'设计等式性质的天平活动，解释共同运算'}});self.assertEqual(r.status_code,201,r.text);return r.json()
    def begin(self,ident):
        with SessionLocal.begin() as db:
            job=db.get(ModelJob,ident);job.status='running';job.attempt_number+=1;runid='run-'+uuid.uuid4().hex;db.add(ModelRun(id=runid,job_id=ident,number=job.attempt_number));return runid
    async def run_success(self):
        job=await self.new_job();runid=self.begin(job['id']);provider=ControlledPlanProvider()
        with patch('sczx_business.model_jobs.provider',provider):await execute(job['id'],runid)
        return (await self.c.get('/api/ai/jobs/'+job['id'])).json(),provider
    async def test_confirm_draft_is_explicit_and_idempotent(self):
        job,provider=await self.run_success();self.assertEqual(provider.calls,1);self.assertEqual(len(job['result']['steps']),6)
        self.assertEqual(job['result']['verification']['status'],'verified')
        state=(await self.c.get('/api/ai/agent/draft-state',params={'lessonId':'agent-lesson'})).json()
        r=await self.c.post('/api/ai/agent/'+job['id']+'/confirm',json={'expectedDraftHash':'wrong','confirmed':True});self.assertEqual(r.status_code,409)
        r=await self.c.post('/api/ai/agent/'+job['id']+'/confirm',json={'expectedDraftHash':state['draftHash'],'confirmed':False});self.assertEqual(r.status_code,422)
        with SessionLocal() as db:before=db.query(LearningTask).count();version=copy.deepcopy(db.get(LessonVersion,'agent-version').data);old_task=copy.deepcopy(db.get(LearningTask,'agent-old-task').snapshot)
        r=await self.c.post('/api/ai/agent/'+job['id']+'/confirm',json={'expectedDraftHash':state['draftHash'],'confirmed':True});self.assertEqual(r.status_code,200,r.text)
        repeat=await self.c.post('/api/ai/agent/'+job['id']+'/confirm',json={'expectedDraftHash':state['draftHash'],'confirmed':True});self.assertEqual(repeat.status_code,200);self.assertFalse(repeat.json()['created'])
        with SessionLocal() as db:
            draft=db.scalar(select(LessonDraft).where(LessonDraft.teacher_id=='agent-owner'));self.assertTrue(draft.blocks[0]['content'].startswith('受控生成：'));self.assertEqual(draft.lesson_snapshot['versionId'],job['input']['lesson']['versionId']);self.assertEqual(draft.student_base,'保留学生基础');self.assertEqual(draft.due_date,'2026-11-30');self.assertEqual(draft.questions,self.lesson['questions']);self.assertEqual(db.get(LessonVersion,'agent-version').data,version);self.assertEqual(db.query(LearningTask).count(),before);self.assertEqual(db.get(LearningTask,'agent-old-task').snapshot,old_task)
    async def test_timeout_retains_checkpoints_and_resume_does_not_repeat_success(self):
        job=await self.new_job();runid=self.begin(job['id']);provider=ControlledPlanProvider('timeout')
        with self.assertRaises(ModelError):await run_agent(job['id'],runid,provider)
        recover_interrupted();j=(await self.c.get('/api/ai/jobs/'+job['id'])).json();self.assertEqual(j['status'],'failed');self.assertEqual(sum(s['status']=='succeeded' for s in j['result']['steps']),3)
        r=await self.c.post('/api/ai/jobs/'+job['id']+'/retry');self.assertEqual(r.status_code,200);runid=self.begin(job['id']);success=ControlledPlanProvider()
        with patch('sczx_business.model_jobs.provider',success):await execute(job['id'],runid)
        self.assertEqual(success.calls,1)
        # A crash after all nodes were committed but before the job terminal flag must not re-call the model.
        self.begin(job['id']);recover_interrupted();await self.c.post('/api/ai/jobs/'+job['id']+'/retry');runid=self.begin(job['id']);no_call=ControlledPlanProvider('timeout')
        with patch('sczx_business.model_jobs.provider',no_call):await execute(job['id'],runid)
        self.assertEqual(no_call.calls,0)
    async def test_no_cases_materials_and_invalid_output_are_explicit(self):
        job,provider=await self.run_success();self.assertTrue(job['result']['warnings']);self.assertFalse(job['result']['materials'])
        bad=copy.deepcopy(job['result']['editable']);bad['blocks'][0]['evidenceIds']=['invented']
        r=await self.c.put('/api/ai/agent/'+job['id']+'/draft',json=bad);self.assertEqual(r.status_code,422)
        bad=copy.deepcopy(job['result']['editable']);bad['mathClaims']=[{'left':'1','right':'2'}]
        r=await self.c.put('/api/ai/agent/'+job['id']+'/draft',json=bad);self.assertEqual(r.status_code,422)
        other=await self.new_job();runid=self.begin(other['id'])
        with self.assertRaises(ModelError):await run_agent(other['id'],runid,ControlledPlanProvider('invalid'))
        with SessionLocal() as db:self.assertTrue(db.get(ModelJob,other['id']).result['steps'])
    async def test_active_duplicate_and_cross_role_access(self):
        payload={'capability':'lesson_agent','requestKey':str(uuid.uuid4()),'data':{'lessonId':'agent-lesson','task':'解释等式两边共同变化的步骤'}}
        first=await self.c.post('/api/ai/jobs',json=payload);second=await self.c.post('/api/ai/jobs',json=payload);self.assertEqual(first.json()['id'],second.json()['id'])
        ident=first.json()['id']
        for name in ['agent-other','agent-student']:
            await self.login(name)
            self.assertEqual((await self.c.get('/api/ai/jobs/'+ident)).status_code,404)
            self.assertEqual((await self.c.post('/api/ai/agent/'+ident+'/cancel')).status_code,404)
        self.assertEqual((await self.c.post('/api/ai/jobs',json=payload)).status_code,403)
    async def test_cancel_in_progress_keeps_prior_steps(self):
        job=await self.new_job();runid=self.begin(job['id']);provider=ControlledPlanProvider('wait')
        task=asyncio.create_task(run_agent(job['id'],runid,provider));await asyncio.wait_for(provider.entered.wait(),10)
        r=await self.c.post('/api/ai/agent/'+job['id']+'/cancel');self.assertEqual(r.status_code,200)
        provider.release.set()
        with self.assertRaises(asyncio.CancelledError):await task
        current=(await self.c.get('/api/ai/jobs/'+job['id'])).json();self.assertEqual(current['status'],'cancelled');self.assertGreaterEqual(len(current['result']['steps']),3)

    async def test_total_deadline_prevents_model_call(self):
        job=await self.new_job();runid=self.begin(job['id']);provider=ControlledPlanProvider()
        with SessionLocal.begin() as db:
            row=db.get(ModelJob,job['id']);row.result={'steps':[],'warnings':[],'decision':'pending','modelCalls':0,'budgetStartedAt':'2000-01-01T00:00:00+00:00'}
        with self.assertRaises(ModelError):await run_agent(job['id'],runid,provider)
        self.assertEqual(provider.calls,0)

    async def test_unparsed_material_is_not_presented_as_evidence(self):
        from sczx_business.models import FileAsset,SourceMaterial,MaterialUnit
        from sczx_business.prepare_agent import collect_materials
        with SessionLocal.begin() as db:
            db.add(FileAsset(id='agent-pending-file',owner_id='agent-owner',original_name='未解析自编材料.pdf',content_type='application/pdf',size=0,storage_key='agent-pending-file'));db.flush()
            db.add(SourceMaterial(id='agent-pending-material',owner_id='agent-owner',file_id='agent-pending-file',title='未解析自编材料'));db.flush()
            db.add(MaterialUnit(id='agent-pending-unit',material_id='agent-pending-material',position=1,label='第1页',kind='pdf',text='',original_text=''));db.flush()
            result=collect_materials(db,[{'id':'case-pending','versionId':'pending-version','references':[{'unitId':'agent-pending-unit','quote':'尚未解析的文字'}]}],'等式性质')
            self.assertEqual(result,[])

    async def test_step10_source_republish_blocks_old_agent_confirmation(self):
        from sczx_business.models import LessonVersion
        job=await self.new_job();runid=self.begin(job['id']);provider=ControlledPlanProvider('wait')
        with patch('sczx_business.model_jobs.provider',provider):
            execution=asyncio.create_task(execute(job['id'],runid))
            await asyncio.wait_for(provider.entered.wait(),10)
            with SessionLocal.begin() as db:
                number=max(v.number for v in db.scalars(select(LessonVersion).where(LessonVersion.lesson_id=='agent-lesson')))+1
                new=LessonVersion(id='av-'+uuid.uuid4().hex,lesson_id='agent-lesson',number=number,data=copy.deepcopy(self.lesson));db.add(new)
            provider.release.set();await execution
        oldid=job['input']['lesson']['versionId']
        state=(await self.c.get('/api/ai/agent/draft-state',params={'lessonId':'agent-lesson'})).json()
        response=await self.c.post('/api/ai/agent/'+job['id']+'/confirm',json={'expectedDraftHash':state['draftHash'],'confirmed':True})
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual((await self.c.get('/api/ai/jobs/'+job['id'])).json()['input']['lesson']['versionId'],oldid)
        preflight=await self.c.post('/api/ai/jobs',json={'capability':'lesson_agent','requestKey':str(uuid.uuid4()),'data':{'lessonId':'agent-lesson','task':'旧来源应先核对再生成'}})
        self.assertEqual(preflight.status_code,409)

        # Restore source alignment for the remaining independent test methods; history stays immutable.
        with SessionLocal.begin() as db:
            row=db.scalar(select(LessonDraft).where(LessonDraft.teacher_id=='agent-owner'));row.lesson_snapshot={**self.lesson,'versionId':new.id}

    async def test_step10_saved_history_concurrency_restore_export_and_permissions(self):
        import io
        from docx import Document
        lesson='agent-lesson'
        platform=(await self.c.get('/api/platform',params={'lessonId':lesson})).json();draft=platform['lessonDraft'];original=copy.deepcopy(draft)
        draft['goal']='并发验收：理解等式两边同时运算';draft['planningDetails']={'focus':'共同运算','difficulty':'只改变一边'}
        saved=await self.c.put('/api/platform',json={'data':platform});self.assertEqual(saved.status_code,200,saved.text)
        stale=await self.c.put('/api/platform',json={'data':platform});self.assertEqual(stale.status_code,409)
        versions=(await self.c.get('/api/preparation/'+lesson+'/versions')).json();self.assertTrue(versions)
        latest=versions[0];stored=(await self.c.get('/api/preparation/'+lesson+'/versions/'+latest['id'])).json();self.assertEqual(stored['goal'],draft['goal'])
        file=await self.c.get('/api/preparation/'+lesson+'/export',params={'versionId':latest['id']});self.assertEqual(file.status_code,200)
        text='\n'.join(p.text for p in Document(io.BytesIO(file.content)).paragraphs);self.assertIn(draft['goal'],text);self.assertIn('教学重点',text);self.assertNotIn('agent-owner',text);self.assertNotIn('ModelJob',text)
        old=(await self.c.get('/api/preparation/'+lesson+'/versions/'+versions[-1]['id'])).json()
        restore=await self.c.post('/api/preparation/'+lesson+'/restore',json={'versionId':versions[-1]['id'],'revision':saved.json()['draftRevision'],'confirmed':True});self.assertEqual(restore.status_code,200,restore.text);self.assertEqual(restore.json()['goal'],old['goal'])
        self.assertEqual((await self.c.get('/api/preparation/'+lesson+'/versions/'+latest['id'])).json(),stored)
        await self.login('agent-other');self.assertEqual((await self.c.get('/api/preparation/'+lesson+'/export',params={'versionId':latest['id']})).status_code,404)
        self.assertEqual((await self.c.get('/api/preparation/'+lesson+'/versions/'+latest['id'])).status_code,404)

    async def test_step10_partial_rewrite_preserves_personalization(self):
        with SessionLocal.begin() as db:
            row=db.scalar(select(LessonDraft).where(LessonDraft.teacher_id=='agent-owner'));data=copy.deepcopy(row.blocks);data[0]['content']='教师手写导入：比较5和5';data[0]['teacherQuestion']='怎样解释相等？';row.blocks=data;row.goal='教师手写目标'
        payload={'capability':'lesson_agent','requestKey':str(uuid.uuid4()),'data':{'lessonId':'agent-lesson','task':'为第二个活动补充追问与回应，保留教师其他修改','rewriteBlockId':self.lesson['blocks'][1]['id']}}
        job=(await self.c.post('/api/ai/jobs',json=payload)).json();runid=self.begin(job['id']);provider=ControlledPlanProvider()
        with patch('sczx_business.model_jobs.provider',provider):await execute(job['id'],runid)
        state=(await self.c.get('/api/ai/agent/draft-state',params={'lessonId':'agent-lesson'})).json()
        reply=await self.c.post('/api/ai/agent/'+job['id']+'/confirm',json={'expectedDraftHash':state['draftHash'],'confirmed':True});self.assertEqual(reply.status_code,200,reply.text)
        with SessionLocal() as db:
            row=db.scalar(select(LessonDraft).where(LessonDraft.teacher_id=='agent-owner'));self.assertEqual(row.goal,'教师手写目标');self.assertEqual(row.blocks[0]['content'],'教师手写导入：比较5和5');self.assertEqual(row.blocks[0]['teacherQuestion'],'怎样解释相等？');self.assertTrue(row.blocks[1]['content'].startswith('受控生成'))
