import os,sys,subprocess,uuid,json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine,text
from sqlalchemy.engine import URL
root=URL.create('mysql+pymysql',username='root',database='mysql',query={'unix_socket':'/tmp/sczx-mysql.sock'});name='sczx_test_memory_'+uuid.uuid4().hex[:8]
with create_engine(root).connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4'))
env=os.environ.copy();env['SCZX_DATABASE_URL']=root.set(database=name).render_as_string(hide_password=False);env['SCZX_RUN_MYSQL_TESTS']='1';env['PYTHONPATH']='backend-business';start=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
r=subprocess.run(['/tmp/sczx-venv/bin/python','-m','unittest','discover','-s','backend-business/tests','-v'],env=env,cwd='/root/Baxxhy/zhiwei/sczx',capture_output=True,text=True)
Path('/tmp/sczx-step14/mysql-tests.log').write_text(r.stdout+r.stderr);Path('/tmp/sczx-step14/mysql-tests.json').write_text(json.dumps({'startedAt':start,'finishedAt':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'database':name,'returnCode':r.returncode,'command':'PYTHONPATH=backend-business SCZX_RUN_MYSQL_TESTS=1 python -m unittest discover -s backend-business/tests -v'},indent=2));print((r.stdout+r.stderr)[-3500:]);sys.exit(r.returncode)
