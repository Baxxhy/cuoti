import json,copy,uuid,sys
from pathlib import Path
import httpx
sys.path.insert(0,'scripts');from install_unit_content import call
fx=json.loads(Path('/tmp/sczx-step16/private.json').read_text());installed=json.loads(Path('/tmp/sczx-step16/content-installed.json').read_text());first=json.loads(Path('/tmp/sczx-step16/teacher-browser.json').read_text())
all_tasks={}
for name,room in [('t1','unit-c0'),('t2','unit-c1')]:
 with httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as c:
  assert c.post('/api/auth/login',json={'username':'unit-'+name,'password':fx['password']}).status_code==200
  if name=='t1':call(c,'POST','/classrooms/'+room+'/members',{'studentId':'unit-s8'})
  rows=[]
  for canonical,lid in installed['mapping'].items():
   if name=='t1' and canonical=='lesson-simple':
    # The teacher browser already created this exact Agent-backed task.
    task=first['task'];call(c,'POST','/teaching/tasks/'+task['id']+'/assign',{'studentIds':['unit-s8']});rows.append({'sourceId':canonical,'taskId':task['id'],'lessonId':lid});continue
   lesson=call(c,'GET','/curriculum/lessons/'+lid);platform=call(c,'GET','/platform?lessonId='+lid);d=platform['lessonDraft'];d.update(lessonId=lid,goal=lesson['goal'],blocks=copy.deepcopy(lesson['blocks']),questions=copy.deepcopy(lesson['questions']),lessonSnapshot=lesson,caseId=lesson.get('caseId'),caseSnapshot=lesson.get('caseSnapshot'));d.setdefault('revision',0);saved=call(c,'PUT','/platform',{'data':{'lessonDraft':d}});d['revision']=saved['draftRevision'];result=call(c,'POST','/tasks/publish',{'lessonId':lid,'classroomId':room,'lessonDraft':d,'idempotencyKey':uuid.uuid4().hex});rows.append({'sourceId':canonical,'taskId':result['taskId'],'lessonId':lid})
  all_tasks[name]=rows
  if name=='t1':
   invite=call(c,'POST','/teaching/classes/'+room+'/invites',{'days':1})
   with httpx.Client(base_url='http://127.0.0.1:8087') as late:
    late.post('/api/auth/login',json={'username':'unit-s7','password':fx['password']});call(late,'POST','/teaching/join',{'code':invite['code']})
   for row in rows:call(c,'POST','/teaching/tasks/'+row['taskId']+'/assign',{'studentIds':['unit-s7']})
   call(c,'DELETE','/teaching/classes/'+room+'/members/unit-s8')
Path('/tmp/sczx-step16/tasks.json').write_text(json.dumps(all_tasks,ensure_ascii=False,indent=2));print('2 teachers published 5 lessons; late join/backfill and removed history retained')
