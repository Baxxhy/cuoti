import json,uuid,time,sys,copy
from pathlib import Path
import httpx
sys.path[:0]=['scripts','backend-business'];from install_unit_content import call
from sczx_business.math_tools import solve_text_equation
out=Path('/tmp/sczx-step16');fx=json.loads((out/'private.json').read_text());r={'checks':[],'jobs':[]}
def save():(out/'release-smoke.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
def job(c,record,data):
 start=time.monotonic();j=call(c,'POST','/ai/jobs',{'capability':'text','recordId':record,'requestKey':uuid.uuid4().hex,'data':data})
 for _ in range(360):
  j=call(c,'GET','/ai/jobs/'+j['id'])
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.5)
 r['jobs'].append({'seconds':round(time.monotonic()-start,3),'job':j});save();assert j['status']=='succeeded',j.get('error');return j
with httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as admin,httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as t,httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as s:
 admin.post('/api/auth/login',json={'username':'unit-admin','password':fx['password']})
 users={}
 for role in ['teacher','student']:
  name='release-'+role+'-'+uuid.uuid4().hex[:5];users[role]=call(admin,'POST','/accounts',{'username':name,'password':fx['password'],'displayName':'预发布冒烟自编验收'+role,'role':role});assert (t if role=='teacher' else s).post('/api/auth/login',json={'username':name,'password':fx['password']}).status_code==200
 room=call(t,'POST','/classrooms',{'name':'新建预发布冒烟验收班','grade':'七年级','subject':'数学'});invite=call(t,'POST','/teaching/classes/'+room['id']+'/invites',{'days':1});call(s,'POST','/teaching/join',{'code':invite['code']});lesson=call(t,'GET','/curriculum/lessons/lesson-simple');d=call(t,'GET','/platform?lessonId=lesson-simple')['lessonDraft'];d.update(lessonId='lesson-simple',goal=lesson['goal'],blocks=lesson['blocks'],questions=lesson['questions'],lessonSnapshot=lesson,caseId=lesson.get('caseId'),caseSnapshot=lesson.get('caseSnapshot'));d.setdefault('revision',0);saved=call(t,'PUT','/platform',{'data':{'lessonDraft':d}});d['revision']=saved['draftRevision'];task=call(t,'POST','/tasks/publish',{'lessonId':'lesson-simple','classroomId':room['id'],'lessonDraft':d,'idempotencyKey':uuid.uuid4().hex})['taskId'];rec=call(s,'GET','/platform')['records'][task]
 attempt=call(s,'POST','/records/'+task+'/attempts',{'question':0,'answer':'0','reason':'我直接猜0，没有核对两边。'});assert not attempt['correct'];wrong=next(w for w in call(s,'GET','/wrongs') if w['taskId']==task)
 hint=job(s,rec['id'],{'guidance':True,'question':0,'strategy':'hint','prompt':'请只提示当前题第一步，保留我已有的错误答案。'})
 a=job(s,rec['id'],{'remediation':True,'wrongId':wrong['id'],'mode':'analysis','prompt':'证据逐字复制我的原答案单字符0，不加引号或前缀；只列可能错因。'});call(s,'PUT','/wrongs/'+wrong['id'],{'cause':a['result']['cause'],'causeConfirmed':True})
 job(s,rec['id'],{'remediation':True,'wrongId':wrong['id'],'mode':'guidance','strategy':'hint','parentJobId':a['id'],'prompt':'针对当前错因给一步提示。'})
 for phase in ['practice','retest']:
  v=job(s,rec['id'],{'remediation':True,'wrongId':wrong['id'],'mode':'variant','phase':phase,'prompt':'保持当前加法一步方程结构，使用不同数值生成新题。'});solved,ok=solve_text_equation(v['result']['variant']['equation']);assert ok;answer=call(s,'POST','/wrongs/'+wrong['id']+'/attempts',{'variantJobId':v['id'],'answer':solved.split('=',1)[1],'reason':'两边共同运算并代回核对。','requestKey':uuid.uuid4().hex});assert answer['correct']
 reviewed=call(t,'GET','/platform')['studentRecords'][task];assert reviewed[0]['attempts'][0]['answer']=='0';assert len(reviewed[0]['repairs'])>=2
 message='先保留原答0，再看共同减去同一个数的步骤；已看到你完成新题复测。';call(t,'PUT','/records/'+rec['id']+'/feedback',{'feedback':message});s.post('/api/auth/logout');s.post('/api/auth/login',json={'username':users['student']['username'],'password':fx['password']});assert call(s,'GET','/platform')['records'][task]['feedback']==message
 r.update(passed=True,taskId=task,classId=room['id'],users=users,sourceVersion=lesson['versionId'],wrong=call(s,'GET','/wrongs/'+wrong['id']),checks=['API-created accounts','teacher created class','student joined by invite','reviewed lesson published','real wrong answer','real guidance','actual variants verified','teacher reads original','feedback after student relogin']);save();print('new-account release smoke full loop PASS')
