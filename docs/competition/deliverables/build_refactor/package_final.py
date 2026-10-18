from pathlib import Path
import zipfile,hashlib,json,re
O=Path(__file__).resolve().parent.parent;archive=O/'错题帮_仓颉杯参赛文档最终版.zip';files={}
for p in O.glob('*_重构终稿.*'):
 if p.suffix in ['.docx','.pdf','.md']:files[p.name]=p
assert len(files)==6
for p in (O/'figures/restructured').glob('*'):
 if p.suffix in ['.svg','.png'] or p.name in ['README.md','titles.json','图表编号对照.md']:files[str(p.relative_to(O))]=p
files['figures/render_figures.py']=O/'build_refactor/render_figures.py'
for n in ['运行与第三方依赖说明.md','正式交付导航.md']:files[n]=O/n
for n,p in files.items():
 assert not any(x in n for x in ['review/','originals/','api_pool','_raw','page_previews']),n
 if p.suffix in ['.md','.py','.svg','.json']:
  t=p.read_text();assert not re.search(r'\b(?:sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{25,})',t),n
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for n,p in sorted(files.items()):z.write(p,n)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for n,p in files.items():assert z.read(n)==p.read_bytes(),n
manifest={'archive':archive.name,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'file_count':len(files),'files':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sorted(files.items())},'excludes':['原始备份','内部评审报告与各轮快照','临时预览和内部审计','业务数据和运行配置','实际凭据']}
(O/'build_refactor/final_package_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print({k:v for k,v in manifest.items() if k!='files'})
