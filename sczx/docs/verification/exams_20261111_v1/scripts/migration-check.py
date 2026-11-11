import json,shutil,hashlib,subprocess,sys,uuid
from pathlib import Path
from sqlalchemy import create_engine,text,inspect
out=Path('/tmp/sczx-step17');name='sczx_test_exam_migration_'+uuid.uuid4().hex[:6];r={'database':name};base={}
with create_engine('mysql+pymysql://root@127.0.0.1:23317/mysql').connect() as c:c.execute(text('CREATE DATABASE '+name+' CHARACTER SET utf8mb4'))
backup=out/'migration-private-backup';backup.mkdir(exist_ok=True);backup.chmod(0o700);shutil.copy2(out/'main-before-private.sql',backup/'database.sql');shutil.copy2(out/'main-files-private.tar.gz',backup/'uploads.tar.gz')
config={'SCZX_DATABASE_URL':'mysql+pymysql://root@127.0.0.1:23317/'+name,'SCZX_STORAGE_DIR':str(out/'migration-uploads'),'SCZX_FRONTEND_DIST':str(out/'release/frontend'),'SCZX_RELEASE_PYTHON':sys.executable,'SCZX_RELEASE_STATE':str(out/'migration-process'),'SCZX_RELEASE_PORT':'8090','SCZX_RELEASE_URL':'http://127.0.0.1:8090','SCZX_RELEASE_HOST':'127.0.0.1'};env=out/'migration.env';env.write_text('\n'.join(k+'='+v for k,v in config.items()));env.chmod(0o600)
def cmd(action):subprocess.run([sys.executable,'deploy/manage.py',action,'--env',str(env),*(['--archive',str(backup)] if action=='restore' else [])],check=True)
def snapshot():
 e=create_engine(config['SCZX_DATABASE_URL']);tables={}
 with e.connect() as c:
  for t in inspect(e).get_table_names():
   if t=='alembic_version':continue
   rows=sorted(json.dumps(dict(row._mapping),sort_keys=True,default=str) for row in c.execute(text('SELECT * FROM `'+t+'`')));tables[t]={'count':len(rows),'sha256':hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
 return tables
cmd('restore');before=snapshot();cmd('start');after=snapshot()
for table,data in before.items():assert after[table]==data,table
r.update(before=before,newTables={t:d for t,d in after.items() if t not in before},allOriginalRowsUnchanged=True,passed=True);assert len(r['newTables'])==8;cmd('stop');(out/'migration-check.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print('actual 0013 backup restored -> 0014 migration; every original table row unchanged and 8 new tables empty PASS')
