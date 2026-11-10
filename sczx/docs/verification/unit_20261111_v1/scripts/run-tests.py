import os,sys,subprocess,json,uuid
from pathlib import Path
from sqlalchemy import create_engine,text
name='sczx_test_unit_tests_'+uuid.uuid4().hex[:6]
with create_engine('mysql+pymysql://root@127.0.0.1:23317/mysql').connect() as c:c.execute(text('CREATE DATABASE '+name+' CHARACTER SET utf8mb4'))
env={**os.environ,'SCZX_DATABASE_URL':'mysql+pymysql://root@127.0.0.1:23317/'+name,'SCZX_RUN_MYSQL_TESTS':'1','PYTHONPATH':str(Path('backend-business').resolve())}
label=sys.argv[1] if len(sys.argv)>1 else 'initial';command=[sys.executable,'-m','unittest','discover','-s','backend-business/tests','-v']
with open('/tmp/sczx-step16/tests-'+label+'.log','w') as f:r=subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT)
Path('/tmp/sczx-step16/tests-'+label+'.json').write_text(json.dumps({'database':name,'exitCode':r.returncode,'command':command},indent=2));print(name,r.returncode);sys.exit(r.returncode)
