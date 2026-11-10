import json,hashlib,subprocess,sys,uuid,time
from pathlib import Path
from sqlalchemy import create_engine,text,inspect
import httpx
sys.path.insert(0,'deploy');from manage import configuration
out=Path('/tmp/sczx-step16');config=configuration(out/'release.env');fx=json.loads((out/'private.json').read_text());report={'checks':[]};backup=out/('backup-'+uuid.uuid4().hex[:6]);target='sczx_test_unit_restore_'+uuid.uuid4().hex[:6];restored={**config,'SCZX_DATABASE_URL':'mysql+pymysql://root@127.0.0.1:23317/'+target,'SCZX_STORAGE_DIR':str(out/('restored-uploads-'+target)),'SCZX_RELEASE_STATE':str(out/('restored-process-'+target)),'SCZX_RELEASE_PORT':'8088','SCZX_RELEASE_URL':'http://127.0.0.1:8088'}
path=out/'restored.env';path.write_text('\n'.join(k+'='+v for k,v in restored.items())+'\n');path.chmod(0o600)
def cmd(action,env='release.env',*extra):
 p=subprocess.run([sys.executable,'deploy/manage.py',action,'--env',str(out/env),*extra],capture_output=True,text=True);assert p.returncode==0,p.stderr;return p.stdout

def digest(url):
 e=create_engine(url);result={}
 with e.connect() as c:
  for name in sorted(inspect(e).get_table_names()):
   data=sorted([json.dumps(dict(r._mapping),default=str,sort_keys=True) for r in c.execute(text('SELECT * FROM `'+name+'`'))]);result[name]={'rows':len(data),'sha256':hashlib.sha256('\n'.join(data).encode()).hexdigest()}
 e.dispose();return result

def files(folder):return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(folder).rglob('*') if p.is_file()}
with create_engine(config['SCZX_DATABASE_URL']).connect() as c:assert c.execute(text("SELECT COUNT(*) FROM model_jobs WHERE status IN ('queued','running')")).scalar()==0
with create_engine('mysql+pymysql://root@127.0.0.1:23317/mysql').connect() as c:c.execute(text('CREATE DATABASE '+target+' CHARACTER SET utf8mb4'))
try:
 report['stopOriginal']=cmd('stop');before=digest(config['SCZX_DATABASE_URL']);original_files=files(config['SCZX_STORAGE_DIR']);report['backup']=cmd('backup','release.env','--output',str(backup));report['restore']=cmd('restore','restored.env','--archive',str(backup));after=digest(restored['SCZX_DATABASE_URL']);new_files=files(restored['SCZX_STORAGE_DIR']);assert before==after;assert original_files==new_files;report.update(tables=before,files=original_files,allRowsIdentical=True,allFilesIdentical=True,backupPath=str(backup),restoredDatabase=target)
 report['startRestored']=cmd('start','restored.env')
 with httpx.Client(base_url='http://127.0.0.1:8088',timeout=30) as c:
  assert c.get('/').status_code==200;assert c.post('/api/auth/login',json={'username':'unit-s0','password':fx['password']}).status_code==200;p=c.get('/api/platform').json();assert sum(r['completed'] for r in p['records'].values())==5;assert any(r['feedback'] for r in p['records'].values());wrongs=c.get('/api/wrongs').json();assert sum(w['status']=='retest_passed' for w in wrongs)>=3;report['checks'].append({'name':'restored-production-login-five-submissions-three-remediations-feedback','passed':True})
 report['stopRestored']=cmd('stop','restored.env');report['passed']=True
finally:
 report['restartOriginal']=cmd('start');(out/'backup-restore.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('independent DB + upload restore: all tables/bytes identical; production login/records PASS')
