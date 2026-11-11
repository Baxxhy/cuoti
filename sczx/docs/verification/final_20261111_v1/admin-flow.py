import json,io,time,sys,uuid
from pathlib import Path
from docx import Document
import httpx
sys.path.insert(0,'scripts');from install_unit_content import call
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());r={'at':time.time(),'checks':[]};doc=Document();doc.add_heading('共同运算核对',0);doc.add_paragraph('出示x−3=5。问：如果左边加3，右边应怎样变化？让学生写出x−3+3=5+3，再得x=8，代回8−3=5。');doc.add_paragraph('同除只能除以非零数。不要把变号当作不需要依据的移动。');buf=io.BytesIO();doc.save(buf)
with httpx.Client(base_url='https://127.0.0.1:9443',verify=f['tlsCert'],timeout=180) as c:
 assert c.post('/api/auth/login',json={'username':'handoff-admin','password':f['password']}).status_code==200
 start=time.monotonic();response=c.post('/api/library/materials',files={'file':('交付验收自编材料.docx',buf.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')},data={'title':'交付验收自编共同运算材料','author':'项目工程验收','sourceNote':'合成示例，非真实课堂材料','grade':'七年级','subject':'数学'});assert response.status_code==201,response.text;material=response.json();r['uploadSeconds']=round(time.monotonic()-start,3)
 for _ in range(150):
  material=call(c,'GET','/library/materials/'+material['id'])
  if material['status']=='ready':break
  time.sleep(.2)
 assert material['status']=='ready';units=[u['id'] for u in material['units']];r['checks'].append({'name':'upload-parse-reread-original','materialId':material['id'],'units':len(units)})
 # Manual editor path: uses actual original source units and preserves revision/publish lifecycle.
 case=call(c,'POST','/library/cases',{'title':'交付验收：共同运算追问','unitIds':units[:2]});data=case['draft'];data.update(title='交付验收：共同运算追问',content='出示x−3=5，先问两边同时进行什么运算，再写等式并代回。',source='交付验收自编共同运算材料',author='项目工程验收',grade='七年级',subject='数学',knowledgeIds=['kp-equality']);case=call(c,'PUT','/library/cases/'+case['id']+'/draft',{'data':data});call(c,'POST','/library/cases/'+case['id']+'/verify');call(c,'POST','/library/cases/'+case['id']+'/review');published=call(c,'POST','/library/cases/'+case['id']+'/publish');r['checks'].append({'name':'edit-verify-review-publish-with-original-reference','caseId':case['id'],'case':published})
 issues=call(c,'GET','/support');jobs=call(c,'GET','/ai/jobs');r['checks'].append({'name':'admin-existing-feedback-and-model-abnormality-list','issues':len(issues),'modelJobs':len(jobs),'failedJobs':sum(j['status']=='failed' for j in jobs)})
r['passed']=True;(out/'admin-flow.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print('admin upload/local parse/source/edit/review/publish/issues/tasks PASS')
