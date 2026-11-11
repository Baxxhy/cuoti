#!/usr/bin/env python3
"""Explicit, single-host releases. Preflight never migrates; start never creates schema."""
import argparse,contextlib,hashlib,json,os,re,shutil,signal,subprocess,sys,tarfile,tempfile,time,math
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,unquote
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend-business'))
def utc():return datetime.now(timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path,value):
    path=Path(path);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');path.chmod(0o600)
def mysql_target(config):
    url=urlparse(config['SCZX_DATABASE_URL'].replace('mysql+pymysql://','mysql://',1));name=unquote(url.path[1:])
    if not re.fullmatch(r'[A-Za-z0-9_]+',name):raise ValueError('数据库名无效')
    return url,name
def protected(config):return config.get('SCZX_ENV')=='production' or not mysql_target(config)[1].startswith('sczx_test_')
def configuration(path):
    values={}
    for raw in Path(path).read_text().splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):continue
        key,sep,value=line.partition('=')
        if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*',key):raise ValueError('配置只接受KEY=VALUE，不执行Shell')
        values[key]=value.strip().strip('"').strip("'")
    for key in ['SCZX_DATABASE_URL','SCZX_STORAGE_DIR','SCZX_FRONTEND_DIST','SCZX_RELEASE_PYTHON','SCZX_RELEASE_STATE']:
        if not values.get(key):raise ValueError('缺少配置 '+key)
    if not values['SCZX_DATABASE_URL'].startswith('mysql+pymysql://'):raise ValueError('仅支持MySQL')
    values.setdefault('SCZX_ENV','staging');mysql_target(values)
    if values.get('SCZX_RELEASE_ROOT') and not Path(values['SCZX_RELEASE_ROOT']).is_absolute():raise ValueError('SCZX_RELEASE_ROOT必须为绝对路径')
    timeout=float(values.get('SCZX_CODEX_TIMEOUT_SECONDS','115'))
    if not math.isfinite(timeout) or not 10<=timeout<=600:raise ValueError('模型超时必须为10至600秒')
    if not 1<=int(values.get('SCZX_RELEASE_PORT','8087'))<=65535:raise ValueError('服务端口无效')
    if values['SCZX_ENV'] not in ('development','staging','production'):raise ValueError('SCZX_ENV无效')
    for key in ['SCZX_STORAGE_DIR','SCZX_FRONTEND_DIST','SCZX_RELEASE_PYTHON','SCZX_RELEASE_STATE']:
        if not Path(values[key]).is_absolute():raise ValueError(key+'必须使用绝对路径')
    if values.get('SCZX_AUTO_CREATE_SCHEMA','false').lower()!='false':raise ValueError('发布环境不允许隐式建表或种子初始化')
    return values
def env_for(config):return {**os.environ,**config,'PYTHONPATH':str(ROOT/'backend-business'),'SCZX_AUTO_CREATE_SCHEMA':'false',**({'PATH':config['SCZX_RUNTIME_PATH']} if config.get('SCZX_RUNTIME_PATH') else {})}
def runtime_issues(config):
    issues=[]
    if protected(config):
        public=config.get('SCZX_PUBLIC_URL',config.get('SCZX_RELEASE_URL',''))
        if not public.startswith('https://') or config.get('SCZX_COOKIE_SECURE','false').lower()!='true':issues.append('正式目标必须配置HTTPS与Secure Cookie')
        for key in ['SCZX_STORAGE_DIR','SCZX_FRONTEND_DIST','SCZX_RELEASE_PYTHON','SCZX_RELEASE_STATE']:
            if Path(config[key]).resolve().is_relative_to('/tmp'):issues.append('正式路径不能依赖/tmp：'+key)
        if config.get('SCZX_RELEASE_HOST','127.0.0.1') not in ('127.0.0.1','::1','localhost'):issues.append('正式后端应由已批准代理访问，不能直接绑定公网')
        if '*' in config.get('SCZX_FORWARDED_ALLOW_IPS','127.0.0.1'):issues.append('不能信任任意代理头')
    return issues
def db_engine(config):
    from sqlalchemy import create_engine
    return create_engine(config['SCZX_DATABASE_URL'],pool_pre_ping=True)
def scripts():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    c=Config(str(ROOT/'backend-business/alembic.ini'));c.set_main_option('script_location',str(ROOT/'backend-business/migrations'));return ScriptDirectory.from_config(c)
def target_revision(target='head'):
    script=scripts();rev=script.get_revision(target)
    if not rev:raise ValueError('迁移目标无效')
    return rev.revision
def file_manifest(folder):
    folder=Path(folder)
    if not folder.is_dir():raise ValueError('文件目录不存在：'+str(folder))
    result={}
    for p in sorted(folder.rglob('*')):
        if p.is_symlink():raise ValueError('不自动归档符号链接，请核查：'+str(p.relative_to(folder)))
        if p.is_file():result[str(p.relative_to(folder))]={'bytes':p.stat().st_size,'sha256':sha(p)}
    return result
def database_digest(config):
    from sqlalchemy import inspect,text
    e=db_engine(config);result={}
    try:
        with e.connect() as c:
            for table in sorted(inspect(e).get_table_names()):
                if table=='alembic_version':continue
                rows=sorted(json.dumps(dict(r._mapping),sort_keys=True,ensure_ascii=False,default=str) for r in c.execute(text('SELECT * FROM `'+table.replace('`','``')+'`')))
                result[table]={'rows':len(rows),'sha256':hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
    finally:e.dispose()
    return result
def database_state(config):
    from sqlalchemy import inspect,text
    from alembic.runtime.migration import MigrationContext
    e=db_engine(config)
    try:
        with e.connect() as c:
            tables=inspect(c).get_table_names();heads=list(MigrationContext.configure(c).get_current_heads());connection=c.execute(text('SELECT CONNECTION_ID()')).scalar()
            sessions=[{'id':r.ID,'user':r.USER,'host':r.HOST,'command':r.COMMAND} for r in c.execute(text('SELECT ID,USER,HOST,COMMAND FROM information_schema.PROCESSLIST WHERE DB=:db AND ID<>:own'),{'db':mysql_target(config)[1],'own':connection})]
            active_jobs=c.execute(text("SELECT COUNT(*) FROM model_jobs WHERE status IN ('queued','running')")).scalar() if 'model_jobs' in tables else 0
        return {'heads':heads,'tables':sorted(tables),'otherSessions':sessions,'activeModelJobs':active_jobs}
    finally:e.dispose()
def process_writers(config):
    wanted=mysql_target(config);result=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            raw=(p/'environ').read_bytes();args=(p/'cmdline').read_bytes()
            if not any(k in args for k in [b'python',b'uvicorn',b'gunicorn',b'codex']):continue
            settings=dict(row.split(b'=',1) for row in raw.split(b'\0') if b'=' in row)
            value=settings.get(b'SCZX_DATABASE_URL',b'').decode()
            if not value:continue
            other=mysql_target({'SCZX_DATABASE_URL':value})
            if (('127.0.0.1' if other[0].hostname in ('localhost','::1') else other[0].hostname),other[0].port or 3306,other[1])==(('127.0.0.1' if wanted[0].hostname in ('localhost','::1') else wanted[0].hostname),wanted[0].port or 3306,wanted[1]):result.append({'pid':int(p.name),'program':Path(os.readlink(p/'exe')).name})
        except (OSError,ValueError,UnicodeDecodeError):continue
    return result
def release_identity(config):
    manifest=ROOT/'release-manifest.json'
    if manifest.exists():
        value=json.loads(manifest.read_text())
        if config.get('SCZX_RELEASE_COMMIT') and value['sczxCommit']!=config['SCZX_RELEASE_COMMIT']:raise RuntimeError('配置的sczx发布提交不一致')
        if config.get('SCZX_RELEASE_MANIFEST_SHA256') and sha(manifest)!=config['SCZX_RELEASE_MANIFEST_SHA256']:raise RuntimeError('配置的发布清单摘要不一致')
        for file,digest in value['files'].items():
            path=ROOT/file
            if not path.is_file() or sha(path)!=digest:raise RuntimeError('固定发布包文件不一致：'+file)
        return {'fixed':True,'sczxCommit':value['sczxCommit'],'tree':value['tree'],'manifestSha256':sha(manifest),'frontendIndexSha256':sha(Path(config['SCZX_FRONTEND_DIST'])/'index.html')}
    return {'fixed':False,'sczxCommit':None,'candidateOnly':True}
def preflight(config,target='head'):
    state=database_state(config);destination=target_revision(target);heads=state['heads']
    if len(heads)>1:raise RuntimeError('数据库存在多条迁移分支，拒绝自动选择')
    current=heads[0] if heads else None;script=scripts()
    if current:script.get_revision(current)
    plan=[r.revision for r in reversed(list(script.iterate_revisions(destination,current or 'base')))] if current!=destination else []
    return {'at':utc(),'environment':config['SCZX_ENV'],'database':mysql_target(config)[1],'current':current,'target':destination,'plan':plan,'otherSessions':state['otherSessions'],'processWriters':process_writers(config),'activeModelJobs':state['activeModelJobs'],'tableCount':len(state['tables']),'release':release_identity(config),'runtimeIssues':runtime_issues(config),'sideEffects':False}
def approval(config,action,target=None):
    if not protected(config):return
    file=Path(config.get('SCZX_APPROVAL_FILE','/nonexistent/sczx-approval.json'))
    if not file.is_file() or file.stat().st_mode&0o077:raise RuntimeError('正式操作须有本机0600的目标环境批准记录；本轮未获授权不能生成或代签')
    a=json.loads(file.read_text());url,name=mysql_target(config)
    if a.get('database')!=name or a.get('host')!=url.hostname or a.get('port')!=(url.port or 3306) or action not in a.get('actions',[]):raise RuntimeError('批准记录不覆盖本次目标或操作')
    if not a.get('approvedBy') or not a.get('maintenanceWindow') or not a.get('backupPath'):raise RuntimeError('批准记录必须明确批准人、停机窗口和备份位置')
    if action in ('start','migrate') and (a.get('releaseCommit')!=config.get('SCZX_RELEASE_COMMIT') or a.get('publicUrl')!=config.get('SCZX_PUBLIC_URL') or a.get('storagePath')!=config.get('SCZX_STORAGE_DIR')):raise RuntimeError('批准记录不覆盖发布提交、访问地址或上传目录')
    if not (Path(a['backupPath'])/'release.json').is_file():raise RuntimeError('批准记录的完整备份不存在')
    if target and a.get('targetRevision')!=target:raise RuntimeError('批准记录的迁移目标不一致')
    if datetime.fromisoformat(a['expiresAt'].replace('Z','+00:00'))<=datetime.now(timezone.utc):raise RuntimeError('批准记录已过期')
def quiescent(config):
    state=database_state(config);writers=process_writers(config)
    if state['otherSessions'] or writers or state['activeModelJobs']:raise RuntimeError('存在其他连接/服务写入者或未结束模型任务；仅停止自己管理的进程不足以继续')
@contextlib.contextmanager
def migration_lock(config):
    from sqlalchemy import text
    e=db_engine(config);connection=e.connect()
    try:
        key='sczx-release-'+mysql_target(config)[1]
        if connection.execute(text('SELECT GET_LOCK(:key,0)'),{'key':key}).scalar()!=1:raise RuntimeError('已有部署操作持有数据库发布锁')
        # Exclude this deliberately held advisory connection from the quiescence check.
        yield connection
    finally:
        try:connection.execute(text('SELECT RELEASE_LOCK(:key)'),{'key':'sczx-release-'+mysql_target(config)[1]})
        finally:connection.close();e.dispose()
def migrate(config,target,expected,log_path):
    destination=target_revision(target);approval(config,'migrate',destination);plan=preflight(config,destination)
    if plan['current']!=expected:raise RuntimeError('当前数据库版本与明确指定的expected-current不同')
    quiescent(config)
    log=Path(log_path).resolve();log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('ab') as stream:
        stream.write((json.dumps({'at':utc(),'from':expected,'target':destination,'plan':plan['plan']})+'\n').encode());stream.flush()
        with migration_lock(config):
            p=subprocess.run([config['SCZX_RELEASE_PYTHON'],'-m','alembic','-c',str(ROOT/'backend-business/alembic.ini'),'upgrade',destination],cwd=ROOT/'backend-business',env=env_for(config),stdout=stream,stderr=subprocess.STDOUT)
    log.chmod(0o600)
    if p.returncode:raise RuntimeError('迁移失败；禁止启动新版本，保留本机迁移日志')
    after=preflight(config,destination)
    if after['current']!=destination:raise RuntimeError('迁移后版本不符；禁止启动')
    return {'migrated':True,'from':expected,'target':destination,'log':str(log)}
def mysql_options(config,folder):
    url,name=mysql_target(config);p=Path(folder)/'mysql.cnf'
    values=[unquote(url.username or 'root'),unquote(url.password or ''),url.hostname or '127.0.0.1',str(url.port or 3306)]
    if any('\n' in v or '\r' in v for v in values):raise ValueError('MySQL配置含非法换行')
    p.write_text('[client]\nuser='+values[0]+'\npassword='+values[1]+'\nhost='+values[2]+'\nport='+values[3]+'\n');p.chmod(0o600);return p,name
def pid_info(config):
    file=Path(config['SCZX_RELEASE_STATE'])/'process.json'
    if not file.exists():return file,None
    info=json.loads(file.read_text());pid=info['pid']
    try:
        os.kill(pid,0);p=Path('/proc')/str(pid)
        if (p/'stat').read_text().split(')')[1].split()[0]=='Z':return file,None
        if b'uvicorn' not in (p/'cmdline').read_bytes() or Path(os.readlink(p/'cwd')).resolve()!=(ROOT/'backend-business').resolve():raise RuntimeError('PID身份不符，不停止其他进程')
        target=b'SCZX_DATABASE_URL='+config['SCZX_DATABASE_URL'].encode()
        if target not in (p/'environ').read_bytes().split(b'\0'):raise RuntimeError('PID目标数据库不符')
        return file,info
    except (ProcessLookupError,FileNotFoundError):return file,None
def start_checks(config):
    if not (Path(config['SCZX_FRONTEND_DIST'])/'index.html').is_file():raise RuntimeError('前端构建缺失，拒绝启动')
    report=preflight(config)
    if report['runtimeIssues']:raise RuntimeError('；'.join(report['runtimeIssues']))
    if report['current']!=report['target']:raise RuntimeError('数据库版本不兼容；start不会迁移，请先执行显式migrate')
    from sqlalchemy import inspect
    from sczx_business.database import Base
    from sczx_business import models
    engine=db_engine(config)
    try:
        inspector=inspect(engine);existing=set(inspector.get_table_names())
        for name,table in Base.metadata.tables.items():
            if name not in existing:raise RuntimeError('schema缺少表：'+name)
            if set(table.columns.keys())-set(c['name'] for c in inspector.get_columns(name)):raise RuntimeError('schema缺少字段：'+name)
    finally:engine.dispose()
    storage=Path(config['SCZX_STORAGE_DIR'])
    if not storage.is_dir() or not os.access(storage,os.R_OK|os.W_OK|os.X_OK):raise RuntimeError('上传目录不可读写；不自动创建或替换原目录')
    if not Path(config['SCZX_RELEASE_PYTHON']).is_file() or not os.access(config['SCZX_RELEASE_PYTHON'],os.X_OK):raise RuntimeError('固定Python运行环境不可执行')
    if protected(config) and (not config.get('SCZX_RELEASE_COMMIT') or not config.get('SCZX_RELEASE_MANIFEST_SHA256')):raise RuntimeError('正式配置须固定sczx提交和发布清单摘要')
    if protected(config) and not report['release']['fixed']:raise RuntimeError('正式环境须使用固定发布包，不直接运行工作区')
    return report
def activate(config):
    approval(config,'start');start_checks(config)
    path=Path(config['SCZX_RELEASE_STATE'])/'activation.json';path.parent.mkdir(parents=True,exist_ok=True)
    identity=release_identity(config);url,name=mysql_target(config)
    write_json(path,{'at':utc(),'database':name,'host':url.hostname,'port':url.port or 3306,'sczxCommit':identity['sczxCommit'],'manifestSha256':identity.get('manifestSha256'),'publicUrl':config.get('SCZX_PUBLIC_URL'),'storagePath':config.get('SCZX_STORAGE_DIR'),'frontendPath':config['SCZX_FRONTEND_DIST'],'backendPort':config.get('SCZX_RELEASE_PORT','8087')})
    return {'activated':True,'sczxCommit':identity['sczxCommit']}
def active_release(config):
    if not protected(config):return
    path=Path(config['SCZX_RELEASE_STATE'])/'activation.json'
    if not path.is_file() or path.stat().st_mode&0o077:raise RuntimeError('固定版本尚未经过正式激活批准')
    value=json.loads(path.read_text());url,name=mysql_target(config);identity=release_identity(config)
    expected={'database':name,'host':url.hostname,'port':url.port or 3306,'sczxCommit':identity['sczxCommit'],'manifestSha256':identity.get('manifestSha256'),'publicUrl':config.get('SCZX_PUBLIC_URL'),'storagePath':config.get('SCZX_STORAGE_DIR'),'frontendPath':config['SCZX_FRONTEND_DIST'],'backendPort':config.get('SCZX_RELEASE_PORT','8087')}
    if any(value.get(k)!=v for k,v in expected.items()):raise RuntimeError('激活记录与目标或发布版本不一致')
def serve_command(config):return [config['SCZX_RELEASE_PYTHON'],'-m','uvicorn','sczx_business.main:app','--host',config.get('SCZX_RELEASE_HOST','127.0.0.1'),'--port',config.get('SCZX_RELEASE_PORT','8087'),'--proxy-headers','--forwarded-allow-ips',config.get('SCZX_FORWARDED_ALLOW_IPS','127.0.0.1'),'--no-access-log','--log-level','warning']
def run(config,action,archive=None,output=None):
    if action=='preflight':return preflight(config)
    state=Path(config['SCZX_RELEASE_STATE']);pidfile,info=pid_info(config)
    if action=='activate':return activate(config)
    if action=='check':return start_checks(config)
    if action=='status':return {'running':bool(info),'pid':info['pid'] if info else None,'url':config.get('SCZX_PUBLIC_URL',config.get('SCZX_RELEASE_URL'))}
    if action=='stop':
        approval(config,'stop')
        if info:
            os.kill(info['pid'],signal.SIGTERM)
            for _ in range(150):
                if not pid_info(config)[1]:break
                time.sleep(.1)
            else:raise RuntimeError('停止未完成，保留PID与日志，不强杀其他进程')
        pidfile.unlink(missing_ok=True);return {'stopped':True}
    if action in ('start','serve'):
        if action=='start':approval(config,'start')
        else:active_release(config)
        start_checks(config)
        if not info:quiescent(config)
        if action=='serve':
            os.chdir(ROOT/'backend-business')
            os.execvpe(config['SCZX_RELEASE_PYTHON'],serve_command(config),env_for(config))
        if info:return {'running':True,'created':False}
        if protected(config):activate(config)
        state.mkdir(parents=True,exist_ok=True);log_dir=Path(config.get('SCZX_LOG_DIR',state));log_dir.mkdir(parents=True,exist_ok=True)
        with (log_dir/'service.log').open('ab') as log:p=subprocess.Popen(serve_command(config),cwd=ROOT/'backend-business',env=env_for(config),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        write_json(pidfile,{'pid':p.pid,'root':str(ROOT),'startedAt':utc(),'release':release_identity(config)})
        health=config.get('SCZX_HEALTH_URL',config.get('SCZX_RELEASE_URL','http://127.0.0.1:8087'))+'/api/health'
        for _ in range(100):
            if p.poll() is not None:raise RuntimeError('服务启动失败，保留service.log和PID记录')
            try:
                with urlopen(health,timeout=1) as r:
                    if r.status==200:return {'running':True,'created':True,'pid':p.pid}
            except Exception:time.sleep(.1)
        raise RuntimeError('健康检查超时，保留日志和进程状态')
    if action=='backup':
        quiescent(config);before=database_digest(config);files=file_manifest(config['SCZX_STORAGE_DIR']);identity=release_identity(config)
        if protected(config) and not identity['fixed']:raise RuntimeError('正式备份必须指向固定发布包，不能记录父仓HEAD充作sczx版本')
        target=Path(output).resolve() if output else state/('backup-'+datetime.now().strftime('%Y%m%d_%H%M%S'));target.mkdir(parents=True,exist_ok=False);target.chmod(0o700)
        with tempfile.TemporaryDirectory() as tmp:
            cnf,database=mysql_options(config,tmp)
            with (target/'database.sql').open('wb') as stream:subprocess.run(['mysqldump','--defaults-extra-file='+str(cnf),'--single-transaction','--skip-lock-tables','--no-tablespaces',database],stdout=stream,check=True)
        with tarfile.open(target/'uploads.tar.gz','w:gz') as tar:tar.add(config['SCZX_STORAGE_DIR'],arcname='uploads')
        bundle=config.get('SCZX_RELEASE_BUNDLE')
        if bundle:shutil.copy2(bundle,target/'release.tar.gz')
        shutil.copy2(ROOT/'deploy/release.env.example',target/'config.env.example')
        after=database_digest(config);quiescent(config)
        if after!=before or file_manifest(config['SCZX_STORAGE_DIR'])!=files:raise RuntimeError('备份期间数据或文件变化，保留失败目标，不能标记一致备份')
        write_json(target/'release.json',{'schema':2,'time':utc(),'release':identity,'database':database,'databaseVersion':database_state(config)['heads'],'rows':before,'uploads':files,'files':{p.name:sha(p) for p in target.iterdir() if p.is_file()}})
        for p in target.iterdir():p.chmod(0o600)
        return {'backup':str(target),'verified':True,'tables':len(before),'files':len(files)}
    if action=='restore':
        approval(config,'restore');quiescent(config);source=Path(archive).resolve();meta=json.loads((source/'release.json').read_text());storage=Path(config['SCZX_STORAGE_DIR'])
        if database_state(config)['tables'] or (storage.exists() and any(storage.iterdir())):raise RuntimeError('只恢复到新空库与空目录，绝不覆盖原数据')
        for file,digest in meta['files'].items():
            if sha(source/file)!=digest:raise RuntimeError('备份摘要不符，拒绝恢复：'+file)
        with tempfile.TemporaryDirectory() as tmp:
            cnf,database=mysql_options(config,tmp)
            with (source/'database.sql').open('rb') as stream:subprocess.run(['mysql','--defaults-extra-file='+str(cnf),database],stdin=stream,check=True)
            with tarfile.open(source/'uploads.tar.gz','r:gz') as tar:tar.extractall(tmp,filter='data')
            storage.mkdir(parents=True,exist_ok=True);shutil.copytree(Path(tmp)/'uploads',storage,dirs_exist_ok=True)
        if database_digest(config)!=meta['rows'] or file_manifest(storage)!=meta['uploads']:raise RuntimeError('恢复后记录或字节摘要不一致；保留故障副本，不自动重试覆盖')
        return {'restored':True,'database':database,'tables':len(meta['rows']),'files':len(meta['uploads'])}
    raise ValueError('未知操作')
def package(revision,frontend,output):
    if not re.fullmatch('[a-f0-9]{40}',revision):raise ValueError('必须指定完整sczx提交SHA')
    subprocess.run(['git','cat-file','-e',revision+':backend-business'],cwd=ROOT,check=True,capture_output=True)
    frontend=Path(frontend).resolve();build=json.loads((frontend/'build-info.json').read_text());dest=Path(output).resolve()
    if dest.exists():raise RuntimeError('发布目录必须不存在，不覆盖旧发布')
    dest.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive=Path(tmp)/'source.tar'
        with archive.open('wb') as stream:subprocess.run(['git','archive',revision],cwd=ROOT,stdout=stream,check=True)
        with tarfile.open(archive) as tar:tar.extractall(dest,filter='data')
    for file,digest in build['sources'].items():
        if sha(dest/file)!=digest:raise RuntimeError('构建与源码提交不符，保留失败目录：'+file)
    shutil.copytree(frontend,dest/'frontend/dist')
    files={str(p.relative_to(dest)):sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}
    write_json(dest/'release-manifest.json',{'schema':1,'at':utc(),'sczxCommit':revision,'tree':subprocess.check_output(['git','rev-parse',revision+'^{tree}'],cwd=ROOT,text=True).strip(),'files':files})
    tar_path=dest.with_suffix('.tar.gz')
    with tarfile.open(tar_path,'w:gz') as tar:tar.add(dest,arcname='release')
    tar_path.chmod(0o600);return {'release':str(dest),'bundle':str(tar_path),'sczxCommit':revision,'sha256':sha(tar_path)}
def cli():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','check','migrate','activate','start','serve','stop','status','backup','restore','package']);p.add_argument('--env');p.add_argument('--target',default='head');p.add_argument('--expected-current');p.add_argument('--log');p.add_argument('--archive');p.add_argument('--output');p.add_argument('--revision');p.add_argument('--frontend');a=p.parse_args()
    config={}
    try:
        if a.action=='package':result=package(a.revision or '',a.frontend,a.output)
        else:
            if not a.env:raise ValueError('必须指定--env')
            config=configuration(a.env)
            if config.get('SCZX_RELEASE_ROOT'):
                global ROOT
                ROOT=Path(config['SCZX_RELEASE_ROOT']).resolve();sys.path.insert(0,str(ROOT/'backend-business'))
            if a.action=='migrate':
                if not a.expected_current or not a.log:raise ValueError('迁移必须明确--expected-current和--log')
                result=migrate(config,a.target,None if a.expected_current=='base' else a.expected_current,a.log)
            elif a.action=='preflight':result=preflight(config,a.target)
            else:result=run(config,a.action,a.archive,a.output)
        print(json.dumps(result,ensure_ascii=False))
    except Exception as e:
        message=str(e);url=config.get('SCZX_DATABASE_URL','')
        if url:message=message.replace(url,'[数据库连接已隐藏]');password=unquote(urlparse(url).password or '');message=message.replace(password,'[隐藏]') if password else message
        print(message,file=sys.stderr);return 1
    return 0
if __name__=='__main__':sys.exit(cli())
