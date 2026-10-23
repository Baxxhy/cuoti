from pathlib import Path
import shutil,subprocess,os,re,json
R=Path(__file__).resolve().parents[2];D=R/'.runtime/competition-package/context';P=D/'payload';P.mkdir(parents=True,exist_ok=True)
def cp(src,dst):
 src=Path(src);dst=P/dst
 if src.is_dir():shutil.copytree(src,dst,dirs_exist_ok=True,symlinks=True,ignore=shutil.ignore_patterns('__pycache__','.git','.pytest_cache','tests'))
 else:dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
cp(R/'backend-algorithms','app/backend-algorithms');cp(R/'backend-cangjie/schema','app/backend-cangjie/schema');cp(R/'backend-cangjie/target/release/bin/main','app/backend-cangjie/main');cp(R/'frontend/dist/build/h5','app/web');cp(R/'scripts/retrieval_inference_server.py','app/scripts/retrieval_inference_server.py');cp(R/'config/api_pool.example.json','app/config/api_pool.json')
# Package just interpreter/stdlib and the application venv, never base site-packages or user configuration.
cp('/root/miniconda3/bin/python3.13','python/bin/python3.13')
stdlib=Path('/root/miniconda3/lib/python3.13')
for f in stdlib.iterdir():
 if f.name not in ('site-packages','__pycache__','test','tests','idlelib','tkinter','turtledemo'):cp(f,'python/lib/python3.13/'+f.name)
cp(R/'.venv/lib/python3.13/site-packages','python/lib/python3.13/site-packages')
for f in list((P/'python').rglob('*.pth')):
 if '__editable__' in f.name:f.unlink()
for f in list((P/'python').rglob('__editable__*')):
 if f.is_file():f.unlink()
for root in [R/'.runtime/cangjie/cangjie/runtime/lib/linux_x86_64_cjnative',R/'.runtime/cangjie/linux_x86_64_cjnative/dynamic/stdx']:
 for f in root.glob('*.so*'):cp(f,'native/'+f.name)
cp(R/'.runtime/mysql-client/libzhiwei_mysql.so','native/libzhiwei_mysql.so')
for f in ('mysqld','mysql','mysqladmin'):
 path=shutil.which(f);cp(path,'mysql/bin/'+f)
cp('/usr/share/mysql','mysql/share');cp('/usr/lib/mysql/plugin','mysql/lib/plugin')
cp('/etc/ssl/certs/ca-certificates.crt','certs/ca-certificates.crt')
cp('/usr/share/fonts/truetype/dejavu','fonts/dejavu')
# Resolve non-glibc shared-library dependencies without baking machine paths into the startup commands.
paths=[str(R/'.runtime/mysql-client/root/usr/lib/x86_64-linux-gnu'),'/root/miniconda3/lib',str(P/'native')]
env={**os.environ,'LD_LIBRARY_PATH':':'.join(paths)}
exclude=re.compile(r'^(libc\.so|libm\.so|libpthread\.so|libdl\.so|librt\.so|libutil\.so|libresolv\.so|ld-linux)')
files=[P/'app/backend-cangjie/main',P/'python/bin/python3.13',*list((P/'native').glob('*.so*')),*list((P/'mysql/bin').iterdir()),*list((P/'python/lib/python3.13/lib-dynload').glob('*.so')), *list((P/'python/lib/python3.13/site-packages/cv2').glob('*.so')), *list((P/'python/lib/python3.13/site-packages/ctranslate2').glob('*.so')), *list((P/'python/lib/python3.13/site-packages/PIL').glob('*.so'))]
seen=set()
while files:
 f=files.pop()
 if str(f) in seen:continue
 seen.add(str(f))
 out=subprocess.run(['ldd',str(f)],env=env,text=True,capture_output=True).stdout
 for name,path in re.findall(r'\s+(\S+) => (/\S+)',out):
  if exclude.match(name):continue
  target=P/'native'/name
  if not target.exists():cp(path,'native/'+name);files.append(target)
# Retain runtime license notices.
for src in [R/'.runtime/cangjie/cangjie/LICENSE',Path('/usr/share/doc/mysql-server/copyright'),Path('/root/miniconda3/lib/python3.13/LICENSE.txt')]:
 if src.exists():cp(src,'licenses/'+src.parent.name+'-'+src.name)
cp('/lib/x86_64-linux-gnu/libtinfo.so.6','native/libtinfo.so.6')
cp(R/'deployment/competition','app/deployment')
shutil.copy2(R/'deployment/competition/Dockerfile',D/'Dockerfile')
print('core payload ready',flush=True)
