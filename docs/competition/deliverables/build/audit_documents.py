from pathlib import Path
import fitz,zipfile,xml.etree.ElementTree as ET,re,json,hashlib,runpy
B=Path(__file__).resolve().parent;O=B.parent;R=O.parents[2]
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
def norm(s):return re.sub(r'\s+|\u00ad|\u200b','',s)
manifest=runpy.run_path(str(B/'build_documents.py'))
missing=[]
for code,title,paths in manifest['E']:
 for path in paths.split('；'):
  if not (R/path).exists():missing.append(path)
assert not missing,missing
summary=[]
for label,module,limits in [('项目说明文档','project_content.py',(30,35)),('系统设计文档','system_content.py',(50,55))]:
 name='错题帮_'+label;pdf=fitz.open(O/(name+'.pdf'));text='\n'.join(p.get_text(clip=fitz.Rect(0,45,p.rect.width,p.rect.height-45)) for p in pdf);flat=norm(text)
 assert limits[0]<=len(pdf)<=limits[1],(label,len(pdf))
 assert not re.search(r'\[\[AUTO_TOC\]\]|TODO:|\{\{[^}]+\}\}|组员[ABC](?=\s|$)',text)
 with zipfile.ZipFile(O/(name+'.docx')) as z:
  root=ET.fromstring(z.read('word/document.xml'))
  assert root.findall('.//w:sdt',ns) or b'TOC' in z.read('word/document.xml')
  headers=''.join(z.read(n).decode() for n in z.namelist() if re.match(r'word/footer\d+.xml',n))
  assert 'PAGE' in headers and 'NUMPAGES' in headers
  para=[norm(''.join(p.itertext())) for p in root.findall('.//w:p',ns)]
  ptexts=[norm(''.join(t.text or '' for t in p.findall('.//w:t',ns))) for p in root.findall('.//w:p',ns)]
  ptexts=[p for p in ptexts if len(p)>24 and not re.search(r'\.{3,}',p)]
  absent=[p[:100] for p in ptexts if p not in flat]
  assert not absent,absent[:5]
  images=root.findall('.//wp:inline',ns)
 pages=[];out=B/'page_previews'/name;out.mkdir(parents=True,exist_ok=True)
 for i,page in enumerate(pdf):
  assert len(page.get_text().strip())>100,('短页',name,i+1)
  boxes=[]
  for block in page.get_text('dict')['blocks']:
   if block['type']==0:
    for line in block['lines']:
     for span in line['spans']:
      b=fitz.Rect(span['bbox']);assert b.x0>=12 and b.y0>=5 and b.x1<=page.rect.width-10 and b.y1<=page.rect.height-8,('越界',name,i+1,span['text'][:40])
   else:boxes.append(block['bbox'])
  for info in page.get_image_info():
   b=fitz.Rect(info['bbox']);assert b.x0>=10 and b.x1<=page.rect.width-10 and b.y1<=page.rect.height-15
   assert 13*b.width/640>=9,('图字过小',name,i+1,b.width)
  page.get_pixmap(matrix=fitz.Matrix(.8,.8),alpha=False).save(out/f'{i+1:02d}.png')
  pages.append({'page':i+1,'characters':len(page.get_text()),'image_count':len(boxes)})
 info={'document':name,'pages':len(pdf),'characters':len(text),'inline_images':len(images),'docx_pdf_text_matched':True,'page_bounds_passed':True,'all_pages_rendered':True,'sha256':{ext:hashlib.sha256((O/(name+'.'+ext)).read_bytes()).hexdigest() for ext in ['docx','pdf','md']},'page_checks':pages}
 summary.append(info)
assert sum(s['inline_images'] for s in summary)==16
(B/'quality_manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps([{k:v for k,v in s.items() if k!='page_checks'} for s in summary],ensure_ascii=False))
