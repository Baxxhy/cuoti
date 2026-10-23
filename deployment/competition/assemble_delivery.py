"""Assemble public documentation and source; never collect live .env or volumes."""
from pathlib import Path
import json,shutil,subprocess,zipfile
from docx import Document
from docx.shared import Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
R=Path(__file__).resolve().parents[2];S=R/'deployment/competition';B=R/'.runtime/competition-package/bundle/错题帮_可运行程序包';B.mkdir(parents=True,exist_ok=True)
doc=Document()
for name in ['Normal','Title','Heading 1','Heading 2','Heading 3']:
 st=doc.styles[name];st.font.name='宋体' if name=='Normal' else '黑体';st.font.size=Pt(12 if name=='Normal' else 16);st.font.color.rgb=RGBColor(0,0,0);st.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),st.font.name)
for line in (S/'部署说明.md').read_text().splitlines():
 if not line:continue
 if line.startswith('# '):doc.add_heading(line[2:],0)
 elif line.startswith('## '):doc.add_heading(line[3:],1)
 else:doc.add_paragraph(line.replace('**','').replace('`',''))
doc.save(S/'部署说明.docx')
for pattern in ['*.sh','*.md','*.docx','*.yaml','*.lock.txt','configuration.env.example']:
 for f in S.glob(pattern):
  if f.name=='README.md':continue
  shutil.copy2(f,B/f.name)
(B/'部署源码').mkdir(exist_ok=True)
for name in ['entry.py','gateway.py','demo.sql','Dockerfile','Dockerfile.models','prepare_payload.py','prepare_exports.py']:
 shutil.copy2(S/name,B/'部署源码'/name)
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=R).decode().split('\0')
prefixes=('frontend/','backend-algorithms/','backend-cangjie/','scripts/')
selected=[]
for n in tracked:
 if not n:continue
 if not (n.startswith(prefixes) or n in ('README.md','Makefile','config/api_pool.example.json','docs/final/README.md','docs/final/IMPLEMENTATION_STATUS.md')):continue
 p=Path(n)
 if p.name=='.env' or p.suffix in ('.zip','.mp4') or any(x in p.parts for x in ('node_modules','__pycache__','.models','.runtime')):continue
 if (R/n).is_file():selected.append(n)
selected += [str(f.relative_to(R)) for f in S.rglob('*') if f.is_file() and '__pycache__' not in f.parts]
with zipfile.ZipFile(B/'项目源码.zip','w',zipfile.ZIP_DEFLATED) as z:
 for n in sorted(set(selected)):z.write(R/n,n)
print('Documentation and source assembled:',len(set(selected)),'files')
