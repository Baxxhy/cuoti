"""Class/task/message API integration against an explicitly isolated MySQL database."""
import asyncio, copy, os, secrets, subprocess, sys, unittest, uuid
from datetime import datetime,timedelta
from pathlib import Path
from types import SimpleNamespace
import httpx
from sqlalchemy import select,func
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account,Course,Lesson,KnowledgePoint,LessonContent,LessonVersion,Classroom,ClassMember,LearningTask,StudentRecord,Attempt,ClassInvite,BusinessMessage,SupplementalInstruction,SupplementRecipient
from sczx_business.main import app
from sczx_business.lesson_seed import first_lesson
from sczx_business.security import hash_password
from sczx_business.teaching import cutoff,personal_status,assign,now

class DeadlineTests(unittest.TestCase):
    def test_shanghai_end_of_day_and_exact_boundary(self):
        due=cutoff('2026-11-10',True)
        self.assertEqual(due,datetime(2026,11,10,15,59,59,999999))
        self.assertEqual(cutoff('2026-11-10T23:59:59+08:00'),datetime(2026,11,10,15,59,59))
        self.assertEqual(cutoff('2026-11-10T23:59:59'),datetime(2026,11,10,15,59,59))
        self.assertEqual(cutoff('2026-11-10T15:59:59Z'),datetime(2026,11,10,15,59,59))
        rec=SimpleNamespace(completed=False,feedback='',observation='',drafts={})
        self.assertEqual(personal_status(rec,due,clock=due),'待开始')
        self.assertEqual(personal_status(rec,due,clock=due+timedelta(microseconds=1)),'已逾期')
        rec.completed=True
        self.assertEqual(personal_status(rec,due,clock=due+timedelta(days=1)),'已提交')
        rec.feedback='继续比较两边变化'
        self.assertEqual(personal_status(rec,due),'已反馈')
        self.assertEqual(personal_status(rec,due,False),'历史只读')
        self.assertIsNone(cutoff(''));self.assertIsNone(cutoff('bad'))
        with self.assertRaises(Exception):cutoff('2026-02-30',True)

def create_accounts(password):
    with SessionLocal.begin() as db:
        for name,role in [('t1','teacher'),('t2','teacher')]+[('s'+str(i),'student') for i in range(11)]:
            ident='teaching-'+name
            db.add(Account(id=ident,username=ident,display_name={'t1':'陈老师','t2':'周老师'}.get(name,'同学'+name[1:]),role=role,password_hash=hash_password(password)))

def fixture(prefix):
    """2 teachers, 3 classes of 3, one cross-class student and a late joiner."""
    data=first_lesson();lesson=prefix+'-lesson';kp=prefix+'-kp'
    data.update(knowledgeIds=[kp],prerequisiteIds=[],caseId=None,caseVersionId=None)
    for q in data['questions']:q['knowledgeIds']=[kp]
    classes=[];tasks=[]
    with SessionLocal.begin() as db:
        db.add(Course(id=prefix+'-course',title='班级验收自编课程',grade='七年级'));db.flush()
        db.add(Lesson(id=lesson,course_id=prefix+'-course',title='等式性质'));db.add(KnowledgePoint(id=kp,name='等式性质',prerequisites=[],aliases=[]));db.flush()
        db.add(LessonContent(lesson_id=lesson,draft=None,status='published',reviewed=True));db.add(LessonVersion(id=prefix+'-version',lesson_id=lesson,number=1,data=data))
        for i in range(3):
            room=Classroom(id=prefix+'-c'+str(i),teacher_id='teaching-t1' if i<2 else 'teaching-t2',name=['七年级一班','七年级二班','七年级三班'][i],grade='七年级',subject='数学');db.add(room);db.flush();classes.append(room.id)
            students=['teaching-s'+str(i*3+j) for j in range(3)]
            if i<2:students.append('teaching-s9')
            for student in students:db.add(ClassMember(classroom_id=room.id,student_id=student))
            db.flush()
            for j in range(2):
                task=LearningTask(id=prefix+'-t'+str(i)+str(j),classroom_id=room.id,teacher_id=room.teacher_id,lesson_id=lesson,title=['天平与等式','共同运算练习'][j],snapshot={**copy.deepcopy(data),'lessonSnapshot':{**data,'versionId':prefix+'-version'}},questions=copy.deepcopy(data['questions']),due_date='2020-01-01' if i==0 and j==0 else '',published_at=now());db.add(task);db.flush();tasks.append(task.id)
                for student in students:assign(db,task,student)
    return {'classes':classes,'tasks':tasks,'lesson':lesson,'data':data}

@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','requires isolated MySQL')
class TeachingMySQLTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        assert engine.url.database.startswith('sczx_test_')
        subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True)
        cls.password=secrets.token_urlsafe(24);create_accounts(cls.password)
    async def asyncSetUp(self):
        self.fx=fixture('teach-'+uuid.uuid4().hex[:8]);self.room=self.fx['classes'][0];self.task=self.fx['tasks'][0]
        self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=True),base_url='http://test');await self.login('t1')
    async def asyncTearDown(self):await self.c.aclose()
    async def login(self,name):
        self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':'teaching-'+name,'password':self.password});self.assertEqual(r.status_code,200,r.text)
    async def call(self,method,path,body=None,status=200):
        r=await self.c.request(method,'/api'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
    async def test_class_isolation_edit_members_and_empty_tasks(self):
        rows=await self.call('GET','/teaching/classes');self.assertNotIn(self.fx['classes'][2],{r['id'] for r in rows})
        for path in ['/teaching/classes/'+self.fx['classes'][2]+'/tasks','/classrooms/'+self.fx['classes'][2]+'/members','/teaching/tasks/'+self.fx['tasks'][4]]:await self.call('GET',path,status=404)
        result=await self.call('PUT','/teaching/classes/'+self.room,{'name':'一班·改名','grade':'八年级','subject':'代数'});self.assertEqual(result['subject'],'代数')
        await self.call('PUT','/teaching/classes/'+self.room,{'name':' ','grade':'八','subject':'数'},422)
        rows=await self.call('GET','/classrooms/'+self.room+'/members');cross=next(r for r in rows if r['id']=='teaching-s9');self.assertEqual({r['id'] for r in cross['classes']}&set(self.fx['classes']),set(self.fx['classes'][:2]))
        new=await self.call('POST','/classrooms',{'name':'新班','grade':'七年级','subject':'数学'},201)
        self.assertEqual(await self.call('GET','/teaching/classes/'+new['id']+'/tasks'),[])
        await self.login('t2');await self.call('PUT','/teaching/classes/'+self.room,{'name':'越权','grade':'七','subject':'数'},404)
    async def test_invite_join_expire_revoke_and_throttle(self):
        invite=await self.call('POST','/teaching/classes/'+self.room+'/invites',{'days':1},201)
        await self.login('s10');first=await self.call('POST','/teaching/join',{'code':invite['code']});second=await self.call('POST','/teaching/join',{'code':invite['code']});self.assertTrue(first['created']);self.assertFalse(second['created'])
        self.assertFalse(first['historyTasksAutomaticallyAssigned']);await self.call('GET','/teaching/tasks/'+self.task,status=404)
        await self.login('t1');await self.call('POST','/teaching/classes/'+self.room+'/invites/'+invite['id']+'/revoke');await self.login('s10');await self.call('POST','/teaching/join',{'code':invite['code']},422)
        await self.login('t1');expired=await self.call('POST','/teaching/classes/'+self.room+'/invites',{'days':1},201)
        with SessionLocal.begin() as db:db.get(ClassInvite,expired['id']).expires_at=now()-timedelta(seconds=1)
        await self.login('s10');await self.call('POST','/teaching/join',{'code':expired['code']},422)
        for _ in range(3):await self.call('POST','/teaching/join',{'code':'INVALID'},422)
        await self.call('POST','/teaching/join',{'code':'INVALID'},429)
    async def test_late_join_backfill_idempotence_and_removal_readonly(self):
        await self.call('POST','/classrooms/'+self.room+'/members',{'studentId':'teaching-s10'},201)
        with SessionLocal() as db:original=copy.deepcopy(db.get(LearningTask,self.task).snapshot)
        for n in [1,0]:
            result=await self.call('POST','/teaching/tasks/'+self.task+'/assign',{'studentIds':['teaching-s10','teaching-s10']});self.assertEqual(result['created'],n)
        await self.login('s10');self.assertFalse((await self.call('GET','/teaching/tasks/'+self.task))['readOnly'])
        await self.login('t1');await self.call('DELETE','/teaching/classes/'+self.room+'/members/teaching-s10')
        await self.login('s10');task=await self.call('GET','/teaching/tasks/'+self.task);self.assertEqual(task['status'],'历史只读');self.assertTrue(task['readOnly'])
        for path,body in [('/records/'+self.task+'/attempts',{'question':0,'answer':'3','reason':'两边同时减'}),('/records/'+self.task+'/submit',{}),('/curriculum/tasks/'+self.task+'/questions/0/hint',{})]:
            await self.call('POST',path,body,403)
        with SessionLocal() as db:self.assertEqual(db.get(LearningTask,self.task).snapshot,original);self.assertEqual(db.scalar(select(func.count()).select_from(StudentRecord).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='teaching-s10')),1)
        await self.login('t1');await self.call('POST','/classrooms/'+self.room+'/members',{'studentId':'teaching-s10'},201)
        await self.login('s10');self.assertFalse((await self.call('GET','/teaching/tasks/'+self.task))['readOnly']);await self.call('GET','/teaching/tasks/'+self.fx['tasks'][1],status=404)
    async def test_teacher_stats_personal_status_and_dashboard(self):
        with SessionLocal.begin() as db:
            recs=db.scalars(select(StudentRecord).where(StudentRecord.task_id==self.task).order_by(StudentRecord.student_id)).all()
            recs[0].completed=True;recs[0].submitted_at=now();recs[0].feedback='请比较两边';recs[1].drafts={'x':'已学习'}
        task=await self.call('GET','/teaching/tasks/'+self.task);self.assertEqual({k:task['summary'][k] for k in ['members','assigned','started','submitted','unsubmitted','overdue','feedback']},{'members':4,'assigned':4,'started':2,'submitted':1,'unsubmitted':3,'overdue':3,'feedback':1})
        dash=await self.call('GET','/teaching/dashboard?classId='+self.room);self.assertEqual(dash['stats'],{'tasks':2,'unsubmittedStudents':4,'waitingFeedback':0});self.assertEqual(len(dash['recentSubmissions']),1)
        await self.login('s0');self.assertEqual((await self.call('GET','/teaching/tasks/'+self.task))['status'],'已反馈')
        await self.login('s1');self.assertEqual((await self.call('GET','/teaching/tasks/'+self.task))['status'],'已逾期')
        self.assertEqual((await self.call('GET','/teaching/tasks/'+self.fx['tasks'][1]))['status'],'待开始')
        with SessionLocal.begin() as db:
            r=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.fx['tasks'][1],StudentRecord.student_id=='teaching-s1'));r.observation='比较左右'
        self.assertEqual((await self.call('GET','/teaching/tasks/'+self.fx['tasks'][1]))['status'],'学习中')
        await self.login('s9');dash=await self.call('GET','/teaching/dashboard');self.assertTrue(set(self.fx['tasks'][:4])<={t['id'] for t in dash['tasks']});self.assertFalse(set(self.fx['tasks'][4:])&{t['id'] for t in dash['tasks']})
    async def test_messages_persist_read_private_and_no_duplicates(self):
        await self.login('s0');one=await self.call('GET','/teaching/messages');two=await self.call('GET','/teaching/messages');self.assertEqual({m['id'] for m in one},{m['id'] for m in two});msg=next(m for m in one if m['taskId']==self.task and m['kind']=='new_task')
        self.assertLess(abs((datetime.fromisoformat(msg['createdAt'].replace('Z',''))-now()).total_seconds()),60);self.assertEqual(msg['recipientId'],'teaching-s0');await self.call('POST','/teaching/messages/'+msg['id']+'/read');await self.login('s0');again=await self.call('GET','/teaching/messages');self.assertTrue(next(m for m in again if m['id']==msg['id'])['readAt'])
        await self.login('s1');await self.call('POST','/teaching/messages/'+msg['id']+'/read',status=404);self.assertNotIn(msg['id'],{m['id'] for m in await self.call('GET','/teaching/messages')})
        await self.login('t1');sent=await self.call('GET','/teaching/messages?box=sent');self.assertTrue(any(m['id']==msg['id'] for m in sent))
        await self.login('t2');self.assertNotIn(msg['id'],{m['id'] for m in await self.call('GET','/teaching/messages?box=sent')})
    async def test_supplement_lifecycle_targets_privacy_and_feedback(self):
        payload={'kind':'learning','content':'画出天平两边同时减去两个砝码后的状态。','studentIds':['teaching-s0'],'dueDate':'2026-12-10','requestKey':str(uuid.uuid4())}
        first=await self.call('POST','/teaching/tasks/'+self.task+'/supplements',payload,201);again=await self.call('POST','/teaching/tasks/'+self.task+'/supplements',payload,201);self.assertEqual(first['id'],again['id']);self.assertFalse(again['created']);sid=first['id']
        await self.login('s1');self.assertEqual(await self.call('GET','/teaching/tasks/'+self.task+'/supplements'),[])
        platform=await self.call('GET','/platform');self.assertNotIn(sid,{s['id'] for s in platform['supplements']});await self.call('POST','/teaching/supplements/'+sid+'/start',{},404)
        await self.login('s0');await self.call('POST','/teaching/supplements/'+sid+'/start',{});await self.login('t1');await self.call('POST','/teaching/supplements/'+sid+'/cancel',{},409)
        await self.login('s0');await self.call('POST','/teaching/supplements/'+sid+'/submit',{'response':'两边同时拿走两个砝码，仍然平衡。'});await self.call('POST','/teaching/supplements/'+sid+'/submit',{'response':'不覆盖第一次说明'})
        with SessionLocal() as db:
            self.assertFalse(db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='teaching-s0')).completed)
            self.assertEqual(db.get(SupplementRecipient,(sid,'teaching-s0')).response,'两边同时拿走两个砝码，仍然平衡。')
        await self.login('t1');await self.call('PUT','/teaching/supplements/'+sid+'/students/teaching-s0/feedback',{'feedback':'说明清楚，再写出等式。'})
        await self.login('s0');items=await self.call('GET','/teaching/tasks/'+self.task+'/supplements');self.assertEqual(items[0]['recipients'][0]['feedback'],'说明清楚，再写出等式。')
        await self.login('s1');self.assertFalse(any(m['objectId']==sid for m in await self.call('GET','/teaching/messages')))
    async def test_note_correction_cancel_and_legacy_notes(self):
        sid=(await self.call('POST','/teaching/tasks/'+self.task+'/supplements',{'kind':'correction','content':'订正移项符号，并说明两边同时做的运算。','requestKey':str(uuid.uuid4())},201))['id']
        await self.call('POST','/teaching/supplements/'+sid+'/cancel')
        note=(await self.call('POST','/teaching/tasks/'+self.task+'/supplements',{'kind':'note','content':'明天带直尺。','requestKey':str(uuid.uuid4())},201))['id']
        with SessionLocal.begin() as db:db.add(SupplementalInstruction(id='old-'+uuid.uuid4().hex[:30],task_id=self.task,teacher_id='teaching-t1',content='旧版补充说明'))
        await self.login('s0');items=await self.call('GET','/teaching/tasks/'+self.task+'/supplements');self.assertTrue(any(i['content']=='旧版补充说明' for i in items))
        for ident in [sid,note]:await self.call('POST','/teaching/supplements/'+ident+'/start',{},409)
        self.assertTrue(any(m['kind']=='correction' and m['objectId']==sid for m in await self.call('GET','/teaching/messages')))
    async def test_publish_snapshot_repeat_and_feedback_notification(self):
        data=self.fx['data'];draft={'goal':data['goal'],'blocks':copy.deepcopy(data['blocks']),'questions':copy.deepcopy(data['questions']),'dueDate':'','lessonSnapshot':{**data,'versionId':self.fx['lesson'].replace('-lesson','-version')}}
        payload={'classroomId':self.room,'lessonId':self.fx['lesson'],'lessonDraft':draft,'idempotencyKey':str(uuid.uuid4())}
        first=await self.call('POST','/tasks/publish',payload,201);second=await self.call('POST','/tasks/publish',payload,201);self.assertEqual(first['taskId'],second['taskId']);self.assertFalse(second['created'])
        with SessionLocal() as db:
            task=db.get(LearningTask,first['taskId']);self.assertEqual(task.classroom_id,self.room);snapshot=copy.deepcopy(task.snapshot);rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==task.id,StudentRecord.student_id=='teaching-s0'));rid=rec.id
        draft['goal']='修改草稿不改快照'
        await self.call('PUT','/records/'+rid+'/feedback',{'feedback':'两边要同时减去相同数。'})
        await self.login('s0');messages=await self.call('GET','/teaching/messages');self.assertTrue(any(m['kind']=='feedback' and m['taskId']==first['taskId'] for m in messages))
        with SessionLocal() as db:self.assertEqual(db.get(LearningTask,first['taskId']).snapshot,snapshot)
    async def test_original_learning_submit_retry_keeps_first_time_and_single_message(self):
        await self.login('s0')
        await self.call('POST','/records/'+self.task+'/submit',{},422)
        with SessionLocal.begin() as db:
            rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='teaching-s0'))
            task=db.get(LearningTask,self.task);rec.drafts={'blocks':{b['id']:{'completed':True,'explanation':'两边共同变化'} for b in task.snapshot['blocks'] if b['type'] not in ('practice','check')}}
        for i,question in enumerate(self.fx['data']['questions'][:4]):
            if i==0:await self.call('POST','/curriculum/tasks/'+self.task+'/questions/0/hint',{})
            result=await self.call('POST','/records/'+self.task+'/attempts',{'question':i,'answer':question['answer'],'reason':'两边同时进行相同运算。'},201);self.assertTrue(result['correct'])
        first=await self.call('POST','/records/'+self.task+'/submit',{});second=await self.call('POST','/records/'+self.task+'/submit',{});self.assertEqual(first['submittedAt'],second['submittedAt'])
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(BusinessMessage).where(BusinessMessage.task_id==self.task,BusinessMessage.kind=='submission',BusinessMessage.sender_id=='teaching-s0')),1)
            rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='teaching-s0'));attempts=db.scalars(select(Attempt).where(Attempt.record_id==rec.id).order_by(Attempt.question)).all();self.assertTrue(attempts[0].helped);self.assertFalse(attempts[1].helped)
    async def test_concurrent_notification_reads_and_backfill_are_idempotent(self):
        await self.call('POST','/classrooms/'+self.room+'/members',{'studentId':'teaching-s10'},201)
        results=await asyncio.gather(*[self.c.post('/api/teaching/tasks/'+self.task+'/assign',json={'studentIds':['teaching-s10']}) for _ in range(2)])
        self.assertEqual(sorted(r.json()['created'] for r in results),[0,1])
        await self.login('s0')
        results=await asyncio.gather(*[self.c.get('/api/teaching/messages') for _ in range(3)])
        for r in results:self.assertEqual(r.status_code,200,r.text)
        with SessionLocal() as db:
            rows=db.scalars(select(BusinessMessage).where(BusinessMessage.task_id==self.task,BusinessMessage.recipient_id=='teaching-s0',BusinessMessage.kind=='overdue')).all();self.assertEqual(len(rows),1)
