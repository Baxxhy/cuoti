import os,sys,json,uuid,subprocess,hashlib
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.engine import URL
root=URL.create('mysql+pymysql',username='root',database='mysql',query={'unix_socket':'/tmp/sczx-mysql.sock'});name='sczx_test_repair_migration_'+uuid.uuid4().hex[:6]
with create_engine(root).connect().execution_options(isolation_level='AUTOCOMMIT') as db:db.execute(text('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4'))
os.environ['SCZX_DATABASE_URL']=root.set(database=name).render_as_string(hide_password=False);sys.path[:0]=['backend-business','backend-business/tests']
subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd='backend-business',check=True,capture_output=True)
from sczx_business.database import SessionLocal,engine
from sczx_business.models import WrongQuestion,RepairAttempt,StudentRecord
from test_teaching_mysql import fixture,create_accounts
from sqlalchemy import select
create_accounts('not-an-operative-login-password','migration-');fx=fixture('migration','migration-')
with SessionLocal.begin() as db:
 rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==fx['tasks'][0],StudentRecord.student_id=='migration-s0'));db.add(WrongQuestion(id='migration-wrong',record_id=rec.id,prompt='x-3=5',answer='2'));db.flush();db.add(RepairAttempt(id='migration-repair',wrong_id='migration-wrong',answer='7',correct=True,verification={'status':'verified','correct':True}))
# Recreate precisely the pre-0011 columns and revision; do not downgrade/drop data.
with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as db:
 fk=db.execute(text("SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=:d AND TABLE_NAME='wrong_questions' AND COLUMN_NAME='owner_id' AND REFERENCED_TABLE_NAME IS NOT NULL"),{'d':name}).scalar()
 if fk:db.execute(text('ALTER TABLE wrong_questions DROP FOREIGN KEY `'+fk+'`'))
 db.execute(text('ALTER TABLE wrong_questions DROP INDEX ix_wrong_questions_owner_id, DROP COLUMN owner_id, DROP COLUMN details, MODIFY record_id VARCHAR(40) NOT NULL'))
 db.execute(text('ALTER TABLE repair_attempts DROP COLUMN details'));db.execute(text("UPDATE alembic_version SET version_num='0010_teaching_messages'"))
 tables=['accounts','student_records','wrong_questions','repair_attempts','learning_tasks']
 def snap():return {t:[dict(x._mapping) for x in db.execute(text('SELECT * FROM '+t+' ORDER BY id'))] for t in tables}
 before=snap()
r=subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd='backend-business',capture_output=True,text=True);assert r.returncode==0,r.stderr
with engine.connect() as db:
 after={t:[dict(x._mapping) for x in db.execute(text('SELECT * FROM '+t+' ORDER BY id'))] for t in tables}
 projected={t:[{k:x[k] for k in before[t][i]} for i,x in enumerate(after[t])] for t in tables};assert projected==before
 assert after['wrong_questions'][0]['owner_id']=='migration-s0';assert after['repair_attempts'][0]['correct']==1
report={'database':name,'oldColumnsAndValuesUnchanged':True,'ownerBackfill':'migration-s0','oldFixedCorrectRetained':True,'rows':{t:len(v) for t,v in before.items()},'migrationOutput':r.stdout+r.stderr}
Path('/tmp/sczx-step13/migration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('Real pre-0011 schema upgrade passed; all prior values retained')
