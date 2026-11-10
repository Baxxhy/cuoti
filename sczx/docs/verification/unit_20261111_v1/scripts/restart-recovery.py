import json,subprocess,time,uuid
from pathlib import Path
import httpx
fx=json.loads(Path('/tmp/sczx-step16/private.json').read_text());tasks=json.loads(Path('/tmp/sczx-step16/tasks.json').read_text());task=tasks['t1'][0]['taskId'];base='http://127.0.0.1:8087';report={'checks':[]}
with httpx.Client(base_url=base,timeout=30) as c:
 c.post('/api/auth/login',json={'username':'unit-s2','password':fx['password']});p=c.get('/api/platform').json();rec=next(r for r in p['records'].values() if r['taskId']==task);j=c.post('/api/ai/jobs',json={'capability':'text','requestKey':uuid.uuid4().hex,'recordId':rec['id'],'data':{'guidance':True,'question':2,'strategy':'hint','prompt':'先解释同除为什么必须非零，只给下一步提示。'}});assert j.status_code==201,j.text;j=j.json()
 for _ in range(40):
  state=c.get('/api/ai/jobs/'+j['id']).json()
  if state['status']=='running':break
  time.sleep(.1)
 assert state['status']=='running',state;report['before']=state
 subprocess.run(['/tmp/sczx-venv/bin/python','deploy/manage.py','stop','--env','/tmp/sczx-step16/release.env'],check=True)
 subprocess.run(['/tmp/sczx-venv/bin/python','deploy/manage.py','start','--env','/tmp/sczx-step16/release.env'],check=True)
 # Cookie/session remain valid after an actual process restart.
 for _ in range(50):
  state=c.get('/api/ai/jobs/'+j['id']).json()
  if state['status']=='failed':break
  time.sleep(.1)
 assert state['status']=='failed',state;report['afterRestart']=state
 retry=c.post('/api/ai/jobs/'+j['id']+'/retry');assert retry.status_code==200,retry.text
 for _ in range(180):
  state=c.get('/api/ai/jobs/'+j['id']).json()
  if state['status'] in ('succeeded','failed'):break
  time.sleep(1)
 assert state['status']=='succeeded',state;report['afterRetry']=state;p=c.get('/api/platform').json();rec=next(r for r in p['records'].values() if r['taskId']==task);helps=[h for h in rec['helps'] if h['id']==state['helpRecordId']];assert len(helps)==1;report['oneOriginalHelpRecord']=True
Path('/tmp/sczx-step16/restart-recovery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('actual restart -> interrupted -> manual retry success; same session and one help record')
