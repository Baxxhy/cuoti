import os,sys,json,uuid,hashlib,subprocess,secrets
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.engine import URL
root=URL.create('mysql+pymysql',username='root',database='mysql',query={'unix_socket':'/tmp/sczx-mysql.sock'});name='sczx_test_memory_migration_'+uuid.uuid4().hex[:6]
with create_engine(root).connect().execution_options(isolation_level='AUTOCOMMIT') as db:db.execute(text('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4'))
os.environ['SCZX_DATABASE_URL']=root.set(database=name).render_as_string(hide_password=False);sys.path[:0]=['backend-business','backend-business/tests']
from sczx_business.database import Base,engine
from sczx_business import models
Base.metadata.create_all(engine,tables=[t for t in Base.metadata.sorted_tables if t.name!='learning_memory_changes'])
from alembic.config import Config
from alembic import command
os.chdir('backend-business');command.stamp(Config('alembic.ini'),'0011_wrong_remediation');os.chdir('..')
from test_teaching_mysql import fixture,create_accounts
create_accounts(secrets.token_urlsafe(24),'migration-memory-');fixture('migration-memory','migration-memory-')
tables=[t.name for t in Base.metadata.sorted_tables if t.name!='learning_memory_changes']
def digest():
 with engine.connect() as db:
  data={t:sorted([dict(r._mapping) for r in db.execute(text('SELECT * FROM `'+t+'`'))],key=lambda x:json.dumps(x,sort_keys=True,default=str)) for t in tables}
 return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest(),{t:len(v) for t,v in data.items()}
before,counts=digest();r=subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd='backend-business',capture_output=True,text=True);assert r.returncode==0,r.stderr;after,_=digest();assert before==after
with engine.connect() as db:assert db.execute(text('SELECT COUNT(*) FROM learning_memory_changes')).scalar()==0
Path('/tmp/sczx-step14/migration.json').write_text(json.dumps({'database':name,'from':'0011_wrong_remediation','to':'0012_learning_memory','allOriginalTablesUnchanged':True,'beforeDigest':before,'afterDigest':after,'originalRows':counts,'newTable':'learning_memory_changes','migrationLog':r.stdout+r.stderr},ensure_ascii=False,indent=2));print('0011→0012 passed; all old tables unchanged')
