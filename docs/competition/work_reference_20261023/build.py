"""Build independent, editable Word reports. No business files are touched."""
from pathlib import Path
import re,json,zipfile
from lxml import etree as E
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from PIL import Image
B=Path(__file__).resolve().parent; O=B.parent/'deliverables/背景与图示修订版'
BLACK=RGBColor(0,0,0)
def font(r,name='SimSun',size=None,bold=None):
 r.font.name=name;r.font.color.rgb=BLACK
 f=r._element.get_or_add_rPr().rFonts
 for a in ['ascii','hAnsi','eastAsia','cs']:f.set(qn('w:'+a),name)
 for a in ['asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme']:f.attrib.pop(qn('w:'+a),None)
 if size:r.font.size=Pt(size)
 if bold is not None:r.bold=bold
def inline(p,text,size=14):
 for token in re.split(r'(\[[^\]]+\]\([^\s)]+\)|\*\*.*?\*\*|`[^`]+`)',text):
  m=re.fullmatch(r'\[([^\]]+)\]\(([^\s)]+)\)',token)
  if m:
   h=OxmlElement('w:hyperlink');h.set(qn('r:id'),p.part.relate_to(m[2],RT.HYPERLINK,is_external=True))
   r=OxmlElement('w:r');rp=OxmlElement('w:rPr');f=OxmlElement('w:rFonts')
   for a in ['ascii','hAnsi','eastAsia','cs']:f.set(qn('w:'+a),'SimSun')
   rp.append(f)
   for tag,val in [('color','000000'),('sz',str(int(size*2))),('u','none')]:
    e=OxmlElement('w:'+tag);e.set(qn('w:val'),val);rp.append(e)
   r.append(rp);t=OxmlElement('w:t');t.text=m[1];r.append(t);h.append(r);p._p.append(h)
  else:
   t=token[2:-2] if token.startswith('**') else token[1:-1] if token.startswith('`') else token
   font(p.add_run(t.replace('<br>','\n')),size=size,bold=token.startswith('**'))
def black_xml(p):
 ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
 with zipfile.ZipFile(p) as z:data={n:z.read(n) for n in z.namelist()}
 for n,b in list(data.items()):
  if not n.startswith('word/') or not n.endswith('.xml'):continue
  root=E.fromstring(b)
  for e in root.xpath('//w:color',namespaces=ns):e.attrib.clear();e.set(qn('w:val'),'000000')
  for e in root.xpath('//w:rPr',namespaces=ns):
   if e.find(qn('w:color')) is None:E.SubElement(e,qn('w:color')).set(qn('w:val'),'000000')
  for e in root.xpath('//a:rPr|//a:defRPr|//a:endParaRPr',namespaces=ns):
   for c in list(e):
    if E.QName(c).localname in ['solidFill','gradFill']:e.remove(c)
   f=E.SubElement(e,'{'+ns['a']+'}solidFill');E.SubElement(f,'{'+ns['a']+'}srgbClr').set('val','000000')
  data[n]=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
 with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in data.items():z.writestr(n,b)
def bibliography(text):
 refs=json.loads((B/'references.json').read_text());order=[]
 def sub(m):
  k=m[1]
  if k not in refs:raise ValueError(k)
  if k not in order:order.append(k)
  return '['+str(order.index(k)+1)+']'
 text=re.sub(r'\[\s*@([a-z_]+)\s*\]',sub,text)
 text+='\n\n## 参考文献\n\n'+'\n\n'.join(f'[{i+1}] {refs[k]}' for i,k in enumerate(order))+'\n'
 return text,order
def build(key,kind):
 text,refkeys=bibliography((B/(key+'.md')).read_text())
 name='错题帮_'+kind+'_背景与图示修订版'
 (O/(name+'.md')).write_text(text)
 d=Document();s=d.sections[0]
 s.page_width=Cm(21);s.page_height=Cm(29.7);s.top_margin=Cm(2.1);s.bottom_margin=Cm(2.1);s.left_margin=s.right_margin=Cm(2.3)
 for st in d.styles:
  if st.type in (1,2):
   st.font.name='SimSun';st.font.color.rgb=BLACK
   f=st.element.get_or_add_rPr().rFonts
   for a in ['ascii','hAnsi','eastAsia','cs']:f.set(qn('w:'+a),'SimSun')
   for a in list(f.attrib):
    if 'theme' in a.lower():del f.attrib[a]
 normal=d.styles['Normal'];normal.font.size=Pt(14);normal.paragraph_format.line_spacing=Pt(25);normal.paragraph_format.space_after=Pt(6);normal.paragraph_format.widow_control=True
 numbering=d.part.numbering_part.element;aid=max([int(e.get(qn('w:abstractNumId'))) for e in numbering.findall(qn('w:abstractNum'))]+[0])+1
 abstract=OxmlElement('w:abstractNum');abstract.set(qn('w:abstractNumId'),str(aid));mt=OxmlElement('w:multiLevelType');mt.set(qn('w:val'),'multilevel');abstract.append(mt)
 for lev in range(4):
  lvl=OxmlElement('w:lvl');lvl.set(qn('w:ilvl'),str(lev))
  for tag,val in [('start','1'),('numFmt','decimal'),('pStyle','Heading'+str(lev+1)),('lvlText','.'.join('%'+str(i+1) for i in range(lev+1))),('suff','space'),('lvlJc','left')]:
   e=OxmlElement('w:'+tag);e.set(qn('w:val'),val);lvl.append(e)
  abstract.append(lvl)
 numbering.append(abstract);num=numbering.add_num(aid).numId
 for lev,size in enumerate([19,16,14,14],1):
  st=d.styles['Heading '+str(lev)];st.font.name='SimHei' if lev<3 else 'SimSun'
  for a in ['ascii','hAnsi','eastAsia','cs']:st.element.get_or_add_rPr().rFonts.set(qn('w:'+a),st.font.name)
  st.font.size=Pt(size);st.font.bold=True
  pf=st.paragraph_format;pf.space_before=Pt(17 if lev==1 else 12);pf.space_after=Pt(9 if lev==1 else 6);pf.line_spacing=Pt(26 if lev==1 else 23);pf.keep_with_next=True;pf.keep_together=True
  np=st.element.get_or_add_pPr().get_or_add_numPr();np.get_or_add_ilvl().val=lev-1;np.get_or_add_numId().val=num
 # Cover: no headers, footers or decorative text.
 p=d.add_paragraph();p.paragraph_format.space_before=Pt(100);p.alignment=WD_ALIGN_PARAGRAPH.CENTER;font(p.add_run('错题帮'),'SimHei',32,True)
 p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Pt(20);font(p.add_run(kind),'SimHei',24,True)
 for t in ['2026“仓颉杯”智能编程大赛','面向中学生的个人错题学习应用']:
  p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Pt(20);font(p.add_run(t),size=14)
 for t in ['2026年10月23日','源码核对版本：0092d19']:
  p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Pt(28);font(p.add_run(t),size=12)
 p=d.add_paragraph();p.paragraph_format.page_break_before=True;font(p.add_run('目录'),'SimHei',19,True);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
 d.add_paragraph('[[AUTO_TOC]]')
 lines=text.splitlines();lines=lines[next(i for i,l in enumerate(lines) if l.startswith('## ')):];i=0;first=True;figs=[];tabs=[]
 while i<len(lines):
  line=lines[i].strip();i+=1
  if not line:continue
  if line.startswith('##'):
   m=re.match(r'(#{2,5}) (.+)',line);lev=len(m[1])-1;title=re.sub(r'^\d+(?:\.\d+)*\s+','',m[2]);p=d.add_heading(title,lev)
   for r in p.runs:font(r,'SimHei' if lev<3 else 'SimSun')
   np=p._p.get_or_add_pPr().get_or_add_numPr();np.get_or_add_ilvl().val=lev-1;np.get_or_add_numId().val=0 if title=='参考文献' else num
   if (lev==1 and first) or title=='参考文献':p.paragraph_format.page_break_before=True;first=False
   continue
  if line.startswith('!['):
   m=re.fullmatch(r'!\[(.+)\]\((.+)\)',line);paths=m[2].split('|');p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.line_spacing=1;p.paragraph_format.keep_with_next=True
   for j,img in enumerate(paths):
    if j:font(p.add_run('    '),size=4)
    width=(5.0 if len(paths)==3 else 7.7) if len(paths)>1 else (8.2 if 'screenshots/' in img else 16.4)
    with Image.open(O/img) as im:width=min(width,(15.8 if 'screenshots/' in img else 17.8)*im.width/im.height)
    p.add_run().add_picture(str(O/img),width=Cm(width))
   p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.line_spacing=Pt(18);p.paragraph_format.space_after=Pt(10);inline(p,m[1],12);figs.append({'caption':m[1],'sources':paths});continue
  if re.match(r'^表\d+ ',line):
   p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True;p.paragraph_format.space_before=Pt(8);p.paragraph_format.space_after=Pt(5);inline(p,line,12);tabs.append(line);continue
  if line.startswith('|'):
   rows=[line]
   while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
   rows=[[v.strip() for v in l.strip('|').split('|')] for l in rows if not re.match(r'^\|\s*:?-{2,}',l)]
   t=d.add_table(rows=0,cols=len(rows[0]));t.style='Table Grid';t.autofit=True
   widths=[6.0,5.2,5.2] if tabs and tabs[-1].startswith('表10 ') else None
   if widths:
    t.autofit=False
    for col,width in zip(t.columns,widths):col.width=Cm(width)
   borders=OxmlElement('w:tblBorders')
   for edge in ['top','left','bottom','right','insideH','insideV']:
    e=OxmlElement('w:'+edge)
    for a,v in [('val','single'),('sz','5'),('color','000000')]:e.set(qn('w:'+a),v)
    borders.append(e)
   t._tbl.tblPr.append(borders)
   for j,row in enumerate(rows):
    cells=t.add_row().cells
    if widths:
     for cell,width in zip(cells,widths):cell.width=Cm(width)
    for cell,txt in zip(cells,row):
     p=cell.paragraphs[0];p.paragraph_format.line_spacing=Pt(18);p.paragraph_format.space_before=Pt(5);p.paragraph_format.space_after=Pt(5);p.paragraph_format.keep_with_next=j<len(rows)-1 if len(rows)<=8 else False
     inline(p,txt,12)
     for r in p.runs:r.bold=j==0
     if j==0:
      sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'EEF2F4');cell._tc.get_or_add_tcPr().append(sh)
    t.rows[-1]._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
   t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'));continue
  p=d.add_paragraph()
  if line.startswith('$$ '):
   p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_together=True
   for piece in re.split(r'(\^w|\^\(1/k\)|_(?:正确|错误|[a-z]+))',line[3:-3].strip()):
    sup=piece.startswith('^');sub=piece.startswith('_')
    r=p.add_run(piece[1:].strip('()') if sup or sub else piece);font(r,size=13)
    if sup:r.font.superscript=True
    if sub:r.font.subscript=True
  else:
   p.paragraph_format.first_line_indent=Pt(28)
   ref=bool(re.match(r'^\[\d+\] ',line));inline(p,line,12 if ref else 14)
   if ref:p.paragraph_format.first_line_indent=Pt(-22);p.paragraph_format.left_indent=Pt(22);p.paragraph_format.line_spacing=Pt(18)
 raw=B/(name+'_raw.docx');d.save(raw);black_xml(raw)
 return {'key':key,'name':name,'characters':len(text),'figures':figs,'tables':tabs,'references':refkeys,'raw':str(raw),'final':str(O/(name+'.docx'))}
if __name__=='__main__':
 report=[build('product','项目说明文档'),build('system','系统设计文档')]
 (B/'build_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps([{k:v for k,v in r.items() if k not in ['figures','tables','references']} for r in report],ensure_ascii=False,indent=2))
