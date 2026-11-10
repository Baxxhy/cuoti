import json,uuid
from pathlib import Path
import httpx
fx=json.loads(Path('/tmp/sczx-step15/browser-private.json').read_text());checks=[]
with httpx.Client(base_url='http://127.0.0.1:8015') as teacher,httpx.Client(base_url='http://127.0.0.1:8015') as student:
 for c,user in [(teacher,'ops-t1'),(student,'ops-s0')]:assert c.post('/api/auth/login',json={'username':user,'password':fx['password']}).status_code==200
 memory=teacher.get('/api/memory?studentId=ops-s0&classId=ops-c0').json();point=next(i for i in memory['items'] if i['id']=='ops-kp1');assert 'ops-kp' in {p['id'] for p in point['prerequisites']}
 for source,body in [('ops-target1',{'kind':'foundation','knowledgeId':'ops-kp1','target':{'taskId':'ops-t00','kind':'learn'},'content':'先复习等式两边共同运算，再返回逆运算课时。'}),('ops-t00',{'kind':'correction','knowledgeId':'ops-kp','target':{'wrongId':'ops-w-ops-s0','kind':'repair'},'content':'对照原答2，订正3z=18的运算过程。'})]:
  r=teacher.post('/api/teaching/tasks/'+source+'/supplements',json={**body,'studentIds':['ops-s0'],'requestKey':uuid.uuid4().hex});assert r.status_code==201,r.text
  rows=student.get('/api/teaching/tasks/'+source+'/supplements').json();item=next(i for i in rows if i['id']==r.json()['id']);assert item['recipients'][0]['outcome']['target']==body['target'];assert not item['recipients'][0]['outcome']['independentPassed'];checks.append({'sourceTask':source,'kind':body['kind'],'knowledgeId':body['knowledgeId'],'actualPrerequisite':point['prerequisites'] if body['kind']=='foundation' else None,'recipient':item['recipients'][0]})
Path('/tmp/sczx-step15/supplement-types.json').write_text(json.dumps({'passed':True,'checks':checks},ensure_ascii=False,indent=2));print('actual prerequisite lesson and owned course wrong targets delivered')
