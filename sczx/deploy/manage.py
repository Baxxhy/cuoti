#!/usr/bin/env python3
"""Single-host release process and restore tooling; no new runtime dependencies."""
import argparse,json,os,signal,subprocess,sys,time,tarfile,shutil,tempfile,hashlib
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import urlopen
from urllib.parse import urlparse,unquote
ROOT=Path(__file__).resolve().parents[1]

def configuration(path):
    values={}
    for raw in Path(path).read_text().splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):continue
        key,sep,value=line.partition('=')
        if not sep or not key.replace('_','').isalnum():raise ValueError('配置格式无效：只接受KEY=VALUE')
        values[key]=value.strip().strip('"').strip("'")
    for key in ['SCZX_DATABASE_URL','SCZX_STORAGE_DIR','SCZX_FRONTEND_DIST','SCZX_RELEASE_PYTHON','SCZX_RELEASE_STATE']:
        if not values.get(key):raise ValueError('缺少配置 '+key)
    if not values['SCZX_DATABASE_URL'].startswith('mysql+pymysql://'):raise ValueError('仅支持MySQL')
    return values

def mysql_options(config,folder):
    url=urlparse(config['SCZX_DATABASE_URL'].replace('mysql+pymysql://','mysql://',1))
    if not url.path[1:].replace('_','').isalnum():raise ValueError('数据库名无效')
    path=Path(folder)/'mysql.cnf';path.write_text('[client]\nuser='+unquote(url.username or 'root')+'\npassword='+unquote(url.password or '')+'\nhost='+(url.hostname or '127.0.0.1')+'\nport='+str(url.port or 3306)+'\n');path.chmod(0o600)
    return path,url.path[1:]

def alive(pid):
    try:os.kill(pid,0);return True
    except (ProcessLookupError,PermissionError):return False

def run(config,action,archive=None,output=None):
    state=Path(config['SCZX_RELEASE_STATE']).resolve();state.mkdir(parents=True,exist_ok=True);pidfile=state/'process.json'
    process=json.loads(pidfile.read_text()) if pidfile.exists() else None
    running=bool(process and alive(process['pid']))
    env={**os.environ,**config,'PYTHONPATH':str(ROOT/'backend-business')}
    if action=='status':return {'running':running,'pid':process['pid'] if running else None,'url':config.get('SCZX_RELEASE_URL','http://127.0.0.1:8087')}
    if action=='stop':
        if running:
            cmd=Path('/proc')/str(process['pid'])/'cmdline'
            if not cmd.exists() or b'uvicorn' not in cmd.read_bytes():raise RuntimeError('PID不属于本服务，拒绝停止')
            os.kill(process['pid'],signal.SIGTERM)
            for _ in range(100):
                if not alive(process['pid']):break
                time.sleep(.1)
        pidfile.unlink(missing_ok=True);return {'stopped':True}
    if action=='start':
        if running:return {'running':True,'created':False}
        if not (Path(config['SCZX_FRONTEND_DIST'])/'index.html').exists():raise RuntimeError('先构建前端')
        subprocess.run([config['SCZX_RELEASE_PYTHON'],'-m','sczx_business.commands','migrate'],cwd=ROOT/'backend-business',env=env,check=True)
        log=(state/'service.log').open('ab');p=subprocess.Popen([config['SCZX_RELEASE_PYTHON'],'-m','uvicorn','sczx_business.main:app','--host',config.get('SCZX_RELEASE_HOST','127.0.0.1'),'--port',config.get('SCZX_RELEASE_PORT','8087'),'--no-access-log','--log-level','warning'],cwd=ROOT/'backend-business',env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);log.close();pidfile.write_text(json.dumps({'pid':p.pid,'root':str(ROOT),'startedAt':datetime.now(timezone.utc).isoformat()}))
        for _ in range(100):
            if p.poll() is not None:raise RuntimeError('服务启动失败，请查看本机service.log')
            try:
                with urlopen(config.get('SCZX_RELEASE_URL','http://127.0.0.1:8087')+'/api/health',timeout=1) as r:
                    if r.status==200:return {'running':True,'created':True,'pid':p.pid}
            except Exception:time.sleep(.1)
        raise RuntimeError('健康检查超时；保留日志和进程状态供调查')
    if action=='backup':
        if running:raise RuntimeError('先停止写入服务，再备份一致的数据库与文件')
        target=Path(output or state/('backup-'+datetime.now().strftime('%Y%m%d_%H%M%S'))).resolve();target.mkdir(parents=True,exist_ok=False);target.chmod(0o700)
        with tempfile.TemporaryDirectory() as tmp:
            cnf,database=mysql_options(config,tmp)
            with (target/'database.sql').open('wb') as f:subprocess.run(['mysqldump','--defaults-extra-file='+str(cnf),'--single-transaction','--skip-lock-tables','--no-tablespaces',database],stdout=f,check=True)
        with tarfile.open(target/'uploads.tar.gz','w:gz') as tar:
            storage=Path(config['SCZX_STORAGE_DIR']);storage.mkdir(parents=True,exist_ok=True);tar.add(storage,arcname='uploads')
        (target/'release.json').write_text(json.dumps({'schema':1,'time':datetime.now(timezone.utc).isoformat(),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'workingTreeDirty':bool(subprocess.check_output(['git','status','--porcelain','--','.'],cwd=ROOT,text=True).strip()),'frontendIndexSha256':hashlib.sha256((Path(config['SCZX_FRONTEND_DIST'])/'index.html').read_bytes()).hexdigest(),'database':database,'frontend':config['SCZX_FRONTEND_DIST']},indent=2));return {'backup':str(target)}
    if action=='restore':
        if running:raise RuntimeError('恢复前必须停止目标服务')
        source=Path(archive).resolve();storage=Path(config['SCZX_STORAGE_DIR']).resolve()
        if storage.exists() and any(storage.iterdir()):raise RuntimeError('目标上传目录必须为空，原文件请保留并改用新目录')
        with tempfile.TemporaryDirectory() as tmp:
            cnf,database=mysql_options(config,tmp)
            check=subprocess.check_output(['mysql','--defaults-extra-file='+str(cnf),'--batch','--skip-column-names',database,'-e','SHOW TABLES'],text=True)
            if check.strip():raise RuntimeError('目标数据库必须为空；不覆盖已有数据')
            with (source/'database.sql').open('rb') as f:subprocess.run(['mysql','--defaults-extra-file='+str(cnf),database],stdin=f,check=True)
            with tarfile.open(source/'uploads.tar.gz','r:gz') as tar:tar.extractall(tmp,filter='data')
            storage.mkdir(parents=True,exist_ok=True);shutil.copytree(Path(tmp)/'uploads',storage,dirs_exist_ok=True)
        return {'restored':True,'database':database,'files':sum(p.is_file() for p in storage.rglob('*'))}
    raise ValueError('未知操作')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','stop','status','backup','restore']);p.add_argument('--env',required=True);p.add_argument('--archive');p.add_argument('--output');args=p.parse_args()
    try:print(json.dumps(run(configuration(args.env),args.action,args.archive,args.output),ensure_ascii=False))
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
