import sys,json,hashlib,time,io
from pathlib import Path
import httpx
from docx import Document
ROOT=Path('/root/Baxxhy/zhiwei/sczx');sys.path.insert(0,str(ROOT/'scripts'))
from install_unit_content import install,call
fx=json.loads(Path('/tmp/sczx-step16/private.json').read_text());bundle_file=ROOT/'docs/planning/第十六步单元内容草案_20261111_v1.json';bundle=json.loads(bundle_file.read_text());approval=json.loads(Path('/tmp/sczx-step16/human-review.json').read_text());assert approval['sha256']==hashlib.sha256(bundle_file.read_bytes()).hexdigest()
with httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as c:
 assert c.post('/api/auth/login',json={'username':'unit-admin','password':fx['password']}).status_code==200
 points=call(c,'GET','/curriculum/knowledge');known={p['id'] for p in points};call(c,'PUT','/curriculum/knowledge',{'points':points+[p for p in bundle['knowledge'] if p['id'] not in known]})
 cases={}
 for key,index in [('equality',0),('application',3)]:
  d=bundle['lessons'][index]['data'];example=next(b for b in d['blocks'] if b['type']=='example');quote=example['content'];existing=next((r['published'] for r in call(c,'GET','/library/cases') if r.get('published') and r['published'].get('content')==quote and r['published'].get('source')=='用户单人复核的项目自编单元'),None)
  if existing:cases[key]=existing;continue
  doc=Document();doc.add_paragraph(quote);buf=io.BytesIO();doc.save(buf)
  r=c.post('/api/library/materials',data={'title':'项目自编单元来源：'+d['title'],'author':'项目自编、AI辅助整理','sourceNote':'用户单人复核的单元草案；非真实教师课堂材料','grade':'七年级','subject':'数学'},files={'file':('来源.docx',buf.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')});assert r.status_code==201,r.text;material=r.json()
  for _ in range(120):
   material=call(c,'GET','/library/materials/'+material['id'])
   if material.get('units'):break
   time.sleep(.25)
  unit=next(u for u in material['units'] if quote in u['text']);case=call(c,'POST','/library/cases',{'unitIds':[unit['id']]});data=case['draft'];data.update(title='项目自编：'+example['title'],content=quote,source='用户单人复核的项目自编单元',author='AI辅助整理',grade='七年级',subject='数学',knowledgeIds=d['knowledgeIds'],experience={'goal':d['goal'],'difficulty':'先看数量关系和当前运算，保留学生的解释','introduction':quote})
  data.pop('reviewed',None);data.pop('updatedAt',None);call(c,'PUT','/library/cases/'+case['id']+'/draft',{'data':data});call(c,'POST','/library/cases/'+case['id']+'/review');published=call(c,'POST','/library/cases/'+case['id']+'/publish');cases[key]=published['published']
 result=install(c,bundle,approval,cases);result['cases']=cases
Path('/tmp/sczx-step16/content-installed.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('reviewed 5-lesson unit installed through curriculum API')
