import json,subprocess,time,uuid,sys,importlib.util,shutil
from pathlib import Path
from sqlalchemy import create_engine,text
import httpx
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());base=Path(f['base']);spec=importlib.util.spec_from_file_location('release',Path('deploy/manage.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=Path(f['releaseRoot']);cfg=m.configuration(f['demoEnv']);report={'startedAt':m.utc(),'checks':[]}
def note(name,**data):report['checks'].append({'name':name,**data});(out/'backup-rollback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(name,flush=True)
def command(action,env,**args):
 cmd=[f['python'],str(Path.cwd()/'deploy/manage.py'),action,'--env',str(env)]
 for k,v in args.items():cmd+=['--'+k,str(v)]
 r=subprocess.run(cmd,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr)
 return json.loads(r.stdout)
def fresh(name,storage,release,port):
 db='sczx_test_final_'+name+'_'+uuid.uuid4().hex[:6];e=create_engine('mysql+pymysql://root:'+f['mysqlPassword']+'@127.0.0.1:23320/mysql')
 with e.begin() as c:c.execute(text('CREATE DATABASE '+db+' CHARACTER SET utf8mb4'))
 e.dispose();storage=storage.parent/db/'uploads';location=base/name/db;v={**cfg,'SCZX_DATABASE_URL':'mysql+pymysql://root:'+f['mysqlPassword']+'@127.0.0.1:23320/'+db,'SCZX_STORAGE_DIR':str(storage),'SCZX_RELEASE_ROOT':str(release),'SCZX_FRONTEND_DIST':str(release/'frontend/dist'),'SCZX_RELEASE_COMMIT':json.loads((release/'release-manifest.json').read_text())['sczxCommit'],'SCZX_RELEASE_MANIFEST_SHA256':m.sha(release/'release-manifest.json'),'SCZX_RELEASE_BUNDLE':str(release)+'.tar.gz','SCZX_RELEASE_STATE':str(location/'process'),'SCZX_LOG_DIR':str(location/'logs'),'SCZX_RELEASE_PORT':str(port),'SCZX_RELEASE_URL':'http://127.0.0.1:'+str(port),'SCZX_HEALTH_URL':'http://127.0.0.1:'+str(port),'SCZX_PUBLIC_URL':'http://127.0.0.1:'+str(port),'SCZX_COOKIE_SECURE':'false'}
 p=location/'release.env';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('\n'.join(k+'='+v for k,v in v.items()));p.chmod(0o600);return v,p
# No business jobs running before maintenance; exact preproduction unit only.
assert m.database_state(cfg)['activeModelJobs']==0
subprocess.run(['systemctl','stop',f['stagingUnit']],check=True);time.sleep(2)
try:
 backup=base/'backups'/('preproduction-0016-'+uuid.uuid4().hex[:6]);r=command('backup',f['demoEnv'],output=backup);note('complete-0016-backup',**r)
 v,env=fresh('restore16',base/'restore16/uploads',Path(f['releaseRoot']),8097);r=command('restore',env,archive=backup);note('empty16-restore-full-rows-files',**r);command('start',env)
 try:
  with httpx.Client(base_url='http://127.0.0.1:8097') as c:
   assert c.post('/api/auth/login',json={'username':'handoff-s1','password':f['password']}).status_code==200
   p=c.get('/api/platform').json();assert all(row['taskId'] in p['records'] for row in f['tasks']);assert p['records'][f['tasks'][0]['taskId']]['feedback'];assert c.get('/api/exams/'+f['examId']).status_code==200;assert c.get('/api/memory').status_code==200
   note('restored16-actual-login-unit-exam-memory-feedback',tasks=len(f['tasks']),recordCount=len(p['records']))
 finally:command('stop',env)
 # Build complete schema2 metadata for original backup, paired with exact historical0013 release.
 original=Path(f['formalBackup']);paired=base/'backups'/('paired-0013-'+uuid.uuid4().hex[:6]);paired.mkdir();paired.chmod(0o700)
 for name in ['database.sql','uploads.tar.gz']:shutil.copy2(original/name,paired/name)
 shutil.copy2(f['oldReleaseBundle'],paired/'release.tar.gz');shutil.copy2('deploy/release.env.example',paired/'config.env.example')
 migration=json.loads((out/'migration-drill.json').read_text());oldRoot=Path(f['oldReleaseRoot']);m.ROOT=oldRoot
 identity=m.release_identity({'SCZX_FRONTEND_DIST':str(oldRoot/'frontend/dist')});files=m.file_manifest(base/'migration/uploads');assert len(files)==migration['originalFileCount']
 m.write_json(paired/'release.json',{'schema':2,'time':m.utc(),'release':identity,'database':'formal-readonly-source','databaseVersion':['0013_teaching_insights'],'rows':migration['originalTables'],'uploads':files,'files':{p.name:m.sha(p) for p in paired.iterdir() if p.is_file()}})
 for p in paired.iterdir():p.chmod(0o600)
 v,env13=fresh('rollback13',base/'rollback13/uploads',oldRoot,8098);r=command('restore',env13,archive=paired);note('paired0013-empty-restore',**r);r=command('start',env13)
 try:
  assert httpx.get('http://127.0.0.1:8098/api/health').status_code==200
  # Original accounts and password hashes untouched; SQL audit account in copy enables real login.
  e=create_engine(v['SCZX_DATABASE_URL']);from sczx_business.security import hash_password
  with e.begin() as c:c.execute(text("INSERT INTO accounts(id,username,display_name,role,password_hash,active,created_at) VALUES(:id,:id,'恢复验收','admin',:p,1,NOW())"),{'id':'rollback-audit-'+uuid.uuid4().hex[:6],'p':hash_password(f['password'])});uid=c.execute(text("SELECT username FROM accounts WHERE display_name='恢复验收' ORDER BY created_at DESC LIMIT 1")).scalar()
  e.dispose()
  with httpx.Client(base_url='http://127.0.0.1:8098') as c:
   assert c.post('/api/auth/login',json={'username':uid,'password':f['password']}).status_code==200;assert c.get('/api/curriculum/courses').status_code==200
  note('old-compatible-release-started-login-read',sczxCommit=f['oldReleaseSha'],revision='0013_teaching_insights',newDataRetainedIn16Backup=True)
 finally:command('stop',env13)
 f=json.loads((out/'private.json').read_text());f.update(finalBackup=str(backup),paired13Backup=str(paired),restore16Env=str(env),rollback13Env=str(env13))
 for p in [out/'private.json',base/'private.json']:p.write_text(json.dumps(f));p.chmod(0o600)
finally:subprocess.run([sys.executable,'/tmp/sczx-step20/start-staging.py'],check=True)
report['completedAt']=m.utc();(out/'backup-rollback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
