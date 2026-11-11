import json,subprocess,uuid,time,sys,importlib.util
from pathlib import Path
from sqlalchemy import create_engine,text
import httpx
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());base=Path(f['base']);s=importlib.util.spec_from_file_location('m','deploy/manage.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);cfg=m.configuration(f['demoEnv']);m.ROOT=Path(f['releaseRoot']);subprocess.run(['systemctl','stop',f['stagingUnit']],check=True);time.sleep(1)
def cmd(action,env,**params):
 args=[f['python'],'deploy/manage.py',action,'--env',str(env)]
 for k,v in params.items():args+=['--'+k,str(v)]
 p=subprocess.run(args,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 return json.loads(p.stdout)
try:
 backup=base/'backups'/('delivery-'+uuid.uuid4().hex[:6]);r=cmd('backup',f['demoEnv'],output=backup);db='sczx_test_delivery_'+uuid.uuid4().hex[:6];e=create_engine('mysql+pymysql://root:'+f['mysqlPassword']+'@127.0.0.1:23320/mysql')
 with e.begin() as c:c.execute(text('CREATE DATABASE '+db+' CHARACTER SET utf8mb4'))
 e.dispose();folder=base/'delivery-restore'/db;folder.mkdir(parents=True);v={**cfg,'SCZX_DATABASE_URL':'mysql+pymysql://root:'+f['mysqlPassword']+'@127.0.0.1:23320/'+db,'SCZX_STORAGE_DIR':str(folder/'uploads'),'SCZX_RELEASE_STATE':str(folder/'process'),'SCZX_LOG_DIR':str(folder/'logs'),'SCZX_RELEASE_PORT':'8097','SCZX_RELEASE_URL':'http://127.0.0.1:8097','SCZX_HEALTH_URL':'http://127.0.0.1:8097','SCZX_PUBLIC_URL':'http://127.0.0.1:8097','SCZX_COOKIE_SECURE':'false'};env=folder/'release.env';env.write_text('\n'.join(k+'='+v for k,v in v.items()));env.chmod(0o600);restored=cmd('restore',env,archive=backup);cmd('start',env)
 try:
  with httpx.Client(base_url='http://127.0.0.1:8097') as c:
   assert c.post('/api/auth/login',json={'username':'handoff-s1','password':f['password']}).status_code==200;p=c.get('/api/platform').json();assert all(p['records'][t['taskId']]['completed'] for t in f['tasks']);assert c.get('/api/units/unit-equation/progress',params={'classId':f['rooms'][0]}).json()['completed']==5;assert c.get('/api/wrongs/'+f['wrong']['id']).json()['status']=='retest_passed'
 finally:cmd('stop',env)
 report={'at':m.utc(),'source':f['releaseSha'],'backup':str(backup),'backupVerified':r['verified'],'restore':restored,'loginAndOriginal5TasksRead':True,'latestUnitFiveCompleted':True,'retestPassedRead':True,'gracefulStopPassed':True};(out/'delivery-restore.json').write_text(json.dumps(report,indent=2));f['finalBackup']=str(backup);f['deliveryRestoreEnv']=str(env)
 for p in [out/'private.json',base/'private.json']:p.write_text(json.dumps(f));p.chmod(0o600)
finally:subprocess.run([f['python'],'/tmp/sczx-step20/start-staging.py'],check=True)
print('final exact source backup, empty restore, login, five lessons/retest and stop PASS')
