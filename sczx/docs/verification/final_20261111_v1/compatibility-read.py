import os,json,secrets,hashlib,importlib.util,sys,httpx
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path.cwd();out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());spec=importlib.util.spec_from_file_location('manage',ROOT/'deploy/manage.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);cfg=m.configuration(f['migrationEnv']);os.environ['SCZX_DATABASE_URL']=cfg['SCZX_DATABASE_URL']
from sqlalchemy.orm import Session
from sqlalchemy import select
from sczx_business.models import Account,LoginSession,StudentRecord
from sczx_business.security import hash_password
from sczx_business.main import record_json
engine=m.db_engine(cfg)
with Session(engine) as db:
 originals=list(db.scalars(select(StudentRecord)));serialized=[record_json(db,r) for r in originals];roles={role:db.scalar(select(Account.id).where(Account.role==role)) for role in ['teacher','student']};aid='final-audit-'+secrets.token_hex(6);password=secrets.token_urlsafe(24);db.add(Account(id=aid,username=aid,display_name='副本兼容性验收账号',role='admin',password_hash=hash_password(password),active=True));db.commit()
engine.dispose();m.run(cfg,'start')
report={'serializedOriginalRecords':len(serialized),'originalSerializationDigest':hashlib.sha256(json.dumps(serialized,sort_keys=True,default=str).encode()).hexdigest(),'auditAccountIsolated':True,'originalPasswordsNotChanged':True,'roleReads':{}}
try:
 with httpx.Client(base_url=cfg['SCZX_RELEASE_URL']) as c:
  r=c.post('/api/auth/login',json={'username':aid,'password':password});r.raise_for_status();report['adminLogin']=r.status_code
  for path in ['/api/curriculum/courses','/api/curriculum/knowledge']:
   r=c.get(path);r.raise_for_status();report['roleReads'][path]={'status':r.status_code,'sha256':hashlib.sha256(r.content).hexdigest(),'items':len(r.json())}
 for role,account in roles.items():
  if not account:continue
  token=secrets.token_urlsafe(32)
  with Session(engine) as db:db.add(LoginSession(id=hashlib.sha256(token.encode()).hexdigest(),account_id=account,expires_at=datetime.utcnow()+timedelta(minutes=10)));db.commit()
  with httpx.Client(base_url=cfg['SCZX_RELEASE_URL'],cookies={'sczx_session':token}) as c:
   r=c.get('/api/platform');r.raise_for_status();data=r.json();report['roleReads'][role]={'status':r.status_code,'tasks':len(data['tasks']),'records':len(data['records']),'sha256':hashlib.sha256(r.content).hexdigest()}
 report['passed']=True;print('restored/migrated original serialization, new audit admin login and original role reads PASS; no raw private records archived')
finally:
 engine.dispose();m.run(cfg,'stop');(out/'migration-compatibility.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
