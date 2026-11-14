#!/usr/bin/env python3
"""Local Linux workspace runner. Own MySQL, explicit initialization, no production access."""
import signal
import argparse,contextlib,fcntl,getpass,hashlib,importlib.util,json,os,secrets,shutil,socket,subprocess,sys,tarfile,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend-business'))
spec=importlib.util.spec_from_file_location('local_release',ROOT/'deploy/manage.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');path.chmod(0o600)
def load(home):
 v=json.loads((home/'local.json').read_text());assert Path(v['home']).resolve()==home
 return v
def free(port):
 with socket.socket() as s:return s.connect_ex(('127.0.0.1',port))!=0
def mysql_ready(v):
 from sqlalchemy import create_engine,text
 e=create_engine(v['databaseUrl'].rsplit('/',1)[0]+'/mysql',connect_args={'connect_timeout':1})
 try:
  with e.connect() as c:return Path(c.execute(text('SELECT @@datadir')).scalar()).resolve()==Path(v['home'])/'mysql/data'
 except Exception:return False
 finally:e.dispose()
def mysql_start(v):
 home=Path(v['home']);folder=home/'mysql';folder.mkdir(exist_ok=True);folder.chmod(0o700);data=folder/'data'
 if mysql_ready(v):return
 if not free(v['mysqlPort']):raise RuntimeError('本地MySQL端口被其他进程占用，未启动或修改其他实例。')
 if not shutil.which('mysqld') or not shutil.which('mysql'):raise RuntimeError('请先安装MySQL8服务端与客户端；不使用其他项目的数据库。')
 if not (data/'mysql').exists():
  with (folder/'initialize.log').open('ab') as log:subprocess.run(['mysqld','--no-defaults','--initialize-insecure','--user='+getpass.getuser(),'--datadir='+str(data)],stdout=log,stderr=log,check=True)
 with (folder/'console.log').open('ab') as log:
  process=subprocess.Popen(['mysqld','--no-defaults','--user='+getpass.getuser(),'--datadir='+str(data),'--bind-address=127.0.0.1','--port='+str(v['mysqlPort']),'--socket='+str(folder/'mysql.sock'),'--pid-file='+str(folder/'mysql.pid'),'--log-error='+str(folder/'error.log'),'--mysqlx=0','--innodb-buffer-pool-size=67108864','--innodb-redo-log-capacity=33554432','--skip-log-bin'],stdout=log,stderr=log,start_new_session=True)
 for _ in range(150):
  if process.poll() is not None:raise RuntimeError('本地MySQL启动失败，查看本地mysql/error.log；未删除数据。')
  if (folder/'mysql.sock').exists():
   # A generated root password is installed exactly once on this owned datadir.
   if not (folder/'password-set').exists():
    r=subprocess.run(['mysql','--no-defaults','--socket='+str(folder/'mysql.sock'),'--user=root'],input="ALTER USER 'root'@'localhost' IDENTIFIED BY '"+v['mysqlPassword']+"';\n",text=True,capture_output=True)
    if r.returncode==0:(folder/'password-set').write_text('set\n')
   if mysql_ready(v):break
  time.sleep(.2)
 else:raise RuntimeError('本地MySQL未就绪，保留目录和日志。')
 (folder/'client.cnf').write_text('[client]\nuser=root\npassword='+v['mysqlPassword']+'\nhost=127.0.0.1\nport='+str(v['mysqlPort'])+'\n');(folder/'client.cnf').chmod(0o600)
def env_path(home):return home/'local.env'
def save_env(v):
 home=Path(v['home']);cfg={'SCZX_ENV':'development','SCZX_DATABASE_URL':v['databaseUrl'],'SCZX_STORAGE_DIR':v['storage'],'SCZX_FRONTEND_DIST':str(ROOT/'frontend/dist'),'SCZX_RELEASE_ROOT':str(ROOT),'SCZX_RELEASE_PYTHON':sys.executable,'SCZX_RELEASE_STATE':str(home/'process'),'SCZX_LOG_DIR':str(home/'logs'),'SCZX_RELEASE_HOST':'127.0.0.1','SCZX_RELEASE_PORT':str(v['port']),'SCZX_RELEASE_URL':'http://127.0.0.1:'+str(v['port']),'SCZX_PUBLIC_URL':'http://127.0.0.1:'+str(v['port']),'SCZX_HEALTH_URL':'http://127.0.0.1:'+str(v['port']),'SCZX_COOKIE_SECURE':'false','SCZX_ALLOWED_ORIGINS':'','SCZX_AUTO_CREATE_SCHEMA':'false','SCZX_MODEL_TRANSPORT':'codex_cli','SCZX_CODEX_BIN':shutil.which('codex') or 'codex','SCZX_CODEX_HOME':os.environ.get('CODEX_HOME',str(Path.home()/'.codex')),'SCZX_RUNTIME_PATH':os.environ['PATH'],'SCZX_CODEX_TIMEOUT_SECONDS':'115'}
 if any(os.environ.get(k) for k in ['HTTPS_PROXY','HTTP_PROXY','ALL_PROXY']):
  cfg['SCZX_CODEX_INHERIT_PROXY']='true';cfg.update({k:os.environ[k] for k in ['HTTPS_PROXY','HTTP_PROXY','ALL_PROXY','NO_PROXY'] if os.environ.get(k)})
 env_path(home).write_text('\n'.join(k+'='+value for k,value in cfg.items())+'\n');env_path(home).chmod(0o600);return cfg
def config(v):
 c=release.configuration(env_path(Path(v['home'])))
 if c['SCZX_ENV']!='development' or not c['SCZX_DATABASE_URL'].endswith('/'+v['database']) or not v['database'].startswith('sczx_test_local_'):raise RuntimeError('本地配置目标无效，拒绝访问其他数据库。')
 return c
def database(v,name):
 from sqlalchemy import create_engine,text
 assert name.startswith('sczx_test_local_') and name.replace('_','').isalnum()
 e=create_engine(v['databaseUrl'])
 try:
  with e.begin() as c:c.execute(text('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4'))
 finally:e.dispose()
def initialize(args,home):
 if args.archive and (not args.accounts or not Path(args.accounts).is_file()):raise RuntimeError('导入备份须同时提供同一演示数据的私有--accounts JSON。')
 if (home/'local.json').exists():return load(home)
 if not free(args.port) or not free(args.mysql_port):raise RuntimeError('本地网页或MySQL端口被占用，请选择其他端口。')
 if not (ROOT/'frontend/dist/index.html').exists():subprocess.run([sys.executable,str(ROOT/'deploy/build_frontend.py')],cwd=ROOT,check=True)
 name='sczx_test_local_demo';password=secrets.token_urlsafe(24);v={'home':str(home),'mysqlPort':args.mysql_port,'port':args.port,'mysqlPassword':password,'database':name,'databaseUrl':'mysql+pymysql://root:'+password+'@127.0.0.1:'+str(args.mysql_port)+'/mysql','storage':str(home/'uploads'),'initialized':False,'freshDemo':not bool(args.archive)};write(home/'local.json',v)
 return finish_init(args,v)
def finish_init(args,v):
 home=Path(v['home']);mysql_start(v)
 if v.get('initialized'):return v
 from sqlalchemy import create_engine,inspect
 e=create_engine(v['databaseUrl'])
 try:
  with e.connect() as c:exists=v['database'] in inspect(c).get_schema_names()
 finally:e.dispose()
 if not exists:database(v,v['database'])
 v['databaseUrl']=v['databaseUrl'].rsplit('/',1)[0]+'/'+v['database'];write(home/'local.json',v);cfg=save_env(v)
 if args.archive:
  release.run(cfg,'restore',archive=args.archive)
  if not args.accounts:raise RuntimeError('备份恢复成功；请用--accounts提供同一演示数据的私有账号JSON，再继续初始化。')
  accounts=json.loads(Path(args.accounts).read_text())
 else:
  heads=release.database_state(cfg)['heads']
  if heads!=[release.target_revision()]:release.migrate(cfg,'head',heads[0] if len(heads)==1 else None,home/'logs/initial-migration.log');Path(v['storage']).mkdir(exist_ok=True)
  accounts=json.loads((home/'accounts.json').read_text()) if (home/'accounts.json').exists() else [{'username':name,'role':role,'password':secrets.token_urlsafe(18)} for name,role in [('admin','admin'),('teacher','teacher'),('student','student')]]
  write(home/'accounts.json',accounts)
  env=release.env_for(cfg)
  for a in accounts:
   env['SCZX_BOOTSTRAP_'+a['role'].upper()+'_PASSWORD']=a['password'];env['SCZX_BOOTSTRAP_'+a['role'].upper()+'_USERNAME']=a['username']
  subprocess.run([sys.executable,'-m','sczx_business.commands','seed'],cwd=ROOT/'backend-business',env=env,check=True)
  subprocess.run([sys.executable,'-m','sczx_business.commands','resources'],cwd=ROOT/'backend-business',env=env,check=True)
 write(home/'accounts.json',accounts);v['initialized']=True;write(home/'local.json',v);return v
def first_task(v,cfg):
 if not v.get('freshDemo') or v.get('demoReady'):return
 import httpx,copy
 accounts=json.loads((Path(v['home'])/'accounts.json').read_text());teacher=next(a for a in accounts if a['role']=='teacher')
 with httpx.Client(base_url=cfg['SCZX_PUBLIC_URL'],timeout=30) as client:
  def call(method,path,body=None):
   response=client.request(method,'/api'+path,json=body)
   if not response.is_success:raise RuntimeError('本地示例课准备失败：'+path+'；原数据保留，请重试启动。')
   return response.json()
  admin=next(a for a in accounts if a['role']=='admin');call('POST','/auth/login',{'username':admin['username'],'password':admin['password']})
  sys.path.insert(0,str(ROOT/'scripts'));from install_unit_content import install
  bundle=json.loads((ROOT/'docs/planning/第十六步单元内容草案_20261111_v1.json').read_text());approval=json.loads((ROOT/'docs/verification/unit_20261111_v1/human-review.json').read_text());installed=install(client,bundle,approval);write(Path(v['home'])/'demo-content.json',installed)
  call('POST','/auth/login',{'username':teacher['username'],'password':teacher['password']})
  for lid in installed['mapping'].values():
   lesson=call('GET','/curriculum/lessons/'+lid);draft=call('GET','/platform?lessonId='+lid)['lessonDraft'];draft.update(lessonId=lid,goal=lesson['goal'],blocks=copy.deepcopy(lesson['blocks']),questions=copy.deepcopy(lesson['questions']),lessonSnapshot=lesson,caseId=lesson.get('caseId'),caseSnapshot=lesson.get('caseSnapshot'));saved=call('PUT','/platform',{'data':{'lessonDraft':draft}});draft['revision']=saved['draftRevision'];call('POST','/tasks/publish',{'lessonId':lid,'classroomId':'class-demo','lessonDraft':draft,'idempotencyKey':'local-first-lesson-v1:'+lid})
  call('POST','/auth/logout')
 v['demoReady']=True;write(Path(v['home'])/'local.json',v)
def frontend_pid(v):
 path=Path(v['home'])/'frontend.pid'
 try:
  pid=int(path.read_text());cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
  return pid if str(ROOT/'frontend/node_modules/vite/bin/vite.js').encode() in cmd else None
 except (OSError,ValueError):return None
def frontend_stop(v):
 pid=frontend_pid(v)
 if pid:
  os.kill(pid,signal.SIGTERM)
  for _ in range(50):
   if free(5175):break
   time.sleep(.1)
 (Path(v['home'])/'frontend.pid').unlink(missing_ok=True)
def frontend_start(v,cfg):
 if frontend_pid(v) and not free(5175):return
 if not free(5175):raise RuntimeError('前端5175端口被其他服务占用，请先停止占用服务；不会自动换端口。')
 env={**os.environ,'SCZX_API_PROXY':cfg['SCZX_RELEASE_URL']}
 with (Path(v['home'])/'logs/frontend.log').open('ab') as log:
  proc=subprocess.Popen(['node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','0.0.0.0','--port','5175','--strictPort'],cwd=ROOT/'frontend',env=env,stdout=log,stderr=log,start_new_session=True)
 (Path(v['home'])/'frontend.pid').write_text(str(proc.pid))
 for _ in range(100):
  if proc.poll() is not None:raise RuntimeError('前端启动失败，请查看logs/frontend.log。')
  if not free(5175):return
  time.sleep(.1)
 raise RuntimeError('前端5175启动超时，请查看logs/frontend.log。')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['init','start','stop','status','doctor','backup','restore']);parser.add_argument('--home',default=str(ROOT/'backend-business/var/local'));parser.add_argument('--port',type=int,default=8099);parser.add_argument('--mysql-port',type=int,default=23321);parser.add_argument('--archive');parser.add_argument('--accounts');args=parser.parse_args();home=Path(args.home).resolve();home.mkdir(parents=True,exist_ok=True);home.chmod(0o700)
 try:
  with (home/'operation.lock').open('w') as lock:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:raise RuntimeError('另一本地操作正在进行，请等待完成。')
   if args.action=='init':v=finish_init(args,load(home)) if (home/'local.json').exists() else initialize(args,home);print('本地初始化完成；演示账号保存在 '+str(home/'accounts.json'));return
   if not (home/'local.json').exists():raise RuntimeError('请先执行 ./start-local.sh init；只会初始化独立本地数据库。')
   v=load(home);cfg=config(v)
   if args.action=='doctor':print(json.dumps({'python':sys.version.split()[0],'mysqlBinary':bool(shutil.which('mysqld')),'mysqlOwnedAndReady':mysql_ready(v),'frontend':(ROOT/'frontend/dist/index.html').exists(),'codexBinary':bool(shutil.which('codex')),'url':'http://127.0.0.1:5175','accountsFile':str(home/'accounts.json')},ensure_ascii=False));return
   if args.action=='status':print(json.dumps({'web':release.run(cfg,'status'),'frontend':{'running':bool(frontend_pid(v)),'url':'http://127.0.0.1:5175'},'mysqlOwnedAndReady':mysql_ready(v)},ensure_ascii=False));return
   if args.action=='stop':
    frontend_stop(v)
    release.run(cfg,'stop')
    if mysql_ready(v):subprocess.run(['mysqladmin','--defaults-extra-file='+str(home/'mysql/client.cnf'),'shutdown'],check=True,capture_output=True)
    print('本地网页与专用MySQL已停止；所有数据保留。');return
   mysql_start(v)
   if args.action=='start':release.run(cfg,'start');first_task(v,cfg);frontend_start(v,cfg);print('打开 http://127.0.0.1:5175'+'；账号见 '+str(home/'accounts.json'));return
   was_running=release.run(cfg,'status')['running'];release.run(cfg,'stop')
   try:
    if args.action=='backup':
     target=home/'backups'/('local-'+uuid.uuid4().hex[:12]);result=release.run(cfg,'backup',output=target);shutil.copy2(home/'accounts.json',target/'accounts-private.json');(target/'accounts-private.json').chmod(0o600)
     meta=json.loads((target/'release.json').read_text());meta['files']['accounts-private.json']=release.sha(target/'accounts-private.json');release.write_json(target/'release.json',meta);print(json.dumps(result,ensure_ascii=False));return
    if not args.archive:raise RuntimeError('恢复必须提供--archive；只恢复到新库和新目录，旧数据保留。')
    name='sczx_test_local_restore_'+uuid.uuid4().hex[:10];database(v,name);new={**v,'database':name,'databaseUrl':v['databaseUrl'].rsplit('/',1)[0]+'/'+name,'storage':str(home/'restored'/name/'uploads')};newcfg={**cfg,'SCZX_DATABASE_URL':new['databaseUrl'],'SCZX_STORAGE_DIR':new['storage']};release.run(newcfg,'restore',archive=args.archive)
    shutil.copy2(env_path(home),home/('prior-'+uuid.uuid4().hex[:8]+'.env'));write(home/'local.json',new);save_env(new);cfg=config(new)
    if (Path(args.archive)/'accounts-private.json').exists():shutil.copy2(Path(args.archive)/'accounts-private.json',home/'accounts.json');(home/'accounts.json').chmod(0o600)
    print('已恢复到新的本地库和上传目录，原库及原文件保留。')
   finally:
    if was_running:release.run(cfg,'start')
 except Exception as error:
  # Never echo database URLs, credentials or a raw SQLAlchemy exception.
  message=str(error)
  for token in [locals().get('v',{}).get('databaseUrl',''),locals().get('v',{}).get('mysqlPassword','')]:
   if token:message=message.replace(token,'[本地连接已隐藏]')
  print('本地操作失败：'+message.split('\n')[0],file=sys.stderr);return 1
 return 0
if __name__=='__main__':sys.exit(main())
