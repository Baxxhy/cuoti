import json,time,sys
from pathlib import Path
import httpx
sys.path.insert(0,'scripts');from install_unit_content import call
out=Path('/tmp/sczx-step17');f=json.loads((out/'private.json').read_text());initial=json.loads((out/'flow-fixture.json').read_text());r={}
with httpx.Client(base_url='http://127.0.0.1:8089',timeout=30) as c:
 c.post('/api/auth/login',json={'username':'unit-t1','password':f['password']});jid=initial['candidate']['id']
 for _ in range(240):
  j=call(c,'GET','/ai/jobs/'+jid)
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.5)
 assert j['status']=='succeeded',j.get('error');q=call(c,'POST','/exams/bank/candidate/'+jid,{});assert q['reviewed'] is False and q['versions']==[];same=call(c,'POST','/exams/bank/candidate/'+jid,{});assert same['id']==q['id'];r.update(passed=True,job=j,question=q,explicitlyAdoptedAsDraft=True,notAutoReviewed=True)
(out/'candidate-check.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print('real Codex candidate validated and adopted only as pending draft PASS')
