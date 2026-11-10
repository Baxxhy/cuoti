import unittest,os,sys,subprocess,uuid,secrets,copy,asyncio
from pathlib import Path
from datetime import datetime,timedelta
import httpx
from sqlalchemy import select
from sczx_business.database import SessionLocal,engine
from sczx_business.models import Attempt,StudentRecord,LearningTask,HelpRecord,KnowledgePoint,WrongQuestion,RepairAttempt,ClassMember,LearningMemoryChange,Account
from sczx_business.main import app
from sczx_business.learning_memory import collect,build,related_memory
from test_teaching_mysql import fixture,create_accounts
@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class MemoryMySQLTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  assert engine.url.database.startswith('sczx_test_');subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True);cls.password=secrets.token_urlsafe(24);create_accounts(cls.password,'memory-')
 async def asyncSetUp(self):
  self.fx=fixture('m-'+uuid.uuid4().hex[:8],'memory-');self.task=self.fx['tasks'][0];self.kp=self.fx['lesson'].replace('-lesson','-kp');self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test');await self.login('s0')
  with SessionLocal.begin() as db:self.rid=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.task,StudentRecord.student_id=='memory-s0')).id
 async def asyncTearDown(self):await self.c.aclose()
 async def login(self,name):
  self.c.cookies.clear();r=await self.c.post('/api/auth/login',json={'username':'memory-'+name,'password':self.password});self.assertEqual(r.status_code,200,r.text)
 def attempt(self,answer='8',correct=True,helped=False,question=0,record=None,when=None,verification=None):
  with SessionLocal.begin() as db:
   row=Attempt(id='attempt-'+uuid.uuid4().hex,record_id=record or self.rid,question=question,answer=answer,reason='原始过程',correct=correct,helped=helped,verification=verification or {'status':'verified' if correct else 'inconsistent','correct':correct},created_at=when or datetime.utcnow());db.add(row);return row.id
 async def get(self,query=''):
  r=await self.c.get('/api/memory'+query);self.assertEqual(r.status_code,200,r.text);return r.json()
 async def test_stable_ids_aggregation_and_help_separation(self):
  aid=self.attempt(helped=True);before=await self.get();after=await self.get();self.assertEqual(before['revision'],after['revision']);item=next(i for i in before['items'] if i['id']==self.kp);self.assertEqual(item['state']['helpedCorrect'],1);self.assertEqual(item['state']['independentCorrect'],0)
  with SessionLocal() as db:other=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.fx['tasks'][1],StudentRecord.student_id=='memory-s0')).id
  self.attempt(question=1,record=other);item=next(i for i in (await self.get())['items'] if i['id']==self.kp);self.assertEqual(item['state']['evidenceCount'],2)
  hid='help-'+uuid.uuid4().hex
  with SessionLocal.begin() as db:db.add(HelpRecord(id=hid,record_id=self.rid,question=0,kind='原始帮助',message='不可被聚合保存覆盖的原始提示'))
  r=await self.c.put('/api/platform',json={'data':{'records':{self.task:{'drafts':{},'helps':[{'id':hid,'kind':'改写','message':'过期客户端覆盖'}]}}}});self.assertEqual(r.status_code,200,r.text)
  with SessionLocal() as db:self.assertEqual(db.get(HelpRecord,hid).message,'不可被聚合保存覆盖的原始提示')
 async def test_teacher_scope_cross_student_and_removal(self):
  self.attempt();await self.login('s1');self.assertEqual((await self.c.get('/api/memory?studentId=memory-s0')).status_code,404)
  await self.login('t2');self.assertEqual((await self.c.get('/api/memory?studentId=memory-s0')).status_code,404)
  await self.login('t1');value=await self.get('?studentId=memory-s0&classId='+self.fx['classes'][0]);self.assertTrue(value['items'])
  with SessionLocal.begin() as db:db.delete(db.get(ClassMember,(self.fx['classes'][0],'memory-s0')))
  self.assertEqual((await self.c.get('/api/memory?studentId=memory-s0&classId='+self.fx['classes'][0])).status_code,404)
  await self.login('s0');self.assertTrue((await self.get())['items'])
 async def test_correction_append_only_conflict_and_replay(self):
  aid=self.attempt();new_kp=self.kp+'-new'
  with SessionLocal.begin() as db:db.add(KnowledgePoint(id=new_kp,name='新知识点',prerequisites=[]))
  await self.login('t1');value=await self.get('?studentId=memory-s0');e=next(i for i in value['items'] if i['id']==self.kp)['evidence'][0];body={'studentId':'memory-s0','knowledgeId':self.kp,'kind':'knowledge_correction','evidenceId':e['evidenceId'],'knowledgeIds':[new_kp],'reason':'题目实际考查另一项','requestKey':uuid.uuid4().hex,'expectedRevision':value['revision']}
  r=await self.c.post('/api/memory/changes',json=body);self.assertEqual(r.status_code,201,r.text);self.assertEqual((await self.c.post('/api/memory/changes',json=body)).json()['id'],r.json()['id']);fresh=await self.get('?studentId=memory-s0');self.assertEqual(next(i for i in fresh['items'] if i['id']==new_kp)['state']['independentCorrect'],1)
  stale={**body,'requestKey':uuid.uuid4().hex};self.assertEqual((await self.c.post('/api/memory/changes',json=stale)).status_code,409)
  with SessionLocal() as db:self.assertEqual(db.get(Attempt,aid).answer,'8');self.assertEqual(db.get(Attempt,aid).reason,'原始过程');self.assertEqual(len(db.scalars(select(LearningMemoryChange).where(LearningMemoryChange.student_id=='memory-s0',LearningMemoryChange.source_event_id=='attempt:'+aid)).all()),1)
 async def test_current_one_layer_only_memory_and_budget(self):
  self.attempt();base=self.kp+'-base';grand=self.kp+'-grand'
  with SessionLocal.begin() as db:
   db.get(KnowledgePoint,self.kp).prerequisites=[base];db.add(KnowledgePoint(id=base,name='前置',prerequisites=[grand]));db.add(KnowledgePoint(id=grand,name='再前置',prerequisites=[]));db.flush()
   rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==self.fx['tasks'][1],StudentRecord.student_id=='memory-s0'));actor=db.get(Account,'memory-s0');memory=related_memory(db,actor,rec,[self.kp]);self.assertTrue(memory);self.assertTrue(all(e['knowledgeId'] in [self.kp,base] and e['sourceType']!='help' for e in memory));self.assertLessEqual(len(memory),6);self.assertNotIn('answer',memory[0])
 async def test_snooze_idempotent_and_new_evidence_reopens(self):
  self.attempt(correct=False,answer='2');value=await self.get();r=next(i['recommendation'] for i in value['items'] if i['id']==self.kp);self.assertIsNotNone(r)
  body={'kind':'snooze','knowledgeId':self.kp,'expectedRevision':value['revision'],'requestKey':uuid.uuid4().hex};a=await self.c.post('/api/memory/changes',json=body);self.assertEqual(a.status_code,201,a.text);self.assertEqual((await self.c.post('/api/memory/changes',json=body)).json()['id'],a.json()['id']);self.assertFalse(any(r['knowledgeId']==self.kp for r in (await self.get())['recommendations']))
  self.attempt(correct=False,question=1,answer='0',when=datetime.utcnow()+timedelta(seconds=1));self.assertTrue(any(r['knowledgeId']==self.kp for r in (await self.get())['recommendations']))
 async def test_legacy_and_unknown_never_count_as_independent(self):
  self.attempt(verification={'status':'unverified'},correct=False);wid='wrong-'+uuid.uuid4().hex
  with SessionLocal.begin() as db:db.add(WrongQuestion(id=wid,owner_id='memory-s0',record_id=None,prompt='x=1',details={'knowledgeIds':[self.kp]}));db.flush();db.add(RepairAttempt(id='repair-'+uuid.uuid4().hex,wrong_id=wid,answer='7',correct=True))
  item=next(i for i in (await self.get())['items'] if i['id']==self.kp);self.assertEqual(item['state']['independentCorrect'],0);self.assertEqual(item['state']['legacyCount'],1)
 async def test_concurrent_change_replay_and_different_edits_conflict(self):
  self.attempt();value=await self.get();body={'kind':'snooze','knowledgeId':self.kp,'expectedRevision':value['revision'],'requestKey':uuid.uuid4().hex};rows=await asyncio.gather(*[self.c.post('/api/memory/changes',json=body) for _ in range(2)]);self.assertTrue(all(r.status_code==201 for r in rows),[r.text for r in rows]);self.assertEqual(rows[0].json()['id'],rows[1].json()['id'])
 async def test_cross_class_same_student_filters_other_teacher_and_personal(self):
  from sczx_business.teaching import assign
  with SessionLocal.begin() as db:
   db.add(ClassMember(classroom_id=self.fx['classes'][2],student_id='memory-s9'));db.flush()
   for tid in self.fx['tasks'][4:]:assign(db,db.get(LearningTask,tid),'memory-s9')
   records=db.scalars(select(StudentRecord).where(StudentRecord.student_id=='memory-s9')).all()
  for r in records:self.attempt(answer='teacher-only-'+r.task_id,record=r.id)
  await self.login('t1');first=await self.get('?studentId=memory-s9&classId='+self.fx['classes'][0]);self.assertTrue(first['items']);events=[e for i in first['items'] for e in i['evidence']];self.assertTrue(all(e['classId'] in self.fx['classes'][:2] for e in events))
  await self.login('t2');second=await self.get('?studentId=memory-s9&classId='+self.fx['classes'][2]);events=[e for i in second['items'] for e in i['evidence']];self.assertTrue(all(e['classId']==self.fx['classes'][2] for e in events))
 async def test_reads_do_not_create_model_jobs_or_repeat_facts(self):
  from sczx_business.models import ModelJob
  self.attempt()
  with SessionLocal() as db:before=len(db.scalars(select(ModelJob.id)).all())
  a=await self.get();b=await self.get();self.assertEqual(a['revision'],b['revision']);self.assertEqual(a['recommendations'],b['recommendations'])
  with SessionLocal() as db:self.assertEqual(len(db.scalars(select(ModelJob.id)).all()),before)
 async def test_prerequisite_one_layer_recommendation_requires_actual_errors(self):
  current=self.kp+'-next';self.attempt(correct=False,answer='2');self.attempt(correct=False,answer='3',question=1)
  with SessionLocal.begin() as db:
   db.add(KnowledgePoint(id=current,name='后续知识',prerequisites=[self.kp]));task=db.get(LearningTask,self.fx['tasks'][1]);snapshot=copy.deepcopy(task.snapshot);snapshot['knowledgeIds']=[current];snapshot['lessonSnapshot']['knowledgeIds']=[current];task.snapshot=snapshot
   questions=copy.deepcopy(task.questions)
   for q in questions:q['knowledgeIds']=[current]
   task.questions=questions
  item=next(i for i in (await self.get())['items'] if i['id']==current);self.assertEqual(item['recommendation']['action'],'foundation');self.assertEqual(item['recommendation']['prerequisiteId'],self.kp)
 async def test_teacher_review_instruction_retires_only_after_new_actual_answer(self):
  self.attempt(correct=False,answer='2');await self.login('t1');current=await self.get('?studentId=memory-s0');item=next(i for i in current['items'] if i['id']==self.kp);event=next(e for e in item['evidence'] if e['sourceType']=='attempt');target=item['lessons'][0]['target']
  body={'kind':'review_content','studentId':'memory-s0','knowledgeId':self.kp,'evidenceId':event['evidenceId'],'reason':'先回看原课，再实际作答','target':target,'expectedRevision':current['revision'],'requestKey':uuid.uuid4().hex};r=await self.c.post('/api/memory/changes',json=body);self.assertEqual(r.status_code,201,r.text);value=await self.get('?studentId=memory-s0');self.assertEqual(next(i for i in value['items'] if i['id']==self.kp)['recommendation']['action'],'teacher_review')
  target_id=target.split('task=')[1]
  with SessionLocal() as db:record=db.scalar(select(StudentRecord).where(StudentRecord.task_id==target_id,StudentRecord.student_id=='memory-s0')).id
  self.attempt(record=record,question=1)
  value=await self.get('?studentId=memory-s0');self.assertNotEqual((next(i for i in value['items'] if i['id']==self.kp)['recommendation'] or {}).get('action'),'teacher_review');self.assertTrue(any(a['kind']=='review_content' for a in value['audit']))
