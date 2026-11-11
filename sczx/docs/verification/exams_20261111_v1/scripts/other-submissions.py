import json,sys
from pathlib import Path
import httpx
sys.path.insert(0,'scripts');from install_unit_content import call
out=Path('/tmp/sczx-step17');f=json.loads((out/'private.json').read_text());teacher=json.loads((out/'teacher-browser.json').read_text());report=[]
for name in ['unit-s1','unit-s2','unit-s6']:
 with httpx.Client(base_url='http://127.0.0.1:8089',timeout=30) as c:
  c.post('/api/auth/login',json={'username':name,'password':f['password']});d=call(c,'POST','/exams/'+teacher['examId']+'/start',{});answers={e['versionId']:{'answer':e['question']['answer'],'reason':'工程验收：对照实际自编方程作答，非课堂效果样本。'} for e in teacher['exam']['paper']['entries']};d=call(c,'POST','/exams/'+teacher['examId']+'/submit',{'revision':d['submission']['revision'],'answers':answers});report.append({'student':name,'submission':d['submission']})
(out/'other-submissions.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('3 additional assigned students actually submitted, own records only')
