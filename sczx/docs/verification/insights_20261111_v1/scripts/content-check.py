import json,time,io
from pathlib import Path
from docx import Document
import httpx
fx=json.loads(Path('/tmp/sczx-step15/browser-private.json').read_text());base='http://127.0.0.1:8015';checks=[]
def note(name,**kw):checks.append({'name':name,**kw})
with httpx.Client(base_url=base,timeout=30) as admin,httpx.Client(base_url=base,timeout=30) as teacher:
 for c,user in [(admin,'ops-admin'),(teacher,'ops-t1')]:assert c.post('/api/auth/login',json={'username':user,'password':fx['password']}).status_code==200
 before=teacher.get('/api/platform').json();tasks={t['id']:{'questions':t['questions'],'snapshot':t['snapshot']} for t in before['tasks']};old=admin.get('/api/ai/cases/ops-case?versionId=ops-case-v1').json();arrangements=teacher.get('/api/teaching/tasks/ops-t00/supplements').json();refs={r['id']:r.get('case') for r in arrangements}
 doc=Document();quote='让学生比较只改变左边和两边一起增加相同砝码的区别。';doc.add_paragraph(quote);stream=io.BytesIO();doc.save(stream)
 r=admin.post('/api/library/materials',data={'title':'第十五步来源核对材料','author':'工程验收自编','sourceNote':'仅用于工程验证，非真实课堂材料','grade':'七年级','subject':'数学'},files={'file':('来源核对.docx',stream.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')});assert r.status_code==201,r.text;material=r.json()
 for _ in range(40):
  material=admin.get('/api/library/materials/'+material['id']).json()
  if material.get('units'):break
  time.sleep(.25)
 assert material.get('units'),material
 unit=material['units'][0];assert quote in unit['text'];note('document-upload-and-source-parse',materialId=material['id'],unitId=unit['id'],text=unit['text'])
 assert admin.post('/api/library/cases/ops-case/revise').status_code==200
 current=admin.get('/api/library/cases/ops-case').json();data=current['draft'];data.pop('reviewed',None);data.pop('updatedAt',None);data['content']=quote+' 先记录单侧变化，再讨论两边共同运算。';data['references']=[{'unitId':unit['id'],'materialId':material['id'],'quote':quote,'label':unit['label'],'source':'工程验收自编'}]
 r=admin.put('/api/library/cases/ops-case/draft',json={'data':data});assert r.status_code==200,r.text
 r=admin.post('/api/library/cases/ops-case/publish');assert r.status_code==422,r.text;note('unreviewed-content-publication-rejected',status=r.status_code)
 assert admin.post('/api/library/cases/ops-case/review').status_code==200
 r=admin.post('/api/library/cases/ops-case/publish');assert r.status_code==200,r.text;new=r.json();assert new['published']['version']==2
 assert admin.get('/api/ai/cases/ops-case?versionId=ops-case-v1').json()==old
 fresh=teacher.get('/api/platform').json();assert tasks=={t['id']:{'questions':t['questions'],'snapshot':t['snapshot']} for t in fresh['tasks']}
 after=teacher.get('/api/teaching/tasks/ops-t00/supplements').json();assert refs=={r['id']:r.get('case') for r in after}
 note('review-revision-and-version2-publication',versionId=new['published']['versionId'],oldCaseUnchanged=True,oldTasksUnchanged=True,interventionCaseSnapshotsUnchanged=True)
Path('/tmp/sczx-step15/content-operations.json').write_text(json.dumps({'checks':checks,'passed':True},ensure_ascii=False,indent=2));print('source parse, review gate, revised publication and historical snapshots PASS')
