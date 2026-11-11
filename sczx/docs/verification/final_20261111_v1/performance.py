import json,httpx,time,statistics
from pathlib import Path
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());r={'environment':'fixed release7731bf8; MySQL23320; loopbackTLS9443; host shared; one sequential browser/operator; classroom2 actual students','concurrency':1,'api':[]}
with httpx.Client(base_url='https://127.0.0.1:9443',verify=f['tlsCert'],timeout=30) as c:
 c.post('/api/auth/login',json={'username':'handoff-s1','password':f['password']})
 for path in ['/api/health','/api/platform','/api/memory','/api/units/unit-equation/progress','/api/exams']:
  times=[]
  for _ in range(5):
   t=time.monotonic();v=c.get(path);assert v.status_code==200;times.append(round((time.monotonic()-t)*1000,2))
  r['api'].append({'path':path,'samplesMs':times,'medianMs':statistics.median(times),'maxMs':max(times)})
models=json.loads((out/'model-flows.json').read_text());r['realModelCalls']=[{'kind':x['key'],'seconds':x['seconds'],'status':x['job']['status']} for x in models['calls']];r['uploadSeconds']=models['uploadSeconds'];r['businessMetricsSource']='exam-class-flows.json metrics: exam draft/submit and live answer/read; no load-test claim';(out/'performance.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print('real API timings and actual model timings recorded')
