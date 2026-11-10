"""Controlled interruption plus real service retry; actual in-flight membership revocation."""
import os,sys,json,asyncio,uuid,time
from pathlib import Path
fx=json.loads(Path('/tmp/sczx-step12/browser-private.json').read_text());os.environ['SCZX_DATABASE_URL']=fx['url'];sys.path.insert(0,'backend-business')
import httpx
from sqlalchemy import select,func
from sczx_business.database import SessionLocal,engine
from sczx_business.models import Account,StudentRecord,ModelJob,ModelRun,HelpRecord
from sczx_business.tutoring import prepare
from sczx_business.model_jobs import recover_interrupted
assert engine.url.database.startswith('sczx_test_')
report={'database':engine.url.database,'controlledStates':[],'liveChecks':[]}
async def login(client,name):
 r=await client.post('/api/auth/login',json={'username':'teaching-'+name,'password':fx['password']});r.raise_for_status()
async def detail(client,id,terminal=True):
 for _ in range(1500):
  r=await client.get('/api/ai/jobs/'+id);r.raise_for_status();value=r.json()
  if terminal and value['status'] in ('succeeded','failed','cancelled'):return value
  if not terminal and value['status']=='running' and value['step']=='正在生成指导':return value
  await asyncio.sleep(.15)
 raise RuntimeError('wait exceeded')
async def main():
 async with httpx.AsyncClient(base_url='http://127.0.0.1:8001',timeout=15) as student,httpx.AsyncClient(base_url='http://127.0.0.1:8001',timeout=15) as teacher:
  await login(student,'s2');await login(teacher,'t1')
  with SessionLocal.begin() as db:
   assert db.scalar(select(func.count()).select_from(ModelJob).where(ModelJob.status=='running'))==0
   owner=db.get(Account,'teaching-s2');rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id=='browser-t01',StudentRecord.student_id==owner.id));data=prepare(db,owner,rec,{'strategy':'hint','prompt':'只给下一步提示，比较两边共同加相同数。','question':0,'blockId':'eq-practice'})
   ident='job-'+uuid.uuid4().hex;rid='run-'+uuid.uuid4().hex;job=ModelJob(id=ident,owner_id=owner.id,record_id=rec.id,capability='text',request_key=uuid.uuid4().hex,input_hash=uuid.uuid4().hex,input=data,status='running',attempt_number=1);db.add(job);db.flush();db.add(ModelRun(id=rid,job_id=ident,number=1,status='running'))
  recover_interrupted()
  first=(await student.get('/api/ai/jobs/'+ident)).json();assert first['status']=='failed' and first['runs'][0]['status']=='failed';report['controlledStates'].append({'name':'模拟服务中断，调用真实恢复函数','job':first})
  r=await student.post('/api/ai/jobs/'+ident+'/retry');assert r.status_code==200
  result=await detail(student,ident);assert result['status']=='succeeded',result.get('error');report['liveChecks'].append({'name':'中断恢复后的真实Codex手动重试','job':result})
  # Repeat input with the same request key: one queued/executing job and one help request.
  await login(student,'s1');platform=(await student.get('/api/platform')).json();record=platform['records']['browser-t01']['id'];key=uuid.uuid4().hex
  payload={'capability':'text','recordId':record,'requestKey':key,'data':{'guidance':True,'strategy':'hint','question':0,'blockId':'eq-practice','prompt':'我想理解为什么两边要一起加同一个数，请只给一个提示。'}}
  a=await student.post('/api/ai/jobs',json=payload);a.raise_for_status();ident=a.json()['id'];b=await student.post('/api/ai/jobs',json=payload);assert b.json()['id']==ident
  await detail(student,ident,False);await asyncio.sleep(.3)
  removed=await teacher.delete('/api/teaching/classes/browser-c0/members/teaching-s1');removed.raise_for_status()
  value=await detail(student,ident);assert value['status']=='failed' and '已移出班级' in value['error'],value
  retry=await student.post('/api/ai/jobs/'+ident+'/retry');new=await student.post('/api/ai/jobs',json={**payload,'requestKey':uuid.uuid4().hex});assert retry.status_code==403 and new.status_code==403
  with SessionLocal() as db:
   help=db.get(HelpRecord,'help-'+ident[4:]);assert help.kind=='指导请求';assert db.get(ModelJob,ident).result is None
  report['liveChecks'].append({'name':'真实运行中移出、结果不写回、历史可读、新建与重试403','job':value,'repeatJobId':b.json()['id'],'retryStatus':retry.status_code,'newStatus':new.status_code})
  # Explicitly ending a queued turn retains the job and stops further UI guidance.
  await login(student,'s2');platform=(await student.get('/api/platform')).json();rec=platform['records']['browser-t01']['id'];r=await student.post('/api/ai/jobs',json={'capability':'text','recordId':rec,'requestKey':uuid.uuid4().hex,'data':{'guidance':True,'strategy':'hint','question':1,'blockId':'eq-practice','prompt':'先比较等式两边。'}});r.raise_for_status();id=r.json()['id'];r=await student.post('/api/ai/jobs/'+id+'/stop');assert r.json()['status']=='cancelled';later=(await student.get('/api/ai/jobs/'+id)).json();assert later['status']=='cancelled';report['liveChecks'].append({'name':'结束一轮且保留历史','job':later})
 report['passed']=True
try:asyncio.run(main())
finally:Path('/tmp/sczx-step12/faults.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('controlled interruption + real retry + live removal + idempotence + stop: PASS')
