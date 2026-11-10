import json,time,zipfile,io,statistics
from pathlib import Path
import httpx
out=Path('/tmp/sczx-step16');fx=json.loads((out/'private.json').read_text());installed=json.loads((out/'content-installed.json').read_text());checks=[]
with httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as c:
 assert c.post('/api/auth/login',json={'username':'unit-t1','password':fx['password']}).status_code==200
 data=c.get('/api/platform',params={'lessonId':installed['mapping']['lesson-simple']}).json();draft=data['lessonDraft'];versions=c.get('/api/preparation/'+installed['mapping']['lesson-simple']+'/versions').json();vid=versions[0]['id'] if isinstance(versions,list) else versions['versions'][0]['id'];r=c.get('/api/preparation/'+installed['mapping']['lesson-simple']+'/export',params={'versionId':vid,'mode':'formal'});assert r.status_code==200,r.text
 path=out/'简单方程_正式教案.docx';path.write_bytes(r.content)
 with zipfile.ZipFile(io.BytesIO(r.content)) as z:
  xml=z.read('word/document.xml').decode();styles=z.read('word/styles.xml').decode();assert '宋体' in xml+styles and 'Times New Roman' in xml+styles;assert '000000' in xml+styles
  from xml.etree import ElementTree as E
  ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};text=''.join(E.fromstring(xml).itertext());assert draft['goal'] in text
 checks.append({'name':'actual_saved_version_docx','draftId':draft['id'],'versionId':vid,'fonts':['宋体','Times New Roman'],'black':True,'goalMatchesSavedVersion':True,'file':path.name})
 timings={}
 for endpoint in ['/api/health','/api/teaching/classes','/api/insights?classId=unit-c0','/api/curriculum/courses']:
  samples=[]
  for _ in range(3):
   start=time.perf_counter();r=c.get(endpoint);assert r.status_code==200;r.content;samples.append(round((time.perf_counter()-start)*1000,2))
  timings[endpoint]={'milliseconds':samples,'median':statistics.median(samples)}
 start=time.perf_counter();r=c.get('/');assert r.status_code==200 and 'assets/' in r.text;static={'httpMilliseconds':round((time.perf_counter()-start)*1000,2),'bytes':len(r.content),'productionAssets':True}
 out.joinpath('export-metrics.json').write_text(json.dumps({'checks':checks,'api':timings,'static':static,'scope':'local 3 samples, not a production load benchmark'},ensure_ascii=False,indent=2));print('saved-version DOCX fonts/content and local API metrics PASS')
