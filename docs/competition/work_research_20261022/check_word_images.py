from pathlib import Path
from zipfile import ZipFile
from PIL import Image
from io import BytesIO
import hashlib,json,re
B=Path(__file__).resolve().parent;O=B.parent/'deliverables/研究重构版'

def fingerprint(data):
 im=Image.open(BytesIO(data)).convert('RGBA');return (im.size,hashlib.sha256(im.tobytes()).hexdigest())
paths=set()
for source in [B/'product.md',B/'system.md']:
 for group in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',source.read_text()):
  for path in group.split('|'):paths.add(O/path)
expected={fingerprint(p.read_bytes()):str(p.relative_to(O)) for p in paths}
seen=set();report={}
for f in O.glob('*_研究重构版.docx'):
 rows=[]
 with ZipFile(f) as z:
  for n in z.namelist():
   if n.startswith('word/media/'):
    key=fingerprint(z.read(n));assert key in expected,(f.name,n,'unmatched image');seen.add(key);rows.append({'embedded':n,'source':expected[key],'pixel_exact':True})
 report[f.name]=rows
assert seen==set(expected),(len(seen),len(expected))
(B/'word_images_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(f'All {len(expected)} diagram/screenshot images match source pixels exactly')
