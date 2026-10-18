from pathlib import Path
import zipfile,json,hashlib,re
B=Path(__file__).resolve().parent;O=B.parent;files={}
for p in O.glob('*_修订版.docx'):files[p.name]=p
assert len(files)==2
for p in O.glob('*_修订版.md'):files[p.name]=p
for folder in ['figures/restructured','figures/screenshots']:
 for p in (O/folder).rglob('*'):
  if not p.is_file():continue
  if p.suffix in ['.svg','.png'] or (folder.endswith('restructured') and ('prompts' in p.parts or p.name in ['titles.json','Sivia绘图提示词与参考.md'])) or p.name in ['provenance.json','README.md']:files[str(p.relative_to(O))]=p
files['figures/render_figures.py']=B/'render_figures.py'
files['本轮交付说明.md']=O/'Word修订版交付说明.md'
for n,p in files.items():
 assert p.suffix!='.pdf' and not any(x in n for x in ['review/','originals/','api_pool','_raw','page_previews'])
 if p.suffix in ['.md','.py','.svg','.json']:assert not re.search(r'\b(?:sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{25,})',p.read_text()),n
zpath=O/'错题帮_仓颉杯Word修订版.zip'
with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for n,p in sorted(files.items()):z.write(p,n)
with zipfile.ZipFile(zpath) as z:
 assert z.testzip() is None
 for n,p in files.items():assert z.read(n)==p.read_bytes()
m={'archive':zpath.name,'bytes':zpath.stat().st_size,'sha256':hashlib.sha256(zpath.read_bytes()).hexdigest(),'files':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()},'pdf_included':False}
(B/'word_package_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2));print('ZIP verified:',len(files),'files',m['bytes'],'bytes')
