import json,time,uuid,sys
from pathlib import Path
import httpx
root=Path('/root/Baxxhy/zhiwei/sczx');sys.path[:0]=[str(root/'backend-business'),str(root/'scripts')]
from sczx_business.math_tools import solve_text_equation
from install_unit_content import call
out=Path('/tmp/sczx-step16');f=json.loads((out/'private.json').read_text());tasks={r['sourceId']:r for r in json.loads((out/'tasks.json').read_text())['t1']};report={'startedAt':time.time(),'cases':[],'errors':[]}
def save():(out/'repair-unit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
def job(c,record,data):
 started=time.monotonic();j=call(c,'POST','/ai/jobs',{'capability':'text','recordId':record,'requestKey':uuid.uuid4().hex,'data':data})
 for _ in range(400):
  j=call(c,'GET','/ai/jobs/'+j['id'])
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.5)
 report['cases'].append({'wrongId':data['wrongId'],'mode':data['mode'],'phase':data.get('phase'),'seconds':round(time.monotonic()-started,3),'job':j});save();print(data['wrongId'],data['mode'],data.get('phase'),j['status'],flush=True)
 if j['status']!='succeeded':raise RuntimeError(j.get('error'))
 return j
with httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as c:
 c.post('/api/auth/login',json={'username':'unit-s0','password':f['password']});wrongs=call(c,'GET','/wrongs')
 for canonical,equation in [('lesson-equation','3z = 18'),('lesson-simple','x+7=12'),('lesson-application','3x+6=21')]:
  try:
   w=next(w for w in wrongs if w['taskId']==tasks[canonical]['taskId'] and w['prompt'].replace(' ','')==equation.replace(' ',''));base={'wrongId':w['id'],'remediation':True};rec=w['recordId'];analysis=job(c,rec,{**base,'mode':'analysis','prompt':'请只依据当前课时、原答0和我的解释分析可能错误；不要把推测当能力结论。'})
   call(c,'PUT','/wrongs/'+w['id'],{'cause':analysis['result']['cause'],'causeConfirmed':True})
   guidance=job(c,rec,{**base,'mode':'guidance','strategy':'hint','parentJobId':analysis['id'],'prompt':'请给一步针对当前错误的提示，先不公布原题答案。'})
   for phase in ['practice','retest']:
    variant=job(c,rec,{**base,'mode':'variant','phase':phase,'prompt':'生成与本题运算结构一致、数值和解不同的新题；原题是'+equation+'，注意非零条件。'})
    eq=variant['result']['variant']['equation'];solved,ok=solve_text_equation(eq);assert ok
    result=call(c,'POST','/wrongs/'+w['id']+'/attempts',{'variantJobId':variant['id'],'answer':solved.split('=',1)[1],'reason':'工程验收：针对实际新题写出共同运算并代回。','requestKey':uuid.uuid4().hex})
    assert result['correct'],result;report['cases'].append({'wrongId':w['id'],'phase':phase,'actualVariant':eq,'actualAnswer':result['answer'],'attempt':result});save()
   final=call(c,'GET','/wrongs/'+w['id']);assert final['status']=='retest_passed',final;assert final['answer']=='0';report['cases'].append({'lesson':canonical,'wrongId':w['id'],'originalAnswerRetained':True,'finalStatus':final['status'],'sourceTask':w['taskId']});save()
  except Exception as e:report['errors'].append({'lesson':canonical,'error':str(e)});save();print('ERROR',canonical,str(e),flush=True)
report['completedAt']=time.time();save()
if report['errors']:sys.exit(1)
