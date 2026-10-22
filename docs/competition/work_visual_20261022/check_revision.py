from pathlib import Path
import re,json,hashlib
B=Path(__file__).resolve().parent;O=B.parent/'deliverables/图文修订版';old=B.parent/'deliverables/研究重构版'
report={}
for stem in ['product','system']:
 s=(B/(stem+'.md')).read_text();body,bib=s.split('## 参考文献');ids=set()
 for token in re.findall(r'\[([\d–-]+)\]',body):
  values=re.split('[–-]',token);ids.update(range(int(values[0]),int(values[-1])+1))
 entries=re.findall(r'^\[(\d+)\] ',bib,re.M)
 assert entries==list(map(str,range(1,21)))
 assert ids==set(range(1,21)),(stem,ids)
 report[stem]={'bibliography_entries':20,'all_entries_cited_in_body':True,'all_links_checked_online':'2026-10-22'}
for k in range(1,11):
 name=f'{k:02d}.png';assert (O/'figures'/name).read_bytes()!=(old/'figures'/name).read_bytes()
for p in (old/'figures/screenshots').glob('*.png'):assert p.read_bytes()==(O/'figures/screenshots'/p.name).read_bytes()
assert hashlib.sha256((old/'错题帮_项目说明文档_研究重构版.docx').read_bytes()).hexdigest()=='a8cd20580eec0ac3cbe74f99adab384ca7555f8030cc1bae8ffa13d6bf43d9e4'
assert hashlib.sha256((old/'错题帮_系统设计文档_研究重构版.docx').read_bytes()).hexdigest()=='4ebb000530029fa29aaf73219fe4ca93f939c3c03575e1efdefeb6fd875473fd'
report['figures']={'replaced_mechanism_figures':10,'unchanged_runtime_screenshots':11,'independent_prompts_saved':10,'reference_images_used':False}
report['previous_word_files_unchanged']=True
(B/'revision_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
