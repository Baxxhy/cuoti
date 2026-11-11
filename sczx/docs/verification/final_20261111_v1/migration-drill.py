import os,sys,json,shutil,subprocess,secrets,tarfile,hashlib,importlib.util,uuid
from pathlib import Path
ROOT=Path.cwd();out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());base=Path(f['base']);spec=importlib.util.spec_from_file_location('manage',ROOT/'deploy/manage.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from sqlalchemy import create_engine,text
formal={'SCZX_ENV':'staging','SCZX_DATABASE_URL':'mysql+pymysql://root@127.0.0.1:23317/sczx','SCZX_STORAGE_DIR':'/tmp/sczx-uploads','SCZX_FRONTEND_DIST':str(ROOT/'frontend/dist'),'SCZX_RELEASE_PYTHON':f['python'],'SCZX_RELEASE_STATE':str(base/'formal-inspection')}
m.quiescent(formal);original=m.database_digest(formal);images=m.file_manifest(formal['SCZX_STORAGE_DIR']);backup=base/'backups'/('formal-0013-'+uuid.uuid4().hex[:8]);backup.mkdir(parents=True);backup.chmod(0o700)
with (backup/'database.sql').open('wb') as stream:subprocess.run(['mysqldump','--host=127.0.0.1','--port=23317','--user=root','--single-transaction','--skip-lock-tables','--no-tablespaces','sczx'],stdout=stream,check=True)
with tarfile.open(backup/'uploads.tar.gz','w:gz') as tar:tar.add(formal['SCZX_STORAGE_DIR'],arcname='uploads')
assert m.database_digest(formal)==original and m.file_manifest(formal['SCZX_STORAGE_DIR'])==images;m.quiescent(formal)
for p in backup.iterdir():p.chmod(0o600)
name='sczx_test_final_migration_'+uuid.uuid4().hex[:6];url='mysql+pymysql://root:'+f['mysqlPassword']+'@127.0.0.1:23320/'+name
admin=create_engine('mysql+pymysql://root:'+f['mysqlPassword']+'@127.0.0.1:23320/mysql')
with admin.begin() as c:c.execute(text('CREATE DATABASE '+name+' CHARACTER SET utf8mb4'))
admin.dispose()
with (backup/'database.sql').open('rb') as stream:subprocess.run(['mysql','--defaults-extra-file='+str(base/'mysql/client.cnf'),name],stdin=stream,check=True)
folder=base/'migration';folder.mkdir(exist_ok=True)
with tarfile.open(backup/'uploads.tar.gz') as tar:tar.extractall(folder,filter='data')
cfg={**formal,'SCZX_DATABASE_URL':url,'SCZX_STORAGE_DIR':str(folder/'uploads'),'SCZX_RELEASE_STATE':str(folder/'process'),'SCZX_RELEASE_PORT':'8096','SCZX_RELEASE_URL':'http://127.0.0.1:8096','SCZX_COOKIE_SECURE':'false','SCZX_CODEX_BIN':shutil.which('codex'),'SCZX_FACT_TIME_OFFSET_SECONDS':'28800'}
assert m.database_digest(cfg)==original and m.file_manifest(cfg['SCZX_STORAGE_DIR'])==images
before=m.database_state(cfg);rootstate=Path(cfg['SCZX_RELEASE_STATE']);rejected=False
try:m.run(cfg,'start')
except RuntimeError as e:rejected='start不会迁移' in str(e)
assert rejected and not rootstate.exists() and m.database_state(cfg)['heads']==['0013_teaching_insights']
# A separate, dormant process with the same target is detected even without a SQL connection.
writer=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],env={**os.environ,'SCZX_DATABASE_URL':url})
try:
 try:m.quiescent(cfg);raise AssertionError('external process not detected')
 except RuntimeError:external_detected=True
finally:writer.terminate();writer.wait()
versions=[];current='0013_teaching_insights'
for target in ['0014_examinations','0015_classroom_community','0016_offline_drafts']:
 old=m.database_digest(cfg);report=m.migrate(cfg,target,current,folder/('migration-'+target+'.log'));after=m.database_digest(cfg);assert all(after[t]==v for t,v in old.items());versions.append({'from':current,'target':target,'oldRowsUnchanged':True,'newTables':{k:v for k,v in after.items() if k not in old}});current=target
assert m.file_manifest(cfg['SCZX_STORAGE_DIR'])==images
f.update(migrationDatabase=name,migrationUrl=url,migrationEnv=str(folder/'release.env'),formalBackup=str(backup));p=base/'private.json';p.write_text(json.dumps(f));p.chmod(0o600);p=out/'private.json';p.write_text(json.dumps(f));p.chmod(0o600);p=folder/'release.env';p.write_text('\n'.join(k+'='+v for k,v in cfg.items()));p.chmod(0o600)
public={'date':'2026-11-11','formalReadOnly':True,'formalCurrent':'0013_teaching_insights','backupPath':str(backup),'sqlBytes':(backup/'database.sql').stat().st_size,'sqlSha256':m.sha(backup/'database.sql'),'uploadArchiveSha256':m.sha(backup/'uploads.tar.gz'),'originalTables':original,'originalFileCount':len(images),'originalFilesDigest':hashlib.sha256(json.dumps(images,sort_keys=True).encode()).hexdigest(),'emptyRestoreVerified':True,'startAt0013RefusedWithoutSideEffects':rejected,'externalDormantWriterDetected':external_detected,'migrationSteps':versions,'finalHeads':m.database_state(cfg)['heads'],'originalFilesUnchanged':True,'formalMigrationExecuted':False}
(out/'migration-drill.json').write_text(json.dumps(public,ensure_ascii=False,indent=2));print('formal0013 read-only backup, empty restore and sequential0014/15/16 full-row/byte protection PASS')
