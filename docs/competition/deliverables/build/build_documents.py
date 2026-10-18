from pathlib import Path
import runpy,json,re
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from PIL import Image
B=Path(__file__).resolve().parent;O=B.parent;F=O/'figures'
FIG={p.name[:2]:p for p in F.glob('*.png')}
E=[
('E01','当前项目与智能体架构','docs/ARCHITECTURE.md'),('E02','当前收尾与完整验收','docs/final/FINALIZATION_2026_10_18.md'),('E03','产品基线与UI规格','docs/final/README.md；docs/final/UI_SPEC.md'),('E04','产品升级与公开产品调研','docs/final/PRODUCT_UPGRADE_2026_10.md'),('E05','智能体合同','docs/final/AGENT_SPEC.md'),('E06','诊断计算与来源','backend-algorithms/diagnosis_compute.py；backend-algorithms/diagnosis_alignment.py；backend-cangjie/src/diagnosis_api.cj'),('E07','身份、学校与授权','backend-cangjie/src/school_access.cj；backend-cangjie/src/guardian_links.cj；backend-cangjie/src/auth.cj'),('E08','学习证据与认知更新','backend-cangjie/src/learning_evidence.cj；backend-cangjie/src/learning_task_worker.cj'),('E09','复习与恢复','backend-cangjie/src/reviews.cj；docs/final/REVIEW_RECOVERY_IMPLEMENTATION.md'),('E10','有来源的学习记忆','backend-cangjie/src/learning_memory.cj；docs/final/MEMORY_IMPLEMENTATION.md'),
('E11','原始图片与手写','docs/final/UPLOAD_ORIGINAL_IMPLEMENTATION.md；backend-cangjie/src/handwriting.cj'),('E12','检索、推荐与适配','backend-algorithms/retrieval_compute.py；backend-cangjie/src/practice_recommend.cj'),('E13','组卷和导出','docs/final/PAPER_RECOVERY_IMPLEMENTATION.md；backend-algorithms/paper_export_compute.py'),('E14','作业与教师复核','backend-cangjie/src/assignment_reviews.cj；docs/final/GUARDIAN_ACCESS_IMPLEMENTATION.md'),('E15','真实AI内容补充核验','docs/final/EXTENDED_AI_ACCEPTANCE_2026_10.md；backend-algorithms/tests/test_semantic_diagnosis.py'),('E16','任务与十类行为证据','backend-cangjie/src/learning_tasks.cj；backend-cangjie/src/learning_task_worker.cj；docs/final/AGENT_ACCEPTANCE.md'),('E17','服务与依赖边界','backend-algorithms/service.py；frontend/package.json；backend/pyproject.toml；backend/app/providers/api_pool.py'),('E18','手机交付与平台路线','docs/final/MOBILE_DELIVERY.md；frontend/src/manifest.json'),('E19','当前验收与复现脚本','scripts/verify_cangjie.sh；scripts/check_live_extended_curriculum.py；scripts/check_live_extended_curriculum_ui.cjs'),('E20','启动和AI辅助说明','docs/final/QUICK_START.md；docs/competition/2026-10-13-参赛完善说明.md')]
R=[('O01','《2026“仓颉杯”智能编程大赛通知》','用户提供原始PDF，7页；综合系统材料第3页，评分第4页，提交信息第6—7页。'),('O02','《2026“仓颉杯”智能编程大赛章程》','用户提供原始PDF，14页；4.3条第5—6页，5.4条第8页，7.1—7.4条第10—11页。'),('R01','DCloud：uni-app CLI','https://uniapp.dcloud.net.cn/worktile/CLI.html'),('R02','DCloud：安心打包','https://uniapp.dcloud.net.cn/tutorial/build/SafePack.html'),('R03','Pydantic：Models','https://docs.pydantic.dev/latest/concepts/models/'),('R04','SymPy：Solveset','https://docs.sympy.org/latest/modules/solvers/solveset.html'),('R05','Qdrant：Hybrid Queries','https://qdrant.tech/documentation/search/hybrid-queries/'),('R06','BGE-M3模型说明','https://huggingface.co/BAAI/bge-m3'),('R07','Photomath官方功能','https://photomath.com/'),('R08','Quizlet Learn','https://quizlet.com/features/learn'),('R09','Anki官方调度说明','https://docs.ankiweb.net/manual/deck-options')]

def font(style,name,size,bold=False,color='26384A'):
 style.font.name=name;style.font.size=Pt(size);style.font.bold=bold;style.font.color.rgb=RGBColor.from_string(color)
 style.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),name)
def field(p,instr):
 e=OxmlElement('w:fldSimple');e.set(qn('w:instr'),instr);r=OxmlElement('w:r');t=OxmlElement('w:t');t.text='1';r.append(t);e.append(r);p._p.append(e)
def shade(cell,c):
 x=OxmlElement('w:shd');x.set(qn('w:fill'),c);cell._tc.get_or_add_tcPr().append(x)
def table(doc,rows,header=True,small=False):
 t=doc.add_table(rows=0,cols=len(rows[0]));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
 count=len(rows[0]);widths=[3.6,12.8] if count==2 else [4.5,5.7,6.2]
 for i,row in enumerate(rows):
  cells=t.add_row().cells
  for j,txt in enumerate(row):
   cells[j].width=Cm(widths[j]);cells[j].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   p=cells[j].paragraphs[0];p.paragraph_format.space_before=Pt(5 if not small else 4);p.paragraph_format.space_after=Pt(5 if not small else 4);p.paragraph_format.line_spacing=Pt(14 if small else 17)
   r=p.add_run(str(txt));r.font.size=Pt(10 if small else 11.5)
   if i==0 and header:r.bold=True;r.font.color.rgb=RGBColor.from_string('FFFFFF');shade(cells[j],'153D62')
   else:shade(cells[j],'F0F5F8' if i%2==0 else 'FFFFFF')
   tcPr=cells[j]._tc.get_or_add_tcPr();borders=OxmlElement('w:tcBorders');bottom=OxmlElement('w:bottom');bottom.set(qn('w:val'),'single');bottom.set(qn('w:sz'),'4');bottom.set(qn('w:color'),'DDE6EC');borders.append(bottom);tcPr.append(borders)
  pr=t.rows[-1]._tr.get_or_add_trPr();keep=OxmlElement('w:cantSplit');pr.append(keep)
 if header:
  e=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(e)
 return t

def build(kind,module):
 pages=runpy.run_path(str(B/module))['P']
 enrich=runpy.run_path(str(B/'enrich_content.py'));extra=enrich['PROJECT' if module.startswith('project') else 'SYSTEM']
 cases={}
 if module.startswith('system'):
  notes=(B/'技术机制补充素材.md').read_text()
  for match in re.finditer(r'## (\d+) ([^\n]+)\n\n(.+?)\n\n来源：',notes,re.S):cases[int(match.group(1))]=match.group(3).strip()
 for item in pages:
  item['paras'] += [t.strip() for t in extra.get(item['title'],'').split('\n\n') if t.strip()]
  case=enrich['CASE_MAP'].get(item['title']) if module.startswith('system') else None
  if case:item['paras'].append('设计案例：'+cases[case])
 doc=Document();sec=doc.sections[0]
 sec.page_width=Cm(21);sec.page_height=Cm(29.7);sec.top_margin=Cm(2);sec.bottom_margin=Cm(1.8);sec.left_margin=Cm(2.3);sec.right_margin=Cm(2.3);sec.header_distance=Cm(.8);sec.footer_distance=Cm(.8);sec.different_first_page_header_footer=True
 font(doc.styles['Normal'],'Noto Serif CJK SC',12)
 pf=doc.styles['Normal'].paragraph_format;pf.line_spacing=Pt(20);pf.space_after=Pt(7);pf.widow_control=True
 for n,size in [('Title',30),('Heading 1',19),('Heading 2',15),('Heading 3',13)]:font(doc.styles[n],'Noto Sans CJK SC',size,True,'153D62')
 doc.styles['Heading 1'].paragraph_format.line_spacing=Pt(30);doc.styles['Heading 2'].paragraph_format.line_spacing=Pt(24);doc.styles['Heading 1'].paragraph_format.space_after=Pt(12);doc.styles['Heading 1'].paragraph_format.space_before=Pt(0)
 doc.styles['Heading 2'].paragraph_format.space_after=Pt(13);doc.styles['Heading 2'].paragraph_format.space_before=Pt(4)
 for n in ['Header','Footer']:font(doc.styles[n],'Noto Sans CJK SC',9,color='657B8D')
 hp=sec.header.paragraphs[0];hp.text=f'错题帮  /  {kind}';hp.paragraph_format.space_after=Pt(2)
 fp=sec.footer.paragraphs[0];fp.alignment=WD_ALIGN_PARAGRAPH.RIGHT;fp.add_run('错题帮  ·  ');field(fp,'PAGE');fp.add_run(' / ');field(fp,'NUMPAGES')
 # 简洁封面，不加入未经确认的成员、院校、官方Logo。
 p=doc.add_paragraph();p.paragraph_format.line_spacing=1.2;p.paragraph_format.space_before=Pt(55);r=p.add_run('2026“仓颉杯”智能编程大赛');r.font.name='Noto Sans CJK SC';r.font.size=Pt(17);r.font.color.rgb=RGBColor.from_string('46647B')
 p=doc.add_paragraph();p.paragraph_format.line_spacing=1.2;p.paragraph_format.space_before=Pt(48);r=p.add_run('错题帮');r.bold=True;r.font.name='Noto Sans CJK SC';r.font.size=Pt(44);r.font.color.rgb=RGBColor.from_string('153D62')
 p=doc.add_paragraph(kind,style='Title');p.paragraph_format.space_after=Pt(20)
 p=doc.add_paragraph('证据驱动诊断 · 任务驱动辅导 · 验证驱动学习');p.paragraph_format.space_after=Pt(70)
 table(doc,[['材料定位','综合系统赛道文档'],['源码基线','Baxxhy/cuoti · 295366d'],['文档日期','2026年10月18日'],['产品形态','移动优先 · 当前H5与App资源工程']],header=False)
 p=doc.add_paragraph('仓颉业务后端  /  Python算法  /  uni-app前端');p.paragraph_format.space_before=Pt(30);p.runs[0].font.size=Pt(10);p.runs[0].font.color.rgb=RGBColor.from_string('657B8D')
 p=doc.add_paragraph('目录',style='Title');p.paragraph_format.page_break_before=True;doc.add_paragraph('[[AUTO_TOC]]')
 md=[f'# 错题帮_{kind}','', '2026“仓颉杯”智能编程大赛 · 综合系统赛道材料', '', '源码基线：295366d；文档日期：2026-10-18。',''];figures=[];last=''
 for i,item in enumerate(pages):
  if item['ch']!=last:
   p=doc.add_heading(item['ch'],1);p.paragraph_format.page_break_before=(i==0);p.paragraph_format.space_before=Pt(20 if i else 0);md+=['## '+item['ch'],''];last=item['ch'];new_ch=True
  else:new_ch=False
  p=doc.add_heading(item['title'],2)
  if not new_ch:p.paragraph_format.space_before=Pt(14)
  md+=['### '+item['title'],'']
  body=item['paras']
  if item['fig']:
   doc.add_paragraph(body[0]);md+=[body[0],''];body=body[1:]
  if item['fig']:
   k=item['fig'];img=FIG[k];im=Image.open(img);w,h=im.size;scale=16.2/w
   p=doc.add_paragraph();p.paragraph_format.line_spacing=1.0;p.paragraph_format.keep_with_next=True;p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Pt(3);p.paragraph_format.space_after=Pt(4);p.add_run().add_picture(str(img),width=Cm(w*scale),height=Cm(h*scale))
   caption=f'图{int(k):02d}  {img.stem[3:]}';p=doc.add_paragraph(caption);p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(4);p.runs[0].font.size=Pt(10);p.runs[0].font.color.rgb=RGBColor.from_string('46647B');figures.append(k)
   md += [f'![{caption}](figures/{img.name})','',caption,'']
  for text in body:
   doc.add_paragraph(text);md+=[text,'']
  if item['rows']:
   table(doc,item['rows']);md+=['| '+' | '.join(item['rows'][0])+' |','|'+'---|'*len(item['rows'][0])]+['| '+' | '.join(row)+' |' for row in item['rows'][1:]]+['']
  if item['source']:
   previous=doc._body._element[-2]
   prior_paras=[previous] if previous.tag==qn('w:p') else previous.findall('.//'+qn('w:tr'))[-1].findall('.//'+qn('w:p')) if previous.tag==qn('w:tbl') else []
   for prior in prior_paras:
    ppr=prior.find(qn('w:pPr'))
    if ppr is None:ppr=OxmlElement('w:pPr');prior.insert(0,ppr)
    keep=OxmlElement('w:keepNext');ppr.append(keep)
   p=doc.add_paragraph('依据：'+item['source']);p.paragraph_format.space_before=Pt(8);p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=Pt(14)
   for r in p.runs:r.font.size=Pt(9);r.font.color.rgb=RGBColor.from_string('657B8D')
   md+=['依据：'+item['source'],'']
 for n,refs in enumerate([E[:10],E[10:],R]):
  title=['附录A  架构与业务来源','附录B  验证与运行来源','附录C  官方材料与技术资料'][n];p=doc.add_heading(title,2);p.paragraph_format.page_break_before=True;md+=['## '+title,'']
  if n<2:doc.add_paragraph('下列路径均相对于项目仓库。范围以2026年10月18日所核对源码及其有效记录为准。')
  else:doc.add_paragraph('官方PDF由用户提供；外部技术资料访问日期为2026年10月18日。公开产品来源沿用已核验调研；Quizlet本次页面未成功读取，沿用项目此前官方资料记录。本文不据此声称效果优越。')
  table(doc,[['编号','资料与定位']]+[[f'[{a}]',b+'\n'+c] for a,b,c in refs],small=True)
  for a,b,c in refs:md += [f'- [{a}] {b}：{c}']
  md+=['']
 # 字段设置便于Word再次打开更新，正式PDF由UNO实际更新后生成。
 st=doc.settings.element;e=OxmlElement('w:updateFields');e.set(qn('w:val'),'true');st.append(e)
 filename='错题帮_'+kind
 doc.save(str(B/(filename+'_raw.docx')));(O/(filename+'.md')).write_text('\n'.join(md))
 return dict(name=filename,page_target=([30,35] if module.startswith("project") else [50,55]),body_units=len(pages),figures=figures,characters=sum(sum(len(x) for x in p['paras']) for p in pages))
if __name__=='__main__':
 info=[build('项目说明文档','project_content.py'),build('系统设计文档','system_content.py')];(B/'build_manifest.json').write_text(json.dumps(info,ensure_ascii=False,indent=2));print(info)
