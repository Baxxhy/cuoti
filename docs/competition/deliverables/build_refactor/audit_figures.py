from pathlib import Path
from lxml import etree
from PIL import ImageFont
import subprocess,json
O=Path(__file__).resolve().parents[1]/'figures/restructured';rows={};bad=[]
regular=subprocess.check_output(['fc-match','-f','%{file}','Noto Serif CJK SC'],text=True)
bold=subprocess.check_output(['fc-match','-f','%{file}','Noto Sans CJK SC:style=Bold'],text=True)
for p in sorted(O.glob('*.svg')):
 r=etree.fromstring(p.read_bytes());W,H=float(r.get('width')),float(r.get('height'));count=0;small=999
 for t in r.xpath('//*[local-name()="text"]'):
  size=float(t.get('font-size'));small=min(small,size);font=ImageFont.truetype(bold if t.get('font-weight')=='700' else regular,size=round(size));y=float(t.get('y'));anchor=t.get('text-anchor','start')
  assert t.get('fill')=='#000000',(p,'nonblack')
  for sp in t:
   if etree.QName(sp).localname!='tspan':continue
   y+=float(sp.get('dy','0'));x=float(sp.get('x'));txt=sp.text or '';w=font.getlength(txt);left=x-(w/2 if anchor=='middle' else w if anchor=='end' else 0);right=left+w;count+=1
   if left<0 or right>W or y>H or y-size<0:bad.append({'figure':p.name,'text':txt,'bounds':[left,y-size,right,y],'canvas':[W,H]})
 rows[p.stem]={'lines':count,'minimum_font_px':small,'text_color':'#000000','png_width':2700,'effective_ppi_at_16_4cm':418}
res={'method':'SVG black fill and PIL/Noto font-line geometry; does not replace visual review','figures':rows,'canvas_overflow':bad}
(O/'audit.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print('Figures',len(rows),'lines',sum(x['lines'] for x in rows.values()),'overflow',bad);assert not bad
