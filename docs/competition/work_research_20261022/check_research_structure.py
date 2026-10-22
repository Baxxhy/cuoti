"""Validate requested outline, actual numbering, retained mathematics and originals."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import re,json,subprocess,hashlib
B=Path(__file__).resolve().parent;O=B.parent/'deliverables/研究重构版';A=B.parent/'work_20261022'
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
expected={
'product': [('项目概述',['研究背景','现有问题','研究目标','项目特色']),('需求分析',['用户需求','功能设计','学习流程']),('关键技术',['错因定位','掌握评估','学习规划','习题生成']),('系统设计',['总体架构','智能体协同','数据管理','可靠性设计']),('实现与验证',['功能实现','应用案例','系统测试','验证分析']),('总结与展望',['项目成果','应用价值','后续工作'])],
'system':[('总体设计',['设计目标','系统架构','技术选型','模块划分']),('核心算法',['错因定位算法','掌握更新算法','学习规划算法','习题生成算法']),('智能体设计',['协同架构','工作流设计','工具调用','状态管理']),('数据设计',['数据模型','数据关联','版本管理','学习记忆']),('系统实现',['前端实现','业务服务','算法服务','安全与容错','部署方案']),('系统验证',['测试环境','功能测试','算法验证','测试分析']),('总结与展望',['系统总结','改进方向'])]}
result={}
for key,kind in [('product','项目说明文档'),('system','系统设计文档')]:
 source=(B/(key+'.md')).read_text();heads=re.findall(r'^#{2,3} (.+)',source,re.M);wanted=[]
 for i,(h,sub) in enumerate(expected[key],1):
  wanted.append(f'{i} {h}');wanted.extend(f'{i}.{j} {x}' for j,x in enumerate(sub,1))
 assert heads==wanted
 paragraphs=[x for x in source.split('\n\n') if len(x)>100 and not x.startswith('|')];assert len(paragraphs)==len(set(paragraphs))
 assert not any(x in source for x in ['EduOCR','EduVision','Spring Boot','ChatGLM2','800张'])
 if key=='product':
  prefix=source.split('### 5.2 应用案例')[0];suffix=source.split('### 5.3 系统测试')[1];assert 'figures/screenshots/' not in prefix+suffix
 else:assert 'figures/screenshots/' not in source
 f=O/f'错题帮_{kind}_研究重构版.docx'
 with ZipFile(f) as z:
  d=E.fromstring(z.read('word/document.xml'));styles=E.fromstring(z.read('word/styles.xml'));nums=E.fromstring(z.read('word/numbering.xml'))
  hs=d.xpath('//w:p[w:pPr/w:pStyle[@w:val="Heading1" or @w:val="Heading2"]]',namespaces=N)
  for p in hs:
   sid=p.xpath('string(w:pPr/w:pStyle/@w:val)',namespaces=N)
   num=p.xpath('w:pPr/w:numPr/w:numId/@w:val',namespaces=N) or styles.xpath('//w:style[@w:styleId="'+sid+'"]//w:numId/@w:val',namespaces=N)
   assert num and num[0]!='0'
   text=''.join(p.xpath('.//w:t/text()',namespaces=N));assert not re.match(r'^\d',text)
  toc=d.xpath('//w:p[w:pPr/w:pStyle[starts-with(@w:val,"Contents")]]',namespaces=N)
  assert len(toc)==len(heads)
  assert not any(p.xpath('.//w:numPr|.//w:br',namespaces=N) for p in toc)
  assert all(len(p.xpath('.//w:r/w:tab',namespaces=N))==1 for p in toc)
 result[key]={'outline_exactly_matches_request':True,'headings':heads,'genuine_multilevel_numbering':True,'toc_no_list_numbering_or_manual_breaks':True,'toc_one_page_tab_per_entry':True,'duplicate_long_paragraphs':0,'screenshots_only_in_product_cases':True,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
old=(A/'system.md').read_text();new=(B/'system.md').read_text();formula=[l for l in old.splitlines() if l.startswith(('S＝','p′＝','p″＝','Q＝'))];assert all(l in new for l in formula)
assert all(x in new for x in ['H(p)＝－p log₂p－(1－p)log₂(1－p)','R＝1－p exp(－d／τ)','0.913957','0.608193','0.053640','0.956115','24轮','72次','38秒','45秒'])
result['retained_formulas']=formula
for f in (B.parent/'deliverables').glob('*_重写终稿.*'):
 rel='docs/competition/deliverables/'+f.name
 assert f.read_bytes()==subprocess.check_output(['git','show','71894bf:'+rel])
result['prior_word_and_md_unchanged']=True
(B/'research_structure_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('Research outline, actual numbering, TOC, formulas, screenshot placement and original preservation verified')
