import json,time,uuid,copy,sys,io
from pathlib import Path
import httpx
sys.path[:0]=['scripts','backend-business'];from install_unit_content import call
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());report={'startedAt':time.time(),'checks':[],'metrics':[]};clients={}
def save():(out/'final-flows.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
def note(name,**data):report['checks'].append({'name':name,**data});save();print(name,flush=True)
def api(c,method,path,body=None):
 t=time.monotonic();v=call(c,method,path,body);report['metrics'].append({'operation':method+' '+path,'seconds':round(time.monotonic()-t,4)});return v
def login(name,password=None):
 c=httpx.Client(base_url='https://127.0.0.1:9443',verify=f['tlsCert'],timeout=180);r=c.post('/api/auth/login',json={'username':name,'password':password or f['password']});assert r.status_code==200,(name,r.status_code);clients[name]=c;return c
bootstrap=login('offline-admin',f['bootstrapPassword'])
# Admin provisioning is a deployment-only seed; teacher/student creation uses authorized UI API.
import os;os.environ['SCZX_DATABASE_URL']=f['demoUrl']
from sczx_business.database import SessionLocal
from sczx_business.models import Account
from sczx_business.security import hash_password
with SessionLocal.begin() as db:
 if not db.get(Account,'handoff-admin'):db.add(Account(id='handoff-admin',username='handoff-admin',display_name='交付验收管理员',role='admin',password_hash=hash_password(f['password'])))
a=login('handoff-admin');users={u['username']:u for u in api(a,'GET','/accounts')}
for name,role in [('t1','teacher'),('t2','teacher')]+[('s'+str(i),'student') for i in range(1,6)]:
 un='handoff-'+name
 if un not in users:users[un]=api(a,'POST','/accounts',{'username':un,'password':f['password'],'displayName':'交付验收·'+name,'role':role})
f['users']={k:v['id'] for k,v in users.items() if k.startswith('handoff-')};t1=login('handoff-t1');t2=login('handoff-t2');students=[login('handoff-s'+str(i)) for i in range(1,6)]
rooms=[]
for i,t in enumerate([t1,t2]):
 old=api(t,'GET','/teaching/classes');room=next((r for r in old if r['name']=='最终交付'+str(i+1)+'班'),None) or api(t,'POST','/classrooms',{'name':'最终交付'+str(i+1)+'班','grade':'七年级','subject':'数学'});rooms.append(room['id']);invite=api(t,'POST','/teaching/classes/'+room['id']+'/invites',{'days':1})
 for s in [students[i*2],students[i*2+1],students[4]]:api(s,'POST','/teaching/join',{'code':invite['code']})
f['rooms']=rooms
catalog=api(t1,'GET','/curriculum/courses');course=next(c for c in catalog if any(u['id']=='unit-equation' for u in c['units']));unit=next(u for u in course['units'] if u['id']=='unit-equation');order=course['metadata']['unitPlans']['unit-equation'];lessons={lid:api(t1,'GET','/curriculum/lessons/'+lid) for lid in order};f['lessons']=order
search=api(t1,'POST','/ai/search',{'query':'等式 两边 相同 运算','filters':{'knowledgeIds':['kp-equality']}});assert search['items'];f['case']=search['items'][0]
tasks=[]
for lid in order:
 lesson=lessons[lid];d=api(t1,'GET','/platform?lessonId='+lid)['lessonDraft'];d.update(lessonId=lid,goal=lesson['goal']+' 写出运算依据并代回核对。',blocks=copy.deepcopy(lesson['blocks']),questions=copy.deepcopy(lesson['questions']),lessonSnapshot=lesson,caseId=lesson.get('caseId'),caseSnapshot=lesson.get('caseSnapshot'));saved=api(t1,'PUT','/platform',{'data':{'lessonDraft':d}});d['revision']=saved['draftRevision'];r=api(t1,'POST','/tasks/publish',{'lessonId':lid,'classroomId':rooms[0],'lessonDraft':d,'idempotencyKey':uuid.uuid4().hex});tasks.append({'taskId':r['taskId'],'lessonId':lid})
f['tasks']=tasks
for p in [out/'private.json',Path(f['base'])/'private.json']:p.write_text(json.dumps(f));p.chmod(0o600)
# Course attempts are synthetic engineering inputs, not measured human learning.
s=students[0]
for ix,row in enumerate(tasks):
 task=row['taskId'];lesson=lessons[row['lessonId']];p=api(s,'GET','/platform');record=p['records'][task]
 for qi,q in enumerate(lesson['questions']):api(s,'POST','/records/'+task+'/attempts',{'question':qi,'answer':'0' if ix==0 and qi==0 else q['answer'],'reason':'工程验收：两边共同运算并代回原方程。'})
 # Set required study fields via normal platform update, keeping all server records.
 p=api(s,'GET','/platform');r=p['records'][task];r['observation']='两边进行相同运算，除数必须非零。';r['completedBlocks']=[b['id'] for b in lesson['blocks']];r['drafts']={'blocks':{b['id']:{'completed':True,'explanation':'两边相同运算，除数非零。'} for b in lesson['blocks']}};api(s,'PUT','/platform',{'data':{'records':{task:r}}})
 response=s.post('/api/records/'+task+'/submit');
 if response.status_code!=200:note('course-submit-needs-browser-completion',taskId=task,status=response.status_code,detail=response.json())
 else:note('lesson-submitted',taskId=task)
progress=api(s,'GET','/units/unit-equation/progress?classId='+rooms[0]);note('five-lessons-assigned',progress=progress)
record=api(s,'GET','/platform')['records'][tasks[0]['taskId']];f['recordId']=record['id'];f['wrong']=next(w for w in api(s,'GET','/wrongs') if w['taskId']==tasks[0]['taskId'])
api(t1,'PUT','/records/'+record['id']+'/feedback',{'feedback':'保留原答0。请先说明共同运算，再完成新题并代回。'});assert api(s,'GET','/platform')['records'][tasks[0]['taskId']]['feedback'];note('feedback-roundtrip',recordId=record['id'])
for c,path in [(t2,'/teaching/tasks/'+tasks[0]['taskId']),(students[2],'/teaching/tasks/'+tasks[0]['taskId']),(students[1],'/equation-tools/'+record['id']+'/0')]:
 r=c.get('/api'+path);assert r.status_code in(403,404);note('permission-denied',path=path,status=r.status_code)
api(s,'PUT','/equation-tools/'+record['id']+'/0',{'revision':0,'actions':[],'explanation':'保留原式，逐步进行相同运算。'});note('equation-tool-saved')
for p in [out/'private.json',Path(f['base'])/'private.json']:p.write_text(json.dumps(f));p.chmod(0o600)
report['completedAt']=time.time();save();print('fixture/core flows ready')
