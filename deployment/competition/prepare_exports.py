"""Collect the already verified host formula export runtime for the delivery image."""
from pathlib import Path
import shutil,subprocess,re,os
R=Path(__file__).resolve().parents[2];D=R/'.runtime/competition-package/export-context';P=D/'payload'
def cp(src,dest):
 src=Path(src);dst=P/dest;dst.parent.mkdir(parents=True,exist_ok=True)
 if src.is_dir():shutil.copytree(src,dst,symlinks=True,dirs_exist_ok=True)
 else:shutil.copy2(src,dst)
cp(shutil.which('node'),'opt/python/bin/node')
for f in ('package.json','node_modules','src/utils','.playwright-browsers/chromium-1234','.playwright-libs'):
 cp(R/'frontend'/f,'opt/app/frontend/'+f)
cp(R/'scripts/render_math_pdf.cjs','opt/app/scripts/render_math_pdf.cjs')
cp('/usr/share/fonts/opentype/noto','usr/share/fonts/opentype/noto')
cp('/etc/fonts','etc/fonts')
files=[P/'opt/python/bin/node',P/'opt/app/frontend/.playwright-browsers/chromium-1234/chrome-linux64/chrome']
seen=set();exclude=re.compile(r'^(libc\.so|libm\.so|libpthread\.so|libdl\.so|librt\.so|libutil\.so|libresolv\.so|ld-linux)')
env={**os.environ,'LD_LIBRARY_PATH':str(R/'frontend/.playwright-libs/root/usr/lib/x86_64-linux-gnu')}
while files:
 f=files.pop()
 if str(f) in seen:continue
 seen.add(str(f))
 out=subprocess.run(['ldd',str(f)],env=env,text=True,capture_output=True).stdout
 for name,path in re.findall(r'\s+(\S+) => (/\S+)',out):
  if exclude.match(name):continue
  target=P/'opt/native'/name
  if not target.exists() and not (R/'.runtime/competition-package/context/payload/native'/name).exists() and not (R/'.runtime/competition-package/patch/native'/name).exists():cp(path,'opt/native/'+name);files.append(target)
(D/'Dockerfile').write_text('FROM cuoti-submission:20261023\nCOPY payload/ /\n')
print('Formula export runtime collected')
