"""Read-only source-to-Word coverage and reference audit."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import json,re,hashlib,subprocess
B=Path(__file__).resolve().parent;O=B.parent/'deliverables/图文修订版'
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','r':'http://schemas.openxmlformats.org/package/2006/relationships'}
def plain(s):
 s=re.sub(r'\[([^]]+)\]\([^)]*\)',r'\1',s)
 return re.sub(r'[\s`*_^]','',s)
report={}
for kind,stem in [('系统说明文档','product'),('系统设计文档','system')]:
 source=(B/(stem+'.md')).read_text();f=O/('错题帮_'+kind+'_图文修订版.docx')
 with ZipFile(f) as z:
  doc=E.fromstring(z.read('word/document.xml'));text=plain(''.join(doc.xpath('//w:t/text()',namespaces=N)))
  rel=E.fromstring(z.read('word/_rels/document.xml.rels'));links=rel.xpath('//r:Relationship[@TargetMode="External"]/@Target',namespaces=N)
  counts={'paragraphs':0,'table_cells':0,'headings':0,'figure_captions':0};miss=[]
  lines=source.splitlines();lines=lines[next(i for i,l in enumerate(lines) if l.startswith('## ')):]
  for line in lines:
   line=line.strip()
   if not line or line.startswith('# '):continue
   if re.match(r'^\|\s*:?-{2,}',line):continue
   if line.startswith('|'):
    units=[x.strip() for x in line.strip('|').split('|')];counts['table_cells']+=len(units)
   elif line.startswith('!['):
    units=[re.match(r'!\[([^]]+)\]',line)[1]];counts['figure_captions']+=1
   elif line.startswith('##'):
    units=[re.sub(r'^#+\s+(?:\d+(?:\.\d+)*\s+)?','',line)];counts['headings']+=1
   else:
    units=[line.removeprefix('- ')];counts['paragraphs']+=1
   for unit in units:
    if plain(unit) not in text:miss.append(unit[:100])
  assert not miss,(kind,miss)
  for url in re.findall(r'(?<!!)\[[^]]+\]\((https?://[^)]+)\)',source):assert url in links,(kind,url)
  ps=[''.join(p.xpath('.//w:t/text()',namespaces=N)) for p in doc.xpath('//w:body/w:p',namespaces=N)]
  for prefix in ['图','表']:
   seq=[int(re.match(prefix+r'(\d+)\s',p)[1]) for p in ps if re.match(prefix+r'\d+\s',p)]
   assert seq==list(range(1,len(seq)+1)),(kind,prefix,seq)
  assert not any(x in text for x in ['ECED','AEMT','ARPP','TODO','待填写','教师端','家长端'])
  for path in re.findall(r'!\[[^]]*\]\(([^)]+)\)',source):
   assert all((O/x).is_file() for x in path.split('|'))
  report[kind]={**counts,'source_coverage_complete':True,'linked_references_preserved':len(links),'sequential_captions':True,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
originals=[]
for f in sorted((B.parent/'originals_20261019').glob('*')):
 if f.is_file():
  data=subprocess.check_output(['git','show','d963059:docs/competition/deliverables/'+f.name])
  assert data==f.read_bytes(),('original changed',f.name)
  originals.append({'name':f.name,'sha256':hashlib.sha256(data).hexdigest(),'matches_d963059':True})
report['preserved_originals']=originals
(B/'content_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
