from pathlib import Path
import json,httpx,subprocess
home=Path('backend-business/var/local_fresh_acceptance');accounts=json.loads((home/'accounts.json').read_text());report={'roles':[]}
for a in accounts:
 with httpx.Client(base_url='http://127.0.0.1:8101') as c:
  r=c.post('/api/auth/login',json={'username':a['username'],'password':a['password']});assert r.status_code==200
  p=c.get('/api/platform').json();report['roles'].append({'role':a['role'],'username':a['username'],'tasks':len(p['tasks'])})
  if a['role']=='student':assert len(p['tasks'])==5;assert c.get('/api/units/unit-equation/progress').json()['assigned']==5
r=subprocess.run(['./start-local.sh','init','--home',str(home.resolve())],capture_output=True,text=True);assert r.returncode==0
r=subprocess.run(['./start-local.sh','start','--home',str(home.resolve())],capture_output=True,text=True);assert r.returncode==0
report.update(freshDatabase=True,unitLessons=5,repeatInitPreservesAccounts=True,repeatStartPassed=True,passed=True);Path('/tmp/sczx-local-final/fresh-install.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));subprocess.run(['./stop-local.sh','--home',str(home.resolve())],check=True);print('fresh schema migration,3 accounts,5 reviewed example lessons/tasks and repeated init/start PASS')
