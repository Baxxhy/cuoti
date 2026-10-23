"""Isolated evaluation deployment; existing volumes are never reinitialized."""
import os,json,secrets,subprocess,time,signal,sys,urllib.request
from pathlib import Path
ROOT=Path('/opt/app');DATA=Path('/data');DATA.mkdir(exist_ok=True)
children=[]
def stop(*_):
 for p in reversed(children):
  if p.poll() is None:p.terminate()
 for p in reversed(children):
  try:p.wait(timeout=40)
  except subprocess.TimeoutExpired:p.kill()
 sys.exit(0)
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def start(args,**kw):
 p=subprocess.Popen(args,**kw);children.append(p);return p
def wait(check,seconds=180):
 for _ in range(seconds):
  try:
   if check():return
  except Exception:pass
  if any(p.poll() is not None for p in children):raise RuntimeError('子服务已退出，请查看部署日志')
  time.sleep(1)
 raise RuntimeError('启动超时，请查看部署日志')
def main():
 os.umask(0o077)
 secret=DATA/'secrets.json'
 if not secret.exists():secret.write_text(json.dumps({k:secrets.token_hex(32) for k in ('db','auth','algorithm','root')}))
 s=json.loads(secret.read_text())
 env={**os.environ,'CANGJIE_DB_HOST':'127.0.0.1','CANGJIE_DB_PORT':'3307','CANGJIE_DB_NAME':'zhiwei_cangjie_delivery','CANGJIE_DB_USER':'cuoti','CANGJIE_DB_PASSWORD':s['db'],'CANGJIE_AUTH_SECRET':s['auth'],'CANGJIE_ALGORITHM_SECRET':s['algorithm'],'CANGJIE_MEDIA_ROOT':'/data/media','CANGJIE_BACKEND_PORT':'8002','CANGJIE_ALGORITHM_URL':'http://127.0.0.1:8012','CANGJIE_API_POOL_PATH':'/opt/app/config/api_pool.json','CANGJIE_AI_USE_ENV_PROXY':'false','PYTHONPATH':'/opt/app/backend-algorithms:/opt/app/deployment','PYTHONHOME':'/opt/python','SSL_CERT_FILE':'/opt/certs/ca-certificates.crt','HF_HUB_OFFLINE':'1'}
 db=DATA/'mysql';fresh=not (db/'mysql').is_dir();db.mkdir(exist_ok=True)
 base=['/opt/mysql/bin/mysqld','--no-defaults','--user=root','--basedir=/opt/mysql','--datadir='+str(db),'--lc-messages-dir=/opt/mysql/share','--plugin-dir=/opt/mysql/lib/plugin','--secure-file-priv=NULL']
 if fresh:run(base+['--initialize-insecure'])
 start(base+['--bind-address=127.0.0.1','--port=3307','--socket=/tmp/cuoti-mysql.sock','--pid-file=/tmp/cuoti-mysql.pid','--mysqlx=0','--skip-log-bin','--innodb-buffer-pool-size=128M'])
 cfg=DATA/'mysql-client.cnf';cfg.write_text('[client]\nuser=root\npassword='+s['root']+'\nsocket=/tmp/cuoti-mysql.sock\ndefault-character-set=utf8mb4\n')
 root_configured=(DATA/'root-configured').exists()
 admin=['/opt/mysql/bin/mysql',('--defaults-extra-file='+str(cfg) if root_configured else '--no-defaults'),'--socket=/tmp/cuoti-mysql.sock','-uroot','--default-character-set=utf8mb4']
 wait(lambda:subprocess.run(admin+['-NBe','SELECT 1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0)
 if not root_configured:
  sql=f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{s['root']}'; CREATE DATABASE IF NOT EXISTS zhiwei_cangjie_delivery CHARACTER SET utf8mb4; CREATE USER IF NOT EXISTS 'cuoti'@'localhost' IDENTIFIED WITH mysql_native_password BY '{s['db']}'; GRANT ALL ON zhiwei_cangjie_delivery.* TO 'cuoti'@'localhost';"
  run(admin,input=sql,text=True);(DATA/'root-configured').write_text('1');admin=['/opt/mysql/bin/mysql','--defaults-extra-file='+str(cfg)]
 marker=DATA/'initialized'
 if not marker.exists():
  run(admin,input="CREATE DATABASE IF NOT EXISTS zhiwei_cangjie_delivery CHARACTER SET utf8mb4; GRANT ALL ON zhiwei_cangjie_delivery.* TO 'cuoti'@'localhost';",text=True)
  run(['/opt/app/backend-cangjie/main','--init-db'],cwd=ROOT/'backend-cangjie',env=env)
  run(['/opt/app/backend-cangjie/main','--seed-knowledge'],cwd=ROOT/'backend-cangjie',env=env)
  run(admin+['zhiwei_cangjie_delivery'],input=(ROOT/'deployment/demo.sql').read_text(),text=True)
  marker.write_text('1\n')
 if Path('/opt/retrieval/bin/python').exists():
  re={**env,'PYTHONHOME':'/opt/retrieval','PYTHONPATH':'/opt/app','LD_LIBRARY_PATH':'/opt/retrieval/lib:/opt/native','RETRIEVAL_MODEL_CACHE':'/opt/app/.models/bge','RETRIEVAL_EMBEDDING_DEVICE':'cpu','RETRIEVAL_RERANKER_DEVICE':'cpu','OMP_NUM_THREADS':'4'}
  start(['/opt/retrieval/bin/python','-m','uvicorn','scripts.retrieval_inference_server:app','--host','127.0.0.1','--port','8011','--no-access-log'],cwd=ROOT,env=re)
 start(['/opt/python/bin/python3.13','-m','uvicorn','service:create_app','--factory','--host','127.0.0.1','--port','8012','--no-access-log'],cwd=ROOT,env=env)
 start(['/opt/app/backend-cangjie/main'],cwd=ROOT/'backend-cangjie',env=env)
 wait(lambda:urllib.request.urlopen('http://127.0.0.1:8002/readyz',timeout=2).status==200)
 wait(lambda:urllib.request.urlopen('http://127.0.0.1:8012/livez',timeout=2).status==200)
 if Path('/opt/retrieval/bin/python').exists():wait(lambda:urllib.request.urlopen('http://127.0.0.1:8011/health',timeout=2).status==200)
 start(['/opt/python/bin/python3.13','-m','uvicorn','gateway:app','--host','0.0.0.0','--port','8080','--no-access-log'],cwd=ROOT,env=env)
 print('错题帮已就绪：容器端口8080；请在网页注册学生账号。',flush=True)
 while all(p.poll() is None for p in children):time.sleep(2)
 raise RuntimeError('运行中的子服务退出')
try:main()
except Exception as e:
 print('部署失败：'+type(e).__name__+'，请检查前面的服务日志。',flush=True)
 for p in reversed(children):
  if p.poll() is None:p.terminate()
 sys.exit(1)
