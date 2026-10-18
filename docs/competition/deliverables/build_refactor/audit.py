from pathlib import Path
from zipfile import ZipFile
from lxml import etree
import fitz,json,hashlib,re
from PIL import Image,ImageDraw
B=Path(__file__).resolve().parent;O=B.parent
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
result={'date':'2026-10-18','documents':{},'figures':{},'originals_unchanged':True}
for n,h in json.loads((O/'originals/2026-10-18_before_deep_refactor/sha256.json').read_text()).items():
 assert hashlib.sha256((O/n).read_bytes()).hexdigest()==h,n+' original changed'
for f in sorted(O.glob('*_重构终稿.docx')):
 bad=[];text=[]
 with ZipFile(f) as z:
  for n in z.namelist():
   if n.startswith('word/') and n.endswith('.xml'):
    r=etree.fromstring(z.read(n))
    for c in r.xpath('//w:color',namespaces=ns):
     if c.get('{'+ns['w']+'}val')!='000000' or any('theme' in k.lower() for k in c.attrib):bad.append((n,dict(c.attrib)))
    if n=='word/document.xml':text=r.xpath('//w:t/text()',namespaces=ns)
 assert not bad,bad[:10]
 p=fitz.open(f.with_suffix('.pdf'));colors=set();render=B/'page_previews'/f.stem;render.mkdir(parents=True,exist_ok=True);thin=[];outs=[];pdftext=''
 for old in render.glob('*.png'):old.unlink()
 for i,page in enumerate(p):
  t=page.get_text();pdftext+=page.get_text(clip=fitz.Rect(0,45,page.rect.width,page.rect.height-45))
  if len(t.strip())<80:thin.append(i+1)
  for block in page.get_text('dict')['blocks']:
   for line in block.get('lines',[]):
    for span in line['spans']:
     colors.add(span['color'])
     if span['bbox'][0]<20 or span['bbox'][2]>page.rect.width-20:outs.append((i+1,span['text']))
  page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).save(render/f'{i+1:02}.png')
 assert colors=={0},colors
 thumbs=[]
 for im in sorted(render.glob('*.png')):
  img=Image.open(im).convert('RGB');img.thumbnail((210,297));tile=Image.new('RGB',(230,325),'#dddddd');tile.paste(img,((230-img.width)//2,8));ImageDraw.Draw(tile).text((10,305),im.stem,fill='black');thumbs.append(tile)
 sheet=Image.new('RGB',(230*5,325*((len(thumbs)+4)//5)),'white')
 for i,im in enumerate(thumbs):sheet.paste(im,((i%5)*230,(i//5)*325))
 sheet.save(B/(f.stem+'_contact.png'))
 # Ignore generated TOC and numeric fields, compare each substantive source paragraph in reading order.
 norm=lambda x:re.sub(r'\s+','',x)
 full=norm(pdftext);missing=[t for t in text if len(norm(t))>35 and norm(t) not in full]
 result['documents'][f.name]={'pages':len(p),'pdf_text_colors':list(colors),'docx_color_errors':bad,'thin_pages':thin,'horizontal_overflow':outs,'source_fragments_not_found':missing[:15],'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
 for suffix in ['.docx','.pdf','.md']:
  q=f.with_suffix(suffix);result['documents'][f.name][suffix+'_sha256']=hashlib.sha256(q.read_bytes()).hexdigest()
for f in sorted((O/'figures/restructured').glob('*.svg')):
 r=etree.fromstring(f.read_bytes());texts=r.xpath('//*[local-name()="text"]');bad=[e.text for e in texts if e.get('fill')!='#000000'];assert not bad,(f,bad)
 result['figures'][f.stem]={'text_labels':len(texts),'black':True,'png_exists':f.with_suffix('.png').exists()}
(B/'quality_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
