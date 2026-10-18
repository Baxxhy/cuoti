from pathlib import Path
import zipfile,json,hashlib
B=Path(__file__).resolve().parent;O=B.parent;D=O/'figures/academic_v4'
files=list(O.glob('*_图文新版.docx'))+list(O.glob('*_图文新版.md'))+[O/'图文新版交付说明.md']+list(D.glob('[0-9][0-9].png'))+list(D.glob('*_final_prompt.txt'))+[D/'提示词与图表说明.md']+list((O/'figures/screenshots').glob('*-detail.png'))
target=O/'错题帮_仓颉杯Word图文新版.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
 for f in files:z.write(f,str(f.relative_to(O)))
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None
 assert not any(n.endswith('.pdf') or n.startswith(('review/','originals/','build_')) for n in z.namelist())
 for f in files:assert z.read(str(f.relative_to(O)))==f.read_bytes()
report={'zip':target.name,'files':len(files),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'crc_ok':True,'matches_sources':True}
(B/'package_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(report)
