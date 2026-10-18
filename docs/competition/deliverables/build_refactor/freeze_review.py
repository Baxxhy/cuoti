from pathlib import Path
import sys,json,hashlib,shutil
O=Path(__file__).resolve().parent.parent;R=O/'review'/('round'+sys.argv[1]);R.mkdir(parents=True,exist_ok=True);m={}
for f in O.glob('*_重构终稿.*'):
 shutil.copy2(f,R/f.name);m[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
for f in (O/'figures/restructured').glob('*'):
 if f.suffix in ['.svg','.png','.json']:
  q=R/'figures'/f.name;q.parent.mkdir(exist_ok=True);shutil.copy2(f,q);m['figures/'+f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
(R/'输入版本.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
print('frozen',R,len(m),'files')
