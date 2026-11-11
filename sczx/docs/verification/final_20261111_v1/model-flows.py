import json,time,uuid,sys,copy
from pathlib import Path
import httpx
sys.path[:0]=['scripts','backend-business'];from install_unit_content import call
from sczx_business.math_tools import solve_text_equation
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());report=json.loads((out/'model-flows.json').read_text()) if (out/'model-flows.json').exists() else {'startedAt':time.time(),'calls':[]}
def save():(out/'model-flows.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
def client(u):
 c=httpx.Client(base_url='https://127.0.0.1:9443',verify=f['tlsCert'],timeout=180);assert c.post('/api/auth/login',json={'username':'handoff-'+u,'password':f['password']}).status_code==200;return c
s=client('s1');t=client('t1')
def job(c,key,body):
 old=next((x['job'] for x in report['calls'] if x['key']==key and x['job']['status']=='succeeded'),None)
 if old:return old
 started=time.monotonic();failed=next((x['job'] for x in reversed(report['calls']) if x['key']==key and x['job']['status']=='failed'),None);j=call(c,'POST','/ai/jobs/'+failed['id']+'/retry') if failed else call(c,'POST','/ai/jobs',{'requestKey':uuid.uuid4().hex,**body})
 for _ in range(480):
  j=call(c,'GET','/ai/jobs/'+j['id'])
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.5)
 report['calls'].append({'key':key,'seconds':round(time.monotonic()-started,3),'job':j});save();print(key,j['status'],flush=True)
 if j['status']!='succeeded':raise RuntimeError(key+': '+j.get('error',''))
 return j
agent=job(t,'agent',{'capability':'lesson_agent','data':{'lessonId':f['lessons'][1],'task':'纠正机械移项：保留本课题目，要求两边同时运算、除数非零并代回。','taskType':'misconception','constraints':'使用已有来源。只写具体教师提问和学生动作，保持活动ID和题目不变。'}});f['agentJob']=agent['id']
hint=job(s,'text-hint',{'capability':'text','recordId':f['recordId'],'data':{'guidance':True,'question':0,'strategy':'hint','prompt':'我想直接改变左边。先给一步提示，不给答案。'}})
# Original picture is synthetic self-authored input. No real student uploads copied into report.
p=out/'original-question.png'
started=time.monotonic()
with p.open('rb') as stream:r=s.post('/api/files',files={'file':('original-question.png',stream,'image/png')})
assert r.status_code==201;file=r.json();report['uploadSeconds']=round(time.monotonic()-started,3)
ocr=job(s,'ocr',{'capability':'ocr','recordId':f['recordId'],'fileId':file['id'],'data':{'question':0}})
job(s,'ocr-confirmed',{'capability':'text','recordId':f['recordId'],'data':{'guidance':True,'question':0,'strategy':'hint','prompt':'工程验收已对照原图核对，给下一步提示。','ocrJobId':ocr['id'],'confirmed':True,'recognizedText':'x - 3 = 5','confirmedEquation':'x - 3 = 5'}})
w=f['wrong'];base={'wrongId':w['id'],'remediation':True};analysis=job(s,'wrong-analysis',{'capability':'text','recordId':f['recordId'],'data':{**base,'mode':'analysis','prompt':'只依据本题原答0及原解释分析错误；不推断整体能力。'}});call(s,'PUT','/wrongs/'+w['id'],{'cause':analysis['result']['cause'],'causeConfirmed':True})
job(s,'wrong-guidance',{'capability':'text','recordId':f['recordId'],'data':{**base,'mode':'guidance','strategy':'hint','parentJobId':analysis['id'],'prompt':'给一步操作提示，暂不公布答案。'}})
for phase in ['practice','retest']:
 if phase in report:continue
 variant=job(s,'wrong-'+phase,{'capability':'text','recordId':f['recordId'],'data':{**base,'mode':'variant','phase':phase,'prompt':'生成与原题结构相同、数字及解不同的方程。保留除数非零条件。'}});solved,ok=solve_text_equation(variant['result']['variant']['equation']);assert ok
 # New attempts remain actual HTTP records; solver supplies engineering input, not learner evidence.
 attempt=call(s,'POST','/wrongs/'+w['id']+'/attempts',{'variantJobId':variant['id'],'answer':solved.split('=',1)[1],'reason':'工程自动验收：求解新方程并代回核验。','requestKey':uuid.uuid4().hex});assert attempt['correct']
 report[phase]={'equation':variant['result']['variant']['equation'],'attempt':attempt};save()
final=call(s,'GET','/wrongs/'+w['id']);assert final['answer']=='0' and final['status']=='retest_passed';report['wrongFinal']=final;report['memory']=call(s,'GET','/memory');report['completedAt']=time.time();save()
for p in [out/'private.json',Path(f['base'])/'private.json']:v=json.loads(p.read_text());v['agentJob']=agent['id'];p.write_text(json.dumps(v));p.chmod(0o600)
print('actual luna/low Agent/text/OCR/remediation PASS')
