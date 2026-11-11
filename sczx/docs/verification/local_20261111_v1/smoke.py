import json,uuid,time,sys,zipfile,io
from pathlib import Path
import httpx
out=Path('/tmp/sczx-local-final');f=json.loads(Path('/tmp/sczx-step20/private.json').read_text());accounts=json.loads(Path('backend-business/var/local/accounts.json').read_text());report={'at':time.time(),'checks':[]};clients={}
for a in accounts:
 c=httpx.Client(base_url='http://127.0.0.1:8099',timeout=180);assert c.post('/api/auth/login',json={'username':a['username'],'password':a['password']}).status_code==200;clients[a['username']]=c
s=clients['handoff-s2'];t=clients['handoff-t1'];admin=clients['handoff-admin'];p=s.get('/api/platform').json();task=next(x for x in p['tasks'] if x['source']=='published' and not p['records'][x['id']]['completed']);f.update(imagesTask=task['id'],normalTask=task['id']);f['currentRecord']=p['records'][task['id']]['id']
for who,c,paths in [('teacher',t,['/teaching/classes','/insights?classId='+f['rooms'][0],'/groups','/community','/live','/exams/papers','/exams/bank','/exams','/preparation/'+f['lessons'][1]+'/export-options']),('student',s,['/curriculum/courses','/memory','/wrongs','/exams','/live','/teaching/messages','/offline/tasks']),('admin',admin,['/library/materials','/library/cases','/curriculum/courses','/support','/ai/capabilities'])]:
 for path in paths:
  r=c.get('/api'+path);assert r.status_code==200,(who,path,r.text);report['checks'].append({'role':who,'method':'GET','path':path,'status':r.status_code,'count':len(r.json())})
r=t.get('/api/preparation/'+f['lessons'][1]+'/export');assert r.status_code==200
with zipfile.ZipFile(io.BytesIO(r.content)) as z:
 styles=z.read('word/styles.xml').decode();assert '宋体' in styles and 'Times New Roman' in styles
(out/'本地导出样例.docx').write_bytes(r.content);report['exportDocx']=True
r=s.post('/api/support',json={'category':'system','text':'本地使用验收：如何保留离线草稿？','requestKey':uuid.uuid4().hex});assert r.status_code==201,r.text;issue=r.json();r=admin.post('/api/support/'+issue['id']+'/events',json={'status':'replied','content':'退出时选择保留加密下载，联网后用同一账号同步。','expectedRevision':issue['revision'],'requestKey':uuid.uuid4().hex});assert r.status_code==200,r.text;report['newIssueReplyId']=issue['id']
r=clients['handoff-t2'].get('/api/teaching/tasks/'+task['id']);assert r.status_code in (403,404);report['crossTeacherDenied']=r.status_code
started=time.monotonic();r=s.post('/api/ai/jobs',json={'recordId':f['currentRecord'],'capability':'text','requestKey':uuid.uuid4().hex,'data':{'guidance':True,'question':0,'strategy':'hint','prompt':'我想只改变等式左边，请围绕当前题给一步提示，不给答案。'}});assert r.status_code==201,r.text;j=r.json()
for _ in range(400):
 j=s.get('/api/ai/jobs/'+j['id']).json()
 if j['status'] in ['succeeded','failed','cancelled']:break
 time.sleep(.5)
report['actualLocalModel']={'seconds':round(time.monotonic()-started,3),'job':j};assert j['status']=='succeeded',j.get('error')
report['passed']=True;(out/'local-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));f['password']=next(a['password'] for a in accounts if a['username']=='handoff-s2');(out/'private.json').write_text(json.dumps(f));(out/'private.json').chmod(0o600);print('local three roles/module reads,Word export,new support reply,permission and actual luna/low guidance PASS')
