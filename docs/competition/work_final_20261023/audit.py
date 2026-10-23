"""Check the final Word packages and their independently reopened layout."""
from pathlib import Path
from collections import Counter
import json,re,hashlib,zipfile
from lxml import etree as E
from docx import Document
B=Path(__file__).resolve().parent; O=B.parent/'deliverables/参赛终稿'
ROOT=B.parents[2]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
W='{'+NS['w']+'}'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((B/'build_manifest.json').read_text());layout=json.loads((B/'render_audit.json').read_text())
report={'originals':[], 'documents':{}, 'figures':[], 'cross_document':{}}
for item in json.loads((B/'originals.json').read_text()):
 p=ROOT/item['path'];report['originals'].append({'path':item['path'],'unchanged':sha(p)==item['sha256']})
for item in manifest:
 p=Path(item['final']);d=Document(p);md=(O/(item['name']+'.md')).read_text();body=md.split('## 参考文献')[0]
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  trees={n:E.fromstring(z.read(n)) for n in z.namelist() if n.startswith('word/') and n.endswith('.xml')}
  r=trees['word/document.xml'];styles=trees['word/styles.xml']
  badcolors=[(n,dict(e.attrib)) for n,t in trees.items() for e in t.xpath('//w:color',namespaces=NS) if e.get(W+'val')!='000000' or len(e.attrib)>1]
  drawings=r.xpath('//w:drawing',namespaces=NS)
  txt='\n'.join(r.xpath('//w:t/text()',namespaces=NS))
  refnums=[int(v) for v in re.findall(r'^\[(\d+)\] ',md,re.M)]
  cites={int(v) for v in re.findall(r'\[(\d+)\]',body)}
  tablegrids=[]
  for t in r.xpath('//w:tbl',namespaces=NS):
   b=t.find('w:tblPr/w:tblBorders',NS)
   if b is None:
    style=t.find('w:tblPr/w:tblStyle',NS)
    inherited=styles.xpath('//w:style[@w:styleId="'+style.get(W+'val')+'"]/w:tblPr/w:tblBorders',namespaces=NS) if style is not None else []
    b=inherited[0] if inherited else None
   edges=[('top',),('bottom',),('left','start'),('right','end'),('insideH',),('insideV',)]
   tablegrids.append(b is not None and all(any(b.find('w:'+k,NS) is not None and b.find('w:'+k,NS).get(W+'val') not in ('nil','none') for k in group) for group in edges))
  fonts={}
  for name in ('Normal','Heading1','Heading2'):
   st=styles.xpath('//w:style[@w:styleId="'+name+'"]',namespaces=NS)[0]
   fonts[name]={E.QName(k).localname:v for k,v in st.find('w:rPr/w:rFonts',NS).attrib.items()}
  caps=[]
  for para in d.paragraphs:
   if re.match(r'^[图表]\d+ ',para.text):caps.append({'caption':para.text,'centered':str(para.alignment)=='CENTER (1)'})
  tocrows=[]
  for line in layout[item['key']]['toc'].splitlines():
   m=re.match(r'(?:(\d+(?:\.\d+)*)\s+)?(.+?)\t(\d+)$',line)
   if m:
    h=next((x for x in layout[item['key']]['headings'] if x['text']==m[2]),None)
    tocrows.append({'title':m[2],'toc_page':int(m[3]),'actual_page':h['page'] if h else None,'matches':h is not None and h['page']==int(m[3])})
  tocpara=r.xpath('//w:p[w:pPr/w:pStyle[contains(@w:val,"Contents")]]',namespaces=NS)
  direct_num=[p for p in tocpara if p.find('w:pPr/w:numPr/w:numId',NS) is not None and p.find('w:pPr/w:numPr/w:numId',NS).get(W+'val')!='0']
  result={'file':str(p),'sha256':sha(p),'pages':layout[item['key']]['pages'],'word_paragraphs':len(d.paragraphs),'tables':len(d.tables),'embedded_images':len(drawings),'figure_groups':len(item['figures']),'references':len(refnums),'bad_colors':badcolors,'fonts':fonts,'headers_footers':[n for n in z.namelist() if n.startswith(('word/header','word/footer'))], 'all_tables_full_grid':all(tablegrids),'captions':caps,'toc':tocrows,'toc_direct_numbering_count':len(direct_num),'reference_numbers_contiguous':refnums==list(range(1,len(refnums)+1)),'all_references_cited':cites==set(refnums),'has_real_toc_field':bool(re.search(r'\bTOC\b',''.join(r.xpath('//w:instrText/text()',namespaces=NS)))),'unresolved_tokens':[x for x in ('[[AUTO_TOC]]','[ @','TODO','待补充','详见另一份','如项目说明文档所述','## 附录') if x in md or x in txt],'reopened_sha_matches':sha(p)==layout[item['key']]['sha256']}
  report['documents'][item['key']]=result
  assert not badcolors and not result['headers_footers'] and not result['unresolved_tokens'],result
  assert result['all_tables_full_grid'] and all(x['centered'] for x in caps)
  assert result['has_real_toc_field'] and result['all_references_cited'] and result['reference_numbers_contiguous']
  assert all(x['matches'] for x in tocrows) and len(tocrows)==len(layout[item['key']]['headings']),tocrows
  assert result['reopened_sha_matches']
  assert not re.search(r'qwen|通义千问',txt,re.I)
  result['generic_ai_model_naming']=True
  assert len(drawings)==sum(len(x['sources']) for x in item['figures'])
  figure_numbers=[int(re.match(r'图(\d+)',x['caption'])[1]) for x in item['figures']]
  assert figure_numbers==list(range(1,len(figure_numbers)+1))
  assert set(map(int,re.findall(r'图(\d+)',body)))==set(figure_numbers)
  result['figure_numbers_contiguous']=True
  result['figure_references_resolve']=True
  assert all(fonts[k].get('eastAsia')==('SimSun' if k=='Normal' else 'SimHei') for k in fonts)
for p in sorted((O/'figures').glob('*.svg')):
 r=E.fromstring(p.read_bytes());bad=[e.text for e in r.xpath('//*[local-name()="text"]') if e.get('fill') not in ('#000000','black')]
 report['figures'].append({'file':p.name,'nonblack_labels':bad});assert not bad
screens=[]
for p in (O/'figures/screenshots').glob('*.png'):
 old=B.parent/'deliverables/插图优化版/figures/screenshots'/p.name
 screens.append({'file':p.name,'unchanged':sha(p)==sha(old)})
report['screenshots']=screens;assert all(x['unchanged'] for x in screens)
texts=[(B/(k+'.md')).read_text() for k in ('product','system')]
paragraphs=[{p for p in t.split('\n\n') if len(p)>80 and not p.startswith(('#','|','$$'))} for t in texts]
report['cross_document']['identical_long_paragraphs']=sorted(paragraphs[0]&paragraphs[1]);assert not report['cross_document']['identical_long_paragraphs']
report['cross_document']['foreign_project_terms']=[x for x in ('智维错题','MindDimension','错题全都队','多智能体协同') if any(x in t for t in texts)]
assert not report['cross_document']['foreign_project_terms']
assert all(x['unchanged'] for x in report['originals'])
(B/'quality_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:{f:v[f] for f in ('pages','tables','embedded_images','references')} for k,v in report['documents'].items()},ensure_ascii=False))
