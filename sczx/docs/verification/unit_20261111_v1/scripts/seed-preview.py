import os,sys,subprocess,json,uuid,secrets
from pathlib import Path
from sqlalchemy import create_engine,text
root=Path('/root/Baxxhy/zhiwei/sczx');name='sczx_test_unit_preview_'+uuid.uuid4().hex[:6];url='mysql+pymysql://root@127.0.0.1:23317/'+name
with create_engine('mysql+pymysql://root@127.0.0.1:23317/mysql').connect() as c:c.execute(text('CREATE DATABASE '+name+' CHARACTER SET utf8mb4'))
os.environ['SCZX_DATABASE_URL']=url;sys.path[:0]=[str(root/'backend-business'),str(root/'backend-business/tests')];subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=root/'backend-business',check=True)
from sczx_business.seed import ensure_seed
ensure_seed()
from sczx_business.database import SessionLocal
from sczx_business.models import Account,Classroom,ClassMember
from sczx_business.security import hash_password
password=secrets.token_urlsafe(24)
with SessionLocal.begin() as db:
 for who,role in [('admin','admin'),('t1','teacher'),('t2','teacher')]+[('s'+str(i),'student') for i in range(9)]:db.add(Account(id='unit-'+who,username='unit-'+who,display_name='单元验收·'+who,role=role,password_hash=hash_password(password)))
 db.flush()
 for i in range(2):
  room=Classroom(id='unit-c'+str(i),teacher_id='unit-t'+str(i+1),name='单元预发布验收'+str(i+1)+'班',grade='七年级',subject='数学');db.add(room);db.flush()
  for sid in ['unit-s'+str(i*3+j) for j in range(3)]+['unit-s6']:db.add(ClassMember(classroom_id=room.id,student_id=sid))
private=Path('/tmp/sczx-step16/private.json');private.write_text(json.dumps({'database':name,'url':url,'password':password}));private.chmod(0o600)
env=Path('/tmp/sczx-step16/release.env');env.write_text('\n'.join(['SCZX_DATABASE_URL='+url,'SCZX_STORAGE_DIR=/tmp/sczx-step16/uploads','SCZX_FRONTEND_DIST=/tmp/sczx-step16/release/frontend','SCZX_RELEASE_PYTHON='+sys.executable,'SCZX_RELEASE_STATE=/tmp/sczx-step16/process','SCZX_RELEASE_HOST=127.0.0.1','SCZX_RELEASE_PORT=8087','SCZX_RELEASE_URL=http://127.0.0.1:8087','SCZX_MODEL_TRANSPORT=codex_cli','SCZX_COOKIE_SECURE=false','SCZX_FACT_TIME_OFFSET_SECONDS=28800'])+'\n');env.chmod(0o600);print(name)
