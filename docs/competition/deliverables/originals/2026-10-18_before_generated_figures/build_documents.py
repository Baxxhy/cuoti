"""Rebuild editable competition documents from Markdown; original files untouched."""
from pathlib import Path
import re,json,runpy,zipfile
from lxml import etree
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
B=Path(__file__).resolve().parent;O=B.parent
BASE=runpy.run_path(str(O/'build/build_documents.py'))
BASE['R']=[(a,b,('https://docs.ankiweb.net/deck-options.html' if a=='R09' else c)) for a,b,c in BASE['R']]
BASE['R'] += [('R10','小猿搜题官网','https://www.yuansouti.com/'),('R11','作业帮服务协议','https://www.zybang.com/zuoyebang/xieyi/index.html'),('R12','Khanmigo官方介绍','https://www.khanacademy.org/khan-labs')]

def black_xml(path):
 with zipfile.ZipFile(path) as z:data={n:z.read(n) for n in z.namelist()}
 ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
 for n,b in list(data.items()):
  if n.startswith('word/') and n.endswith('.xml'):
   root=etree.fromstring(b)
   for e in root.xpath('//w:color',namespaces=ns):
    e.attrib.clear();e.set(qn('w:val'),'000000')
   for e in root.xpath('//w:rPr',namespaces=ns):
    if e.find(qn('w:color')) is None:
     c=etree.SubElement(e,qn('w:color'));c.set(qn('w:val'),'000000')
   # Explicit style/default and drawing text colors prevent theme inheritance.
   for e in root.xpath('//a:rPr|//a:defRPr|//a:endParaRPr',namespaces=ns):
    for child in list(e):
     if etree.QName(child).localname in ('solidFill','gradFill'):e.remove(child)
    fill=etree.SubElement(e,'{'+ns['a']+'}solidFill');etree.SubElement(fill,'{'+ns['a']+'}srgbClr').set('val','000000')
   data[n]=etree.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in data.items():z.writestr(n,b)

def inline(p,text):
 for i,t in enumerate(re.split(r'(\*\*.*?\*\*|`[^`]+`)',text)):
  r=p.add_run(t[2:-2] if t.startswith('**') else t[1:-1] if t.startswith('`') else t)
  r.bold=t.startswith('**');r.font.color.rgb=RGBColor(0,0,0)
 return p

def build(kind,source):
 doc=Document();s=doc.sections[0]
 s.page_width=Cm(21);s.page_height=Cm(29.7);s.left_margin=s.right_margin=Cm(2.25);s.top_margin=Cm(2);s.bottom_margin=Cm(1.8);s.header_distance=s.footer_distance=Cm(.8);s.different_first_page_header_footer=True
 for st in doc.styles:
  if st.type in (1,2):
   st.font.color.rgb=RGBColor(0,0,0)
   st.font.name='SimSun';st.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'SimSun')
 normal=doc.styles['Normal'];normal.font.size=Pt(12);normal.paragraph_format.line_spacing=Pt(21);normal.paragraph_format.space_after=Pt(4);normal.paragraph_format.widow_control=True
 for n,size in [('Title',28),('Heading 1',18),('Heading 2',14),('Heading 3',12),('Heading 4',11.5)]:
  st=doc.styles[n];family='SimHei' if n in ['Title','Heading 1','Heading 2'] else 'SimSun';st.font.name=family;st.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),family);st.font.size=Pt(size);st.font.bold=True;st.paragraph_format.space_before=Pt(14);st.paragraph_format.space_after=Pt(8);st.paragraph_format.line_spacing=Pt(size+10);st.paragraph_format.keep_with_next=True
 for name in ['Header','Footer']:
  doc.styles[name].font.size=Pt(9)
 s.header.paragraphs[0].text=''
 s.footer.paragraphs[0].text=''
 p=doc.add_paragraph('2026“仓颉杯”智能编程大赛');p.paragraph_format.space_before=Pt(55);p.runs[0].font.size=Pt(16)
 p=doc.add_paragraph('错题帮');p.paragraph_format.space_before=Pt(50);p.runs[0].font.size=Pt(42);p.runs[0].bold=True
 doc.add_paragraph(kind,style='Title');p=doc.add_paragraph('证据驱动诊断 · 任务驱动辅导 · 验证驱动学习');p.paragraph_format.space_after=Pt(65)
 for t in ['综合系统赛道','2026年10月18日','uni-app客户端 · 仓颉业务服务 · Python智能计算']:
  doc.add_paragraph(t)
 p=doc.add_paragraph('目录',style='Title');p.paragraph_format.page_break_before=True;doc.add_paragraph('[[AUTO_TOC]]')
 lines=source.read_text().splitlines();lines=lines[next(i for i,l in enumerate(lines) if l.startswith('## ')):];i=0;first=True;captions=[]
 while i<len(lines):
  line=lines[i].strip();i+=1
  if not line:continue
  if line.startswith('# '):continue
  if line.startswith('##'):
   m=re.match(r'(#{2,5}) (.*)',line);level=len(m[1])-1
   p=doc.add_heading(m[2],level)
   if level==1 and first:p.paragraph_format.page_break_before=True;first=False
   continue
  if line.startswith('!['):
   m=re.match(r'!\[(.*?)\]\((.*?)\)',line)
   if not m:raise ValueError(line)
   p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.line_spacing=1;p.paragraph_format.keep_with_next=True
   for img in m[2].split('|'):
    p.add_run().add_picture(str(O/img),width=Cm(7.8 if '|' in m[2] else 8.2 if 'screenshots/' in img else 16.4))
   p=doc.add_paragraph(m[1]);p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(10)
   for r in p.runs:r.font.size=Pt(10)
   captions.append(m[1]);continue
  if re.match(r'^表\d+\s',line):
   p=doc.add_paragraph(line);p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True;p.paragraph_format.space_before=Pt(6);p.paragraph_format.space_after=Pt(4)
   for r in p.runs:r.font.size=Pt(10);r.bold=True
   continue
  if line.startswith('|'):
   rows=[line]
   while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
   rows=[[c.strip() for c in r.strip('|').split('|')] for r in rows if not re.match(r'^\|\s*:?-{2,}',r)]
   t=doc.add_table(rows=0,cols=len(rows[0]));t.autofit=True;t.style='Table Grid'
   borders=OxmlElement('w:tblBorders')
   for edge in ['top','left','bottom','right','insideH','insideV']:
    e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'6');e.set(qn('w:color'),'000000');borders.append(e)
   t._tbl.tblPr.append(borders)
   for j,row in enumerate(rows):
    cells=t.add_row().cells
    for c,txt in zip(cells,row):
     p=c.paragraphs[0];p.paragraph_format.line_spacing=Pt(16);p.paragraph_format.space_after=Pt(5);p.paragraph_format.space_before=Pt(5);inline(p,txt)
     for r in p.runs:r.font.size=Pt(10);r.bold=(j==0)
     BASE['shade'](c,'EAF1F4' if j==0 else 'FFFFFF')
    pr=t.rows[-1]._tr.get_or_add_trPr();pr.append(OxmlElement('w:cantSplit'))
   t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'));continue
  if line.startswith('- '):inline(doc.add_paragraph(style='List Bullet'),line[2:]);continue
  inline(doc.add_paragraph(),line)
 # References remain in a separate source register; no appendix in the submission document.
 name='错题帮_'+kind+'_修订版';out=B/(name+'_raw.docx');doc.save(out);black_xml(out)
 md=source.read_text()
 (O/(name+'.md')).write_text(md)
 return {'name':name,'characters':len(md),'figures':captions}
if __name__=='__main__':
 info=[build('项目说明文档',B/'product.md'),build('系统设计文档',B/'system.md')];(B/'build_manifest.json').write_text(json.dumps(info,ensure_ascii=False,indent=2));print(info)
