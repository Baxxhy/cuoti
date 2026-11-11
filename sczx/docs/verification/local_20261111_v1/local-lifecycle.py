import json,subprocess,httpx,time
from pathlib import Path
out=Path('/tmp/sczx-local-final');root=Path.cwd();report={'at':time.time(),'checks':[]}
def cli(*args):
 start=time.monotonic();r=subprocess.run([str(root/'start-local.sh'),*args],capture_output=True,text=True);assert r.returncode==0,r.stderr;report['checks'].append({'command':' '.join(args),'seconds':round(time.monotonic()-start,3),'output':r.stdout.strip()});return r.stdout
def read():
 accounts=json.loads((root/'backend-business/var/local/accounts.json').read_text());a=next(a for a in accounts if a['username']=='handoff-s1')
 with httpx.Client(base_url='http://127.0.0.1:8099') as c:
  assert c.post('/api/auth/login',json={'username':a['username'],'password':a['password']}).status_code==200
  progress=c.get('/api/units/unit-equation/progress').json();assert progress['completed']==5;return progress
before=read();cli('start');cli('stop');cli('start');assert read()['completed']==5;backup=json.loads(cli('backup'));cli('restore','--archive',backup['backup']);assert read()['completed']==5;cli('doctor');report['unitBeforeAndAfter']=before;report['passed']=True;(out/'local-lifecycle.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('local double-start, web+MySQL stop/restart, backup/new-target restore, accounts and unit5/5 PASS')
