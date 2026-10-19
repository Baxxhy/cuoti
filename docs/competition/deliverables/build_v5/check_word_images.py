from pathlib import Path
from zipfile import ZipFile
from PIL import Image
from io import BytesIO
import hashlib,json
B=Path(__file__).resolve().parent;O=B.parent

def fingerprint(data):
 im=Image.open(BytesIO(data)).convert('RGBA');return (im.size,hashlib.sha256(im.tobytes()).hexdigest())
expected={fingerprint(p.read_bytes()):str(p.relative_to(O)) for p in list((O/'figures/academic_v5').glob('[0-9][0-9].png'))+list((O/'figures/screenshots').glob('*-detail.png'))}
seen=set();report={}
for f in O.glob('*_参赛定稿.docx'):
 rows=[]
 with ZipFile(f) as z:
  for n in z.namelist():
   if n.startswith('word/media/'):
    key=fingerprint(z.read(n));assert key in expected,(f.name,n,'unmatched image');seen.add(key);rows.append({'embedded':n,'source':expected[key],'pixel_exact':True})
 report[f.name]=rows
assert seen==set(expected),(len(seen),len(expected))
(B/'word_images_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('All 19 diagram/screenshot images match source pixels exactly')
