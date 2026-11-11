import json,subprocess,time,os,sys,uuid,importlib.util,shutil
from pathlib import Path
import httpx
from sqlalchemy import create_engine,text
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());base=Path(f['base']);spec=importlib.util.spec_from_file_location('release',Path('deploy/manage.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=Path(f['releaseRoot']);cfg=m.configuration(f['demoEnv']);report={'startedAt':m.utc(),'checks':[]}
def note(name,**data):report['checks'].append({'name':name,**data});(out/'runtime-drills.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(name,flush=True)
def wait():
 for _ in range(150):
  try:
   if httpx.get('http://127.0.0.1:8095/api/health').status_code==200:return
  except Exception:pass
  time.sleep(.2)
 raise RuntimeError('service did not recover')
before=m.database_digest(cfg);pid=int(subprocess.check_output(['systemctl','show',f['stagingUnit'],'--property=MainPID','--value'],text=True));assert pid>1
os.kill(pid,9);wait();new=int(subprocess.check_output(['systemctl','show',f['stagingUnit'],'--property=MainPID','--value'],text=True));assert new!=pid and m.database_digest(cfg)==before
note('systemd-process-crash-restart',oldPID=pid,newPID=new,dataUnchanged=True,hostReboot=False)
# Misconfigured builds/storage refuse before starting; original service untouched.
for name,changes in [('frontend-missing',{'SCZX_FRONTEND_DIST':str(base/'no-such-build')}),('storage-missing',{'SCZX_STORAGE_DIR':str(base/'no-such-storage')})]:
 try:m.start_checks({**cfg,**changes});raise AssertionError('bad config accepted')
 except RuntimeError as e:note(name,refused=True,message=str(e))
# A second independent DB cloned from formal0013 for a real insufficient-DDL migration failure.
admin=create_engine('mysql+pymysql://root:'+f['mysqlPassword']+'@127.0.0.1:23320/mysql');name='sczx_test_final_fault_'+uuid.uuid4().hex[:6]
with admin.begin() as c:c.execute(text('CREATE DATABASE '+name+' CHARACTER SET utf8mb4'))
with (Path(f['formalBackup'])/'database.sql').open('rb') as stream:subprocess.run(['mysql','--defaults-extra-file='+str(base/'mysql/client.cnf'),name],stdin=stream,check=True)
username='fault_'+uuid.uuid4().hex[:6]
with admin.begin() as c:
 c.execute(text("CREATE USER '"+username+"'@'127.0.0.1' IDENTIFIED BY :p"),{'p':f['password']});c.execute(text('GRANT SELECT ON '+name+".* TO '"+username+"'@'127.0.0.1'"))
admin.dispose();bad={**cfg,'SCZX_DATABASE_URL':'mysql+pymysql://'+username+':'+f['password']+'@127.0.0.1:23320/'+name};digest=m.database_digest(bad)
try:m.migrate(bad,'0014_examinations','0013_teaching_insights',base/'migration/denied-ddl.log');raise AssertionError('migration failure expected')
except RuntimeError as e:
 assert m.database_state(bad)['heads']==['0013_teaching_insights'] and m.database_digest(bad)==digest;note('migration-real-ddl-denied',refused=True,versionUnchanged=True,rowsUnchanged=True,logBytes=(base/'migration/denied-ddl.log').stat().st_size)
note('formal-no-migration',formalVersion='0013_teaching_insights');report['completedAt']=m.utc();(out/'runtime-drills.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
