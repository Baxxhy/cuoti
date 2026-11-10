import os,uuid,subprocess,sys,json
from pathlib import Path
from sqlalchemy import create_engine,text
name='sczx_test_insights_'+uuid.uuid4().hex[:8]
engine=create_engine('mysql+pymysql://root@127.0.0.1:23317/sczx')
with engine.connect() as c:c.execute(text('CREATE DATABASE '+name+' CHARACTER SET utf8mb4'))
env={**os.environ,'SCZX_DATABASE_URL':'mysql+pymysql://root@127.0.0.1:23317/'+name,'SCZX_RUN_MYSQL_TESTS':'1','PYTHONPATH':str(Path('backend-business').resolve())}
args=[sys.executable,'-m','unittest','discover','-s','backend-business/tests','-v']
if len(sys.argv)>1:args+=['-p',sys.argv[1]]
with open('/tmp/sczx-step15/mysql-tests.log','w') as out:r=subprocess.run(args,env=env,stdout=out,stderr=subprocess.STDOUT)
Path('/tmp/sczx-step15/mysql-tests.json').write_text(json.dumps({'database':name,'exitCode':r.returncode,'command':args},indent=2));print('exit',r.returncode,'database',name)
sys.exit(r.returncode)
