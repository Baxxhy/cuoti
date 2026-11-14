import asyncio,json,uuid,os,copy,secrets
from pathlib import Path
import httpx
from sqlalchemy import select,func
from sczx_business.database import SessionLocal
from sczx_business.models import TeachingCase,CaseVersion,StudentRecord,LearningTask,LessonDraft,Course
from sczx_business.curated_resources import digest,load_bundle
OUT=Path(__file__).resolve().parents[2]/'docs/verification/new_accounts_20261115_v1';B=os.environ.get('SCZX_TEST_API','http://127.0.0.1:8104')
assert os.environ.get('SCZX_RUN_REAL_NEW_ACCOUNTS')=='1','Explicit real-model isolated acceptance only'
from sczx_business.database import engine
assert engine.url.database.startswith('sczx_test_')
assert os.environ.get('SCZX_NEW_ACCOUNT_PRIVATE'),'Set ignored private account output path'
PASSWORD=secrets.token_urlsafe(24)
async def run():
 result={};private={};clients=[]
 with SessionLocal() as db:before={r.id:digest(r.data) for r in db.scalars(select(CaseVersion)).all()}
 async def req(c,m,p,data=None,status=200):
  r=await c.request(m,B+'/api'+p,json=data);assert r.status_code==status,(p,r.status_code,r.text[:500]);return r.json()
 async def reg(role):
  c=httpx.AsyncClient(timeout=30);clients.append(c);name='r3'+role+uuid.uuid4().hex[:8];a={'username':name,'password':PASSWORD,'displayName':'全新'+role,'role':role};await req(c,'POST','/auth/register',a,201);private[role]=a;return c
 async def job(c,cap,data,**extra):
  j=await req(c,'POST','/ai/jobs',{'capability':cap,'data':data,'requestKey':uuid.uuid4().hex,**extra},201)
  for i in range(180):
   j=await req(c,'GET','/ai/jobs/'+j['id'])
   if j['status'] in ['succeeded','failed','cancelled']:break
   await asyncio.sleep(2)
  assert j['status']=='succeeded',(j['id'],j.get('error'));return j
 s=await reg('student');student_account=copy.deepcopy(private['student']);t=await reg('teacher');other=await reg('student');private['other']=private['student'];private['student']=student_account
 # Keep distinct login identity from cookies via /me, private account corrected below.
 rows=load_bundle()[0]['entries'];en=next(r for r in rows if r['topic']=='一般过去时')
 w=await req(s,'POST','/wrongs',{'prompt':'I goed to school yesterday. 请引导我检查时态。','answer':'I goed to school yesterday.','reason':'我以为都加ed','subject':'英语','grade':en['grade'],'knowledgeIds':[en['knowledgeId']],'requestKey':uuid.uuid4().hex},201);assert w['recordId'] is None and w['taskId'] is None
 g=await job(s,'text',{'wrongId':w['id'],'mode':'guidance','strategy':'hint','prompt':en['experience']['difficulty']});result['text']={'wrongId':w['id'],'jobId':g['id'],'result':g['result'],'recordId':g['recordId']}
 with open(OUT/'source-question.png','rb') as f:r=await s.post(B+'/api/files',files={'file':('question.png',f,'image/png')})
 assert r.status_code==201,r.text;f=r.json();ocr=await job(s,'ocr',{'wrongCapture':True},fileId=f['id']);print('OCR',ocr['result'],flush=True);assert ocr['result']['text'].replace(' ','').strip()=='3x=18'
 image=await req(s,'POST','/wrongs',{'prompt':ocr['result']['text'],'equation':'3x=18','answer':'5','reason':'不知道怎么算','subject':'数学','grade':'七年级','knowledgeIds':[],'fileId':f['id'],'ocrJobId':ocr['id'],'confirmed':True,'requestKey':uuid.uuid4().hex},201)
 ig=await job(s,'text',{'wrongId':image['id'],'mode':'guidance','strategy':'hint','prompt':'先给我提示'});analysis=await job(s,'text',{'wrongId':image['id'],'mode':'analysis'});variant=await job(s,'text',{'wrongId':image['id'],'mode':'variant','phase':'practice'})
 from sczx_business.math_tools import solve_text_equation
 print('variant',variant['result'],flush=True)
 equation=variant['result']['variant']['equation'];answer,valid=solve_text_equation(equation)
 # Solver returns solution text and validation flag in project helper.
 attempt=await req(s,'POST','/wrongs/'+image['id']+'/attempts',{'variantJobId':variant['id'],'answer':str(answer),'reason':'独立计算，两边同做相同运算','requestKey':uuid.uuid4().hex},201)
 result['image']={'wrongId':image['id'],'ocrJobId':ocr['id'],'guidanceJobId':ig['id'],'variant':variant['result'],'attempt':attempt}
 for resource in ['/wrongs/'+w['id'],'/ai/jobs/'+g['id'],'/files/'+f['id']]:
  r=await other.get(B+'/api'+resource);assert r.status_code in (403,404),(resource,r.status_code)
 result['isolation']='foreign wrong, model job, image denied'
 plan=await job(t,'lesson_agent',{'caseId':en['id'],'caseVersionId':'resver-'+en['id'][4:],'task':en['experience']['difficulty']+'，请设计教学活动。'})
 assert plan['input']['independent'];assert any(x['id']==en['id'] for x in plan['result']['experienceDecision']['selected']);edited=copy.deepcopy(plan['result']['editable']);edited['blocks'][0]['content']+='\n教师修改：请学生圈出时间依据。';saved=await req(t,'PUT','/ai/agent/'+plan['id']+'/draft',edited);assert saved['result']['editable']==edited
 result['teacher']={'jobId':plan['id'],'result':saved['result'],'independent':True}
 for c in [s,t]:
  me=await req(c,'GET','/auth/me');print('user',me,flush=True)
 # Durable reload via separate client with same session cookies; then explicit fresh login later in browser.
 assert (await req(s,'GET','/wrongs/'+w['id']))['answer']==w['answer'];assert (await req(t,'GET','/ai/jobs/'+plan['id']))['result']['editable']==edited
 with SessionLocal() as db:
  assert {r.id:digest(r.data) for r in db.scalars(select(CaseVersion)).all()}==before
  result['database']={m.__tablename__:db.scalar(select(func.count()).select_from(m)) for m in [StudentRecord,LearningTask,LessonDraft,Course]};assert all(x==0 for x in result['database'].values());result['database']['experienceVersionsUnchanged']=len(before)
 OUT.joinpath('api-chain.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));private['teacherJobs']=[plan['id']];privatePath=Path(os.environ['SCZX_NEW_ACCOUNT_PRIVATE']);privatePath.write_text(json.dumps(private));privatePath.chmod(0o600)
 for c in clients:await c.aclose()
asyncio.run(run())
