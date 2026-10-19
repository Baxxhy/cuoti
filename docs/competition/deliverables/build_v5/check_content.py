"""Read-only checks for source coverage, hyperlinks and reference-template leakage."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import re,json,hashlib
B=Path(__file__).resolve().parent;O=B.parent
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
def docparas(f):
 with ZipFile(f) as z:
  d=E.fromstring(z.read('word/document.xml'))
  return [''.join(p.xpath('.//w:t/text()',namespaces=NS)) for p in d.xpath('//w:p',namespaces=NS)]
def norm(t):return re.sub(r'\s+','',t)
def plain(t):return re.sub(r'\[([^\]]+)\]\([^\s)]+\)',r'\1',t).replace('**','').replace('`','')
refdir=Path('/root/.codex/attachments/8406691f-086c-429f-af4c-612759c34123')
refs=list(refdir.glob('*.docx'));assert len(refs)==5
reftexts={norm(p) for f in refs for p in docparas(f) if len(norm(p))>=50}
report={};register=['# v5逐段覆盖登记','', '逐段源文与Word比对记录。内容适用性由三轮全文审查判断，本表的自动匹配不等于质量评分。','']
for key,kind in [('product','项目说明'),('system','系统设计')]:
 source=B/(key+'.md');f=O/('错题帮_'+kind+'文档_参赛定稿.docx');paras=docparas(f);joined=norm(''.join(paras));lines=source.read_text().splitlines();start=next(i for i,l in enumerate(lines) if l.startswith('## '));body=[];section=''
 register += ['## '+kind,'','| 源行 | 所属小节 | 段首 | Word覆盖 |','| --- | --- | --- | --- |']
 for i,l in enumerate(lines[start:],start+1):
  if l.startswith('##'):section=l.lstrip('# ');continue
  if not l.strip() or l.startswith(('![','|','表')):continue
  text=plain(l.removeprefix('- '));matched=norm(text) in joined
  body.append({'line':i,'section':section,'matched':matched});assert matched,(key,i,text[:60])
  register.append(f'| {i} | {section} | {text[:28]} | 已匹配 |')
 copies=[p[:60] for p in paras if len(norm(p))>=50 and norm(p) in reftexts];assert not copies
 placeholders=[x for x in ['TODO','TBD','Lorem ipsum','此处填写','[[AUTO_TOC]]','附录'] if x in joined];assert not placeholders
 with ZipFile(f) as z:
  d=E.fromstring(z.read('word/document.xml'));rels=E.fromstring(z.read('word/_rels/document.xml.rels'));targets={r.get('Id'):r.get('Target') for r in rels};actual=[(''.join(h.xpath('.//w:t/text()',namespaces=NS)),targets[h.get('{'+NS['r']+'}id')]) for h in d.xpath('//w:hyperlink[@r:id]',namespaces=NS)]
 expected=re.findall(r'(?<!!)\[([^\]]+)\]\(([^\s)]+)\)','\n'.join(lines[start:]));assert sorted(actual)==sorted(expected),(key,actual,expected)
 report[key]={'body_paragraphs':len(body),'all_body_paragraphs_matched':True,'reference_documents':len(refs),'exact_reference_paragraph_copies_ge50_chars':copies,'placeholder_hits':placeholders,'hyperlinks_matched':len(actual),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'docx_sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
(B/'content_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));(O/'review/final_v5/逐段覆盖登记.md').write_text('\n'.join(register)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
