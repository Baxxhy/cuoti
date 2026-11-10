import os,sys,subprocess,uuid,json,hashlib
from pathlib import Path
from sqlalchemy import create_engine,text,inspect
name='sczx_test_insights_migration_'+uuid.uuid4().hex[:6];url='mysql+pymysql://root@127.0.0.1:23317/'+name
with create_engine('mysql+pymysql://root@127.0.0.1:23317/mysql').connect() as c:c.execute(text('CREATE DATABASE '+name+' CHARACTER SET utf8mb4'))
root=Path('/root/Baxxhy/zhiwei/sczx');old=Path('/tmp/sczx-step15/old-business');env={**os.environ,'SCZX_DATABASE_URL':url,'PYTHONPATH':str(old)}
r=subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=old,env=env,capture_output=True,text=True);assert r.returncode==0,r.stderr
os.environ['SCZX_DATABASE_URL']=url;sys.path[:0]=[str(root/'backend-business'),str(root/'backend-business/tests')]
from test_teaching_mysql import create_accounts,fixture
create_accounts(__import__('secrets').token_urlsafe(24),'upgrade-');fixture('upgrade','upgrade-')
engine=create_engine(url)
with engine.begin() as c:
 c.execute(text("INSERT INTO support_issues (id,owner_id,text,reply,resolved) VALUES ('old-issue','upgrade-s0','历史问题','历史回复',1)"))
 c.execute(text("INSERT INTO supplemental_instructions (id,task_id,teacher_id,content,kind,due_date,status) VALUES ('old-supp','upgrade-t00','upgrade-t1','旧补充说明','note','','active')"))
columns={t:[x['name'] for x in inspect(engine).get_columns(t)] for t in inspect(engine).get_table_names() if t!='alembic_version'}
def digest():
 with engine.connect() as c:
  rows={t:sorted([list(r) for r in c.execute(text('SELECT '+','.join('`'+x+'`' for x in cols)+' FROM `'+t+'`'))],key=lambda r:json.dumps(r,default=str,sort_keys=True)) for t,cols in columns.items()}
 return hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest(),{t:len(r) for t,r in rows.items()}
before,counts=digest();env['PYTHONPATH']=str(root/'backend-business');r=subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=root/'backend-business',env=env,capture_output=True,text=True);assert r.returncode==0,r.stderr;after,_=digest();assert before==after,(before,after)
with engine.connect() as c:assert c.execute(text("SELECT status FROM support_issues WHERE id='old-issue'")).scalar()=='replied'
Path('/tmp/sczx-step15/migration.json').write_text(json.dumps({'database':name,'from':'0012_learning_memory','to':'0013_teaching_insights','beforeDigest':before,'afterDigest':after,'allOriginalColumnsUnchanged':True,'oldRows':counts,'legacyReplyAndSupplementPreserved':True,'log':r.stdout+r.stderr},ensure_ascii=False,indent=2));print('old0012 to0013 original columns unchanged')
