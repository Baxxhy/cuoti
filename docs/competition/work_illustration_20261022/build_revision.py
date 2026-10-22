from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
import json,shutil,hashlib
B=Path(__file__).resolve().parent;D=B.parent/'deliverables';OLD=D/'图文修订版';OUT=D/'插图优化版'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
manifest=json.loads((B.parent/'work_visual_20261022/word_images_manifest.json').read_text())
revisions={
'图1按问题、方法和证据三列组织对应关系。原始步骤为错因定位提供依据，新作答用于独立验证，复习记录参与后续规划。列间连线表示研究要素的对应关系，底部连线表示记录对规划的反馈；具体计算流程见图2。':
'图1以三条研究主线连接问题、方法与可观察证据：用解集差异核对原始步骤，用条件变化后的独立回答区分辅助表现，用复习作答形成后续规划依据。图中算例用于说明机制，具体计算流程见图2。',
'图3强调同样得到正确答案时，独立完成、提示后完成与看过完整答案具有不同证据含义。该机制保留求助的教学价值，并使辅助记录与独立表现各自承担相应证据作用。学生仍可以获得提示、查看解析和继续练习，系统则据不同记录选择更合适的后续支持。':
'图3区分独立作答、提示作答与辅助学习。以先验0.35的非选择题正确作答为例，独立权重1与提示权重0.35分别得到约0.914和0.608的更新结果。p′为加权证据更新后的估计，p″包含正确作答后的学习转移；数值为规则演算。完整答案曝光和局部订正保留过程记录，不作为独立掌握证据。'
}
report={}
for name,items in manifest.items():
 source=OLD/name;dest=OUT/name.replace('图文修订版','插图优化版')
 replace={i['embedded']:(OUT/i['source']).read_bytes() for i in items if '/screenshots/' not in i['source']}
 changes=[]
 with ZipFile(source) as zin,ZipFile(dest,'w',ZIP_DEFLATED) as zout:
  for item in zin.infolist():
   raw=zin.read(item.filename)
   if item.filename in replace:raw=replace[item.filename]
   elif item.filename=='word/document.xml':
    root=E.fromstring(raw)
    for p in root.findall('.//w:p',NS):
     text=''.join(p.itertext()) if False else ''.join(p.xpath('.//w:t/text()',namespaces=NS))
     if text in revisions:
      ppr=p.find('w:pPr',NS)
      for c in list(p):
       if c is not ppr:p.remove(c)
      r=E.SubElement(p,'{%s}r'%NS['w']);rp=E.SubElement(r,'{%s}rPr'%NS['w'])
      font=E.SubElement(rp,'{%s}rFonts'%NS['w'])
      for a in ['ascii','hAnsi','eastAsia','cs']:font.set('{%s}%s'%(NS['w'],a),'SimSun')
      E.SubElement(rp,'{%s}color'%NS['w']).set('{%s}val'%NS['w'],'000000')
      E.SubElement(rp,'{%s}sz'%NS['w']).set('{%s}val'%NS['w'],'25')
      E.SubElement(r,'{%s}t'%NS['w']).text=revisions[text];changes.append({'before':text,'after':revisions[text]})
    raw=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
   zout.writestr(item,raw)
 md=(OLD/source.with_suffix('.md').name).read_text()
 for old,new in revisions.items():md=md.replace(old,new)
 dest.with_suffix('.md').write_text(md)
 report[dest.name]={'original_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'replaced_technical_images':len(replace),'paragraph_revisions':changes,'retained_screenshots':sum('/screenshots/' in i['source'] for i in items)}
shutil.copytree(OLD/'figures/screenshots',OUT/'figures/screenshots',dirs_exist_ok=True)
S=OUT/'figures/source';S.mkdir(exist_ok=True)
shutil.copytree(B/'icons',S/'icons',dirs_exist_ok=True)
s=(B/'draw_figures.py').read_text().replace("O=B.parent/'deliverables/插图优化版/figures'","O=B.parent")
(S/'draw_figures.py').write_text(s)
(B/'revision_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
for script in ['refresh_word_layout.py','render_word_pages.py','check_word_layout.py']:
 s=(B.parent/'work_visual_20261022'/script).read_text().replace('图文修订版','插图优化版')
 (B/script).write_text(s)
print(json.dumps(report,ensure_ascii=False,indent=2))
