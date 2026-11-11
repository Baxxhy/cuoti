import subprocess,os,sys,uuid,json
from pathlib import Path
from sqlalchemy import create_engine,text
name='sczx_test_exam_'+uuid.uuid4().hex[:6]
with create_engine('mysql+pymysql://root@127.0.0.1:23317/mysql').connect() as c:c.execute(text('CREATE DATABASE '+name+' CHARACTER SET utf8mb4'))
label=sys.argv[1] if len(sys.argv)>1 else 'initial';env={**os.environ,'SCZX_DATABASE_URL':'mysql+pymysql://root@127.0.0.1:23317/'+name,'SCZX_RUN_MYSQL_TESTS':'1','PYTHONPATH':str(Path('backend-business').resolve())};command=[sys.executable,'-m','unittest','discover','-s','backend-business/tests','-v'];
if '--targeted' in sys.argv:command+=['-p','test_exams_mysql.py']
with Path('/tmp/sczx-step17/tests-'+label+'.log').open('w') as f:p=subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT)
Path('/tmp/sczx-step17/tests-'+label+'.json').write_text(json.dumps({'database':name,'exitCode':p.returncode,'command':command},indent=2));print(name,p.returncode);sys.exit(p.returncode)
