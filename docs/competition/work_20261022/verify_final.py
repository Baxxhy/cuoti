from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import json,hashlib,re
B=Path(__file__).resolve().parent;O=B.parent/'deliverables'
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
report={}
for f in O.glob('*_重写终稿.docx'):
 with ZipFile(f) as z:
  d=E.fromstring(z.read('word/document.xml'));s=E.fromstring(z.read('word/styles.xml'))
  styles={x.get('{'+ns['w']+'}styleId'):x for x in s.xpath('//w:style',namespaces=ns)}
  def stylefont(sid):
   seen=set()
   while sid and sid not in seen:
    seen.add(sid);st=styles.get(sid)
    if st is None:return None
    v=st.xpath('w:rPr/w:rFonts/@w:eastAsia',namespaces=ns)
    if v:return v[0]
    sid=st.xpath('string(w:basedOn/@w:val)',namespaces=ns)
   return None
  colors=[];runs=0
  for n in z.namelist():
   if n.startswith('word/') and n.endswith('.xml'):
    r=E.fromstring(z.read(n));colors+=r.xpath('//w:color/@w:val',namespaces=ns)
  assert set(colors)=={'000000'}
  for p in d.xpath('//w:p',namespaces=ns):
   sid=p.xpath('string(w:pPr/w:pStyle/@w:val)',namespaces=ns) or 'Normal'
   expected='SimHei' if sid in ['Heading1','Heading2','Title'] else 'SimSun'
   for r in p.xpath('.//w:r[w:t]',namespaces=ns):
    direct=r.xpath('w:rPr/w:rFonts/@w:eastAsia',namespaces=ns)
    cs=r.xpath('string(w:rPr/w:rStyle/@w:val)',namespaces=ns)
    effective=direct[0] if direct else stylefont(cs) or stylefont(sid) or stylefont('Normal')
    assert effective==expected,(f.name,sid,cs,effective);runs+=1
   text=''.join(p.xpath('.//w:t/text()',namespaces=ns))
   if re.match(r'^[图表]\d+\s',text):assert p.xpath('string(w:pPr/w:jc/@w:val)',namespaces=ns)=='center'
  assert not d.xpath('//w:headerReference|//w:footerReference',namespaces=ns)
  text=''.join(d.xpath('//w:t/text()',namespaces=ns))
  assert '附录' not in text and '[[AUTO_TOC]]' not in text and '源码基线950ce87' in text
  for c in d.xpath('//w:tbl//w:tc',namespaces=ns):
   assert all(c.xpath('w:tcPr/w:tcBorders/w:'+edge+'[@w:val="single"]',namespaces=ns) for edge in ['top','bottom','start','end'])
  report[f.name]={'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'editable_text_black':True,'effective_font_runs_checked':runs,'fonts':['SimSun','SimHei'],'no_headers_footers':True,'no_appendix':True,'full_grid_tables':True,'centered_captions':True,'source_baseline':'950ce87'}
(B/'final_readonly_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
