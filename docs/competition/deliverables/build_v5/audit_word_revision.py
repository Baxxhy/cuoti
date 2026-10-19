from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
import json,re,hashlib
B=Path(__file__).resolve().parent;O=B.parent
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';ns={'w':W};q=lambda x:'{'+W+'}'+x
report={}
for f in O.glob('*_参赛定稿.docx'):
 with ZipFile(f) as z: parts={n:z.read(n) for n in z.namelist()}
 root=E.fromstring(parts['word/document.xml']);styles=E.fromstring(parts['word/styles.xml'])
 # Explicit font assignments survive LibreOffice fallback during directory update.
 for st in styles.xpath('//w:style',namespaces=ns):
  sid=st.get(q('styleId'),'');family='SimHei' if sid in ['Heading1','Heading2','Title'] else 'SimSun'
  rp=st.find(q('rPr'))
  if rp is None:rp=E.SubElement(st,q('rPr'))
  ft=rp.find(q('rFonts'))
  if ft is None:ft=E.SubElement(rp,q('rFonts'))
  ft.attrib.clear()
  for k in ['ascii','hAnsi','eastAsia','cs']:ft.set(q(k),family)
 for p in root.xpath('//w:p',namespaces=ns):
  sid=p.xpath('string(w:pPr/w:pStyle/@w:val)',namespaces=ns);family='SimHei' if sid in ['Heading1','Heading2','Title'] else 'SimSun'
  for r in p.xpath('.//w:r',namespaces=ns):
   rp=r.find(q('rPr'))
   if rp is None:rp=E.Element(q('rPr'));r.insert(0,rp)
   ft=rp.find(q('rFonts'))
   if ft is None:ft=E.SubElement(rp,q('rFonts'))
   ft.attrib.clear()
   for k in ['ascii','hAnsi','eastAsia','cs']:ft.set(q(k),family)
 # Remove unused header/footer references and content, including generated page fields.
 for e in root.xpath('//w:headerReference|//w:footerReference',namespaces=ns):e.getparent().remove(e)
 for n in list(parts):
  if re.match(r'word/(header|footer)\d+\.xml$',n):
   r=E.fromstring(parts[n]);r.clear();parts[n]=E.tostring(r,encoding='UTF-8',xml_declaration=True)
 for e in root.xpath('//w:pBdr',namespaces=ns):e.getparent().remove(e)
 for e in styles.xpath('//w:pBdr',namespaces=ns):e.getparent().remove(e)
 parts['word/document.xml']=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
 parts['word/styles.xml']=E.tostring(styles,encoding='UTF-8',xml_declaration=True,standalone=True)
 for n in parts:
  if n.startswith('word/') and n.endswith('.xml'):
   r=E.fromstring(parts[n])
   for c in r.xpath('//w:color',namespaces=ns):c.attrib.clear();c.set(q('val'),'000000')
   parts[n]=E.tostring(r,encoding='UTF-8',xml_declaration=True,standalone=True)
 with ZipFile(f,'w',ZIP_DEFLATED) as z:
  for n,b in parts.items():z.writestr(n,b)
 texts=root.xpath('//w:t/text()',namespaces=ns);alltext=''.join(texts)
 assert '附录' not in alltext
 headings=[];captions=[]
 for p in root.xpath('//w:p',namespaces=ns):
  text=''.join(p.xpath('.//w:t/text()',namespaces=ns));sid=p.xpath('string(w:pPr/w:pStyle/@w:val)',namespaces=ns)
  if sid in ['Heading1','Heading2','Heading3','Heading4']:
   assert '：' not in text and '、' not in text,(f.name,text);headings.append(text)
  if re.match(r'^[图表]\d+\s',text):
   assert p.xpath('string(w:pPr/w:jc/@w:val)',namespaces=ns)=='center',(f.name,text);captions.append(text)
 tables=root.xpath('//w:tbl',namespaces=ns)
 for t in tables:
  # Word may distribute explicit borders to individual cells after save.
  has_grid=all(all(c.xpath('w:tcPr/w:tcBorders/w:'+edge+'[@w:val="single"]',namespaces=ns) for edge in ['top','bottom','start','end']) for c in t.xpath('.//w:tc',namespaces=ns))
  assert has_grid,(f.name,'missing table borders')
 colors=[]
 for n,b in parts.items():
  if n.startswith('word/') and n.endswith('.xml'):
   r=E.fromstring(b);colors+=r.xpath('//w:color/@w:val',namespaces=ns)
 assert set(colors)=={'000000'}
 assert not root.xpath('//w:headerReference|//w:footerReference',namespaces=ns)
 assert not re.search(r'\[(?:E|R)\d{2}\]',alltext),'dangling reference code'
 report[f.name]={'headings':headings,'captions':captions,'tables':len(tables),'images':len(root.xpath('//*[local-name()="blip"]')),'fonts':['SimSun','SimHei'],'all_editable_text_black':True,'no_appendix':True,'no_headers_footers':True,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
(B/'word_revision_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({n:{k:v for k,v in r.items() if k not in ['headings','captions']} for n,r in report.items()},ensure_ascii=False,indent=2))
