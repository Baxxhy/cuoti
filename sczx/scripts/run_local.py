"""Start only this directory's web, business and algorithm processes."""
import os
from pathlib import Path
import subprocess
import signal
import sys
import time
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]


def stop_on_signal(signum,frame):
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM,stop_on_signal)
    load_dotenv(ROOT/'.env',override=False)
    env=os.environ.copy()
    env.pop('PYTHONPATH',None)
    for key in ['SCZX_AUTH_SECRET','SCZX_ALGORITHM_SECRET']:
        if len(env.get(key,''))<32:raise SystemExit(f'请在 sczx/.env 设置至少32字符的 {key}')
    if not env.get('SCZX_DB_NAME','').startswith('sczx_'):raise SystemExit('请配置 sczx_ 前缀的独立 MySQL 数据库')
    ports={key:int(env.get(key,default)) for key,default in [('SCZX_ALGORITHM_PORT','8012'),('SCZX_BACKEND_PORT','8010'),('SCZX_WEB_PORT','5176')]}
    if len(set(ports.values()))!=3 or any(not 1<=p<=65535 for p in ports.values()):raise SystemExit('三个服务端口必须不同，且处于1至65535之间')
    env['SCZX_ALGORITHM_URL']=f"http://127.0.0.1:{ports['SCZX_ALGORITHM_PORT']}"
    env['SCZX_BACKEND_URL']=f"http://127.0.0.1:{ports['SCZX_BACKEND_PORT']}"
    env.setdefault('SCZX_MEDIA_ROOT',str(ROOT/'.runtime/media'))
    if not env.get('SCZX_API_POOL_PATH'):env.pop('SCZX_API_POOL_PATH',None)
    python=ROOT/'.venv/bin/python';vite=ROOT/'frontend/node_modules/vite/bin/vite.js'
    if not python.exists() or not vite.exists():raise SystemExit('请先运行 bash scripts/setup.sh 安装依赖')
    commands=[('算法',[str(python),'-m','uvicorn','service:create_app','--factory','--app-dir',str(ROOT/'algorithms'),'--host','127.0.0.1','--port',str(ports['SCZX_ALGORITHM_PORT'])],ROOT),('业务',[str(python),'-m','uvicorn','sczx_api.main:app','--app-dir',str(ROOT/'backend'),'--host','127.0.0.1','--port',str(ports['SCZX_BACKEND_PORT'])],ROOT),('网页',['node',str(vite),'--host','127.0.0.1','--port',str(ports['SCZX_WEB_PORT']),'--strictPort'],ROOT/'frontend')]
    children=[]
    try:
        for name,command,cwd in commands:children.append((name,subprocess.Popen(command,cwd=cwd,env=env)))
        print(f"网页：http://127.0.0.1:{ports['SCZX_WEB_PORT']}；按 Ctrl+C 停止本次启动的服务。",flush=True)
        while True:
            for name,child in children:
                if child.poll() is not None:raise SystemExit(f'{name}服务已退出，请检查上方错误信息。')
            time.sleep(.5)
    except KeyboardInterrupt:pass
    finally:
        for _,child in reversed(children):
            if child.poll() is None:child.terminate()
        for _,child in reversed(children):
            try:child.wait(timeout=8)
            except subprocess.TimeoutExpired:child.kill();child.wait()


if __name__=='__main__':main()
