"""Check standalone imports and dependency ownership without a business DB or AI calls."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def python_probe():
    if os.environ.get('SCZX_STANDALONE_TRACE')=='1':
        import faulthandler
        faulthandler.dump_traceback_later(15)
    blocked=[]
    def guard(event,args):
        if event not in ['open','os.listdir','os.scandir'] or not args:return
        raw=args[0]
        if not isinstance(raw,(str,bytes,os.PathLike)):return
        candidate=Path(os.fsdecode(raw)).resolve()
        if candidate.is_relative_to(ROOT/'reference') or (candidate.is_relative_to(ROOT.parent) and not candidate.is_relative_to(ROOT)):
            blocked.append(str(candidate));raise PermissionError('old project access blocked by standalone audit')
    sys.addaudithook(guard)
    try:
        (ROOT.parent/'README.md').read_bytes()
    except PermissionError:canary=True
    else:raise AssertionError('old project guard was not active')
    blocked.clear()
    sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'algorithms')]
    import fastapi,pymysql,sympy,uvicorn,sczx_api,service
    from sczx_api.main import app
    from fastapi.testclient import TestClient
    modules=[fastapi,pymysql,sympy,uvicorn,sczx_api,service]
    origins={module.__name__:str(Path(module.__file__).resolve().relative_to(ROOT)) for module in modules}
    # No lifespan is entered: this is an import/local-compute audit, not a DB check.
    client=TestClient(app)
    try:
        live=client.get('/livez');assert live.status_code==200 and live.json()['status']=='alive'
    finally:client.close()
    secret='standalone-audit-'+secrets.token_hex(24)
    algorithm=service.create_app(secret=secret,pool_path=ROOT/'.runtime/standalone-no-model-pool.json')
    with TestClient(algorithm) as client:
        assert client.get('/livez').json()['logical_model']=='unconfigured'
        response=client.post('/v1/compute',headers={'Authorization':'Bearer '+secret},json={'operation':'math_compare','left':'2*(x+1)','right':'2*x+2'})
        assert response.status_code==200 and response.json()['result']=={'equivalent':True,'verified':True}
        solved=client.post('/v1/compute',headers={'Authorization':'Bearer '+secret},json={'operation':'math_solve','text':'解方程 2x+3=11'})
        assert solved.status_code==200 and solved.json()['result']=={'answer':'x=4','verified':True}
    from importlib.metadata import distribution
    pins=[line for line in (ROOT/'requirements.lock').read_text().splitlines() if line and not line.startswith('#')]
    for pin in pins:
        name,version=pin.split('==',1);installed=distribution(name)
        assert installed.version==version,(name,'installed version differs from lock')
        assert Path(installed.locate_file('')).resolve().is_relative_to(ROOT),(name,'distribution escaped project')
    assert not blocked,blocked
    assert Path(sys.prefix).resolve()==ROOT/'.venv'
    assert not any('site-packages' in value and not Path(value).resolve().is_relative_to(ROOT) for value in sys.path)
    return {'locked_python_distributions':len(pins),'isolated_mode':bool(sys.flags.isolated),'legacy_read_guard_confirmed':canary,'legacy_read_attempts':blocked,'module_origins':origins,'business_livez':True,'local_math_compare_and_solve':True,'scope':'imports, business liveness without lifespan, local algorithm compute; no DB or external model'}


def node_probe():
    program=r"""
import {createRequire} from 'node:module';import fs from 'node:fs';import path from 'node:path';
const root=process.argv[2],require=createRequire(path.join(root,'frontend/package.json')),origins={};
for(const name of ['vue','vite','pinia','katex','@playwright/test']){
 const resolved=fs.realpathSync(require.resolve(name));if(!resolved.startsWith(root+path.sep))throw Error('dependency escaped project');origins[name]=path.relative(root,resolved);
}
const lock=JSON.parse(fs.readFileSync(path.join(root,'frontend/package-lock.json'),'utf8'));
let installed=0,optionalMissing=0;
for(const [key,entry] of Object.entries(lock.packages)){
 if(!key)continue;
 if(key.includes('node_modules/@dcloudio/'))throw Error('uni-app package remains');
 const file=path.join(root,'frontend',key,'package.json');
 if(!fs.existsSync(file)){if(entry.optional){optionalMissing++;continue}throw Error('required locked package missing: '+key)}
 const resolved=fs.realpathSync(file);if(!resolved.startsWith(root+path.sep))throw Error('locked package escaped project');
 if(JSON.parse(fs.readFileSync(resolved,'utf8')).version!==entry.version)throw Error('installed version differs from lock: '+key);
 installed++;
}
console.log(JSON.stringify({module_origins:origins,installed_locked_packages:installed,optional_platform_packages_absent:optionalMissing,uni_app_packages:0}));
"""
    env=os.environ.copy();env.pop('NODE_PATH',None)
    result=subprocess.run(['node','--input-type=module','-',str(ROOT)],input=program,text=True,capture_output=True,timeout=30,env=env)
    assert result.returncode==0,result.stderr
    return json.loads(result.stdout)


def main():
    destination=ROOT/'.runtime/standalone-audit'/secrets.token_hex(4);destination.mkdir(parents=True)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.pop('NODE_PATH',None)
    env.update(SCZX_TASK_WORKERS='0',LANGSMITH_TRACING='false',SCZX_DB_NAME='sczx_standalone_audit',SCZX_DB_SOCKET=str(destination/'no-database.sock'))
    try:
        result=subprocess.run([str(ROOT/'.venv/bin/python'),'-I',str(Path(__file__).resolve()),'--python-probe'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
    except subprocess.TimeoutExpired as error:
        (destination/'python.log').write_text((error.stderr or b'').decode() if isinstance(error.stderr,bytes) else (error.stderr or ''))
        raise
    (destination/'python.log').write_text(result.stderr)
    assert result.returncode==0,result.stderr
    python=json.loads(result.stdout)
    links=[]
    for source in ['backend/sczx_api','algorithms','frontend/src']:
        for path in (ROOT/source).rglob('*'):
            if path.is_symlink() and not path.resolve().is_relative_to(ROOT):links.append(str(path.relative_to(ROOT)))
    assert not links,links
    config=(ROOT/'.venv/pyvenv.cfg').read_text()
    assert 'include-system-site-packages = false' in config
    report={'success':True,'python':python,'node':node_probe(),'source_symlinks_outside_project':links,'system_site_packages':False,'scope':'runtime imports, local calculation and own locked dependencies; deployment DB/model configuration remains explicit'}
    (destination/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'success':True,'report':str(destination/'report.json')},ensure_ascii=False))

if __name__=='__main__':
    if '--python-probe' in sys.argv:print(json.dumps(python_probe(),ensure_ascii=False))
    else:main()
