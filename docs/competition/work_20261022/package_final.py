"""Allowlisted competition document package; excludes internal review and data."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib,json,re
B=Path(__file__).resolve().parent;O=B.parent/'deliverables'
files=[]
for kind in ['项目说明文档','系统设计文档']:
 for ext in ['docx','md']:files.append(O/('错题帮_'+kind+'_重写终稿.'+ext))
files += [O/x for x in ['交付说明.md','证据与来源.md','运行与依赖说明.md','figures/图表说明.md']]
for i in range(1,11):files.extend([O/'figures'/f'{i:02d}.png',O/'figures'/f'{i:02d}_prompt.txt'])
screenshot_paths=set()
for source in ['product.md','system.md']:
 for group in re.findall(r'!\[[^]]*\]\(([^)]+)\)',(B/source).read_text()):
  screenshot_paths.update(x for x in group.split('|') if x.startswith('figures/screenshots/'))
files += [O/x for x in sorted(screenshot_paths)]
assert all(p.is_file() for p in files)
names={p.relative_to(O).as_posix() for p in files}
for p in files:
 if p.suffix=='.md':
  for target in re.findall(r'!?\[[^]]*\]\(([^)]+)\)',p.read_text()):
   if not target.startswith(('https://','http://','#')):assert (p.parent/target).is_file(),(p,target)
zipout=O/'错题帮_仓颉杯参赛文档最终版.zip'
with ZipFile(zipout,'w',ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(files):z.write(p,p.relative_to(O).as_posix())
with ZipFile(zipout) as z:
 assert z.testzip() is None
 assert set(z.namelist())==names
 for p in files:assert z.read(p.relative_to(O).as_posix())==p.read_bytes()
report={'zip':zipout.name,'sha256':hashlib.sha256(zipout.read_bytes()).hexdigest(),'bytes':zipout.stat().st_size,'files':[{'path':p.relative_to(O).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)],'count':len(files),'crc_and_byte_comparison':True,'no_internal_review_or_secrets':True,'local_md_links_exist':True}
(B/'package_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(zipout,len(files),zipout.stat().st_size,'bytes, CRC and all member bytes verified')
