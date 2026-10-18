from pathlib import Path
from zipfile import ZipFile
from lxml import etree
import fitz,re,json
O=Path(__file__).resolve().parent.parent;res={};norm=lambda s:re.sub(r'\s+','',s)
for md in O.glob('*_重构终稿.md'):
 t=md.read_text();defined=set(re.findall(r'^- \[([EOR]\d+)\]',t,re.M));used=set(re.findall(r'\[([EOR]\d+)\]',t));assert not used-defined,(md,used-defined)
 images=re.findall(r'!\[图(\d+) (.*?)\]\((.*?)\)',t);assert [int(a) for a,_,_ in images]==list(range(1,len(images)+1))
 tables=re.findall(r'^表(\d+)\s+(.+)',t,re.M);assert [int(a) for a,_ in tables]==list(range(1,len(tables)+1))
 for _,_,p in images:assert (O/p).exists(),p
 d=fitz.open(md.with_suffix('.pdf'));pdf=''.join(pg.get_text() for pg in d);full=norm(pdf)
 for i,title,_ in images:assert norm('图'+i+title) in full,(md,title)
 for i,title in tables:assert norm('表'+i+title) in full,(md,title)
 # Page fields agree on every physical page after the distinct cover.
 for n,pg in enumerate(d):
  if n:
   assert re.search(r'错题帮\s*·\s*'+str(n+1)+r'\s*/\s*'+str(len(d)),pg.get_text()),(md,n+1,'footer')
 # PDF bookmark destinations provide a second independent route to verify refreshed TOC page numbers.
 toc=d.get_toc();verified=[]
 for level,title,page in toc:
  assert norm(title) in norm(d[page-1].get_text()),(md,title,page)
  verified.append({'title':title,'page':page})
 assert toc,(md,'missing outline')
 printed={}
 for page in d:
  text=page.get_text()
  if '\n目录\n' not in text:continue
  for line in text.splitlines():
   m=re.match(r'^(.*?)\.{3,}\s*(\d+)$',line)
   if m:printed[norm(m[1])]=int(m[2])
 for level,title,page in toc:
  assert printed.get(norm(title))==page,(md,'TOC page mismatch',title,page,printed.get(norm(title)))
 res[md.name]={'defined_sources':sorted(defined),'unresolved_references':[],'figures':len(images),'tables':len(tables),'pdf_bookmark_destinations_verified':verified,'footer_pages_verified':len(d)-1}
(O/'build_refactor/reference_manifest.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print({n:{'figures':r['figures'],'tables':r['tables'],'bookmarks':len(r['pdf_bookmark_destinations_verified'])} for n,r in res.items()})
