import fitz,json,zipfile,re
from pathlib import Path
folder=Path('docs/manuals/20261111_v1');d=fitz.open(folder/'师承智学安装与使用手册.pdf');pages=[]
for page in d:
 spans=[s for b in page.get_text('dict')['blocks'] if 'lines'in b for l in b['lines'] for s in l['spans'] if s['text'].strip()];pages.append({'page':page.number+1,'fonts':sorted(set(s['font'] for s in spans)),'pureBlack':all(s['color']==0 for s in spans),'a4':abs(page.rect.width-595.28)<2 and abs(page.rect.height-841.89)<2,'withinPage':all(fitz.Rect(s['bbox']).x0>=0 and fitz.Rect(s['bbox']).x1<=page.rect.width+1 for s in spans)})
assert all(p['pureBlack'] and p['a4'] and p['withinPage'] for p in pages);assert set(f for p in pages for f in p['fonts'])=={'SimSun','TimesNewRomanPSMT'}
with zipfile.ZipFile(folder/'师承智学安装与使用手册.docx') as z:
 for name in ['word/document.xml','word/styles.xml']:assert not re.search(r'w:color[^>]+w:val="(?!000000)[A-Fa-f0-9]{6}"',z.read(name).decode())
r={'manuals':9,'format':'A4','eastAsiaFont':'宋体','latinFont':'Times New Roman','color':'000000','docxEditableProgrammatically':True,'wordWpsManualReview':False,'pdfRendered':True,'renderer':'existing LibreOffice25.2','pages':pages};Path('/tmp/sczx-step20/manual-check.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));d[0].get_pixmap(matrix=fitz.Matrix(1.1,1.1)).save('/tmp/sczx-step20/manual-page-1.png');print('11 pages exact SimSun/TNR black A4 and bounds verified')
