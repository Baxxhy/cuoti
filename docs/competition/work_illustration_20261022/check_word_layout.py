from pathlib import Path
import json,hashlib,re
from PIL import Image,ImageDraw
B=Path(__file__).resolve().parent;M=json.loads((B/'word_render_manifest.json').read_text());result={}
for name,v in M.items():
 toc={line.rsplit('\t',1)[0]:int(line.rsplit('\t',1)[1]) for line in v['toc_text'].splitlines() if '\t' in line and line.rsplit('\t',1)[1].isdigit()}
 assert all(next((v for k,v in toc.items() if re.sub(r'^\d+(?:\.\d+)*\s*','',k)==h['text']),None)==h['page'] for h in v['headings']),(name,[(h,toc.get(h['text'])) for h in v['headings'] if toc.get(h['text'])!=h['page']])
 folder=B/'word_previews'/Path(name).stem;pics=sorted(folder.glob('*.png'));assert len(pics)==v['pages'];hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in pics];assert len(hashes)==len(set(hashes)),(name,'duplicate page render')
 canvas=Image.new('RGB',(1150,325*((len(pics)+4)//5)),'#dddddd')
 for i,p in enumerate(pics):
  im=Image.open(p).convert('RGB');im.thumbnail((210,297));x=i%5*230;y=i//5*325;canvas.paste(im,(x+10,y+5));ImageDraw.Draw(canvas).text((x+10,y+305),p.stem,fill='black')
 canvas.save(B/'word_previews'/(Path(name).stem+'_contact.png'))
 result[name]={'pages':v['pages'],'toc_entries_checked':len(toc),'toc_pages_match_actual':True,'unique_page_pngs':True,'docx_sha256':v['sha256']}
(B/'word_layout_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
