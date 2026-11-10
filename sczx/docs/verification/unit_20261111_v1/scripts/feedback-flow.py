import json,uuid,sys,time
from pathlib import Path
import httpx
sys.path[:0]=['scripts','backend-business'];from install_unit_content import call
out=Path('/tmp/sczx-step16');fx=json.loads((out/'private.json').read_text());tasks=json.loads((out/'tasks.json').read_text());r={'checks':[]}
clients={n:httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) for n in ['unit-t1','unit-t2','unit-s0','unit-s4','unit-admin']}
for n,c in clients.items():assert c.post('/api/auth/login',json={'username':n,'password':fx['password']}).status_code==200
teacher,student=clients['unit-t1'],clients['unit-s0'];task=next(t['taskId'] for t in tasks['t1'] if t['sourceId']=='lesson-application');record=call(student,'GET','/platform')['records'][task]
insights=call(teacher,'GET','/insights?classId=unit-c0');assert any(q['taskId']==task and q['unverifiedStudents'] for q in insights['questions']);r['checks'].append({'name':'application-numeric-answer-still-needs-modeling-review','record':record['id'],'questions':insights['questions']})
wrong=next(w for w in call(student,'GET','/wrongs') if w['taskId']==task)
sup=call(teacher,'POST','/teaching/tasks/'+task+'/supplements',{'kind':'correction','knowledgeId':'kp-linear-model','studentIds':['unit-s0'],'target':{'wrongId':wrong['id'],'kind':'repair'},'content':'回看原答0与新的变式；说明设元、3件单价加6元运费的数量关系及单位，再检查代回结果。','requestKey':uuid.uuid4().hex});sid=sup['id']
call(student,'POST','/teaching/supplements/'+sid+'/start',{});call(student,'POST','/teaching/supplements/'+sid+'/submit',{'response':'设每件x元，三件商品费用3x元，加6元运费共21元，列3x+6=21；解为5元，代回满足数量关系。'})
feedback='已核对本题数量关系与单位。原答0和补救过程保留；后续独立题继续说明设元、列式与验算。'
call(teacher,'PUT','/teaching/supplements/'+sid+'/students/unit-s0/feedback',{'feedback':feedback});call(teacher,'PUT','/records/'+record['id']+'/feedback',{'feedback':feedback})
assert call(student,'GET','/platform')['records'][task]['feedback']==feedback
r['checks'].append({'name':'teacher-targets-real-wrong-student-submits-teacher-replies','supplementId':sid,'wrongId':wrong['id'],'feedback':feedback,'supplement':call(teacher,'GET','/teaching/tasks/'+task+'/supplements')})
issues=[]
for category,text in [('learning','应用题里6元是一次运费还是每件运费？'),('system','验收问题：重新打开网页后如何返回当前课时？')]:issues.append(call(student,'POST','/support',{'category':category,'taskId':task if category=='learning' else None,'text':text,'requestKey':uuid.uuid4().hex}))
i=issues[0];updated=call(teacher,'POST','/support/'+i['id']+'/events',{'status':'replied','content':'6元为整单一次运费，所以列3x+6=21。','expectedRevision':i['revision'],'requestKey':uuid.uuid4().hex});assert updated['reply'];r['checks'].append({'name':'two-independent-support-items-and-teacher-reply','issues':issues,'replied':updated})
for n,c in clients.items():
 if n in ['unit-t1','unit-s0']:continue
 for method,path,data in [('GET','/teaching/tasks/'+task,None),('PUT','/records/'+record['id']+'/feedback',{'feedback':'越界验收'}),('POST','/support/'+i['id']+'/events',{'status':'replied','content':'越界','expectedRevision':updated['revision'],'requestKey':uuid.uuid4().hex})]:
  response=c.request(method,'/api'+path,json=data);assert response.status_code in (403,404), (n,path,response.status_code);r['checks'].append({'name':'out-of-scope-denied','role':n,'method':method,'path':path,'status':response.status_code})
# Relogin restores actual feedback, not cached Vue state.
student.post('/api/auth/logout');assert student.post('/api/auth/login',json={'username':'unit-s0','password':fx['password']}).status_code==200;assert call(student,'GET','/platform')['records'][task]['feedback']==feedback
r.update(taskId=task,recordId=record['id'],feedback=feedback,passed=True);(out/'feedback-flow.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print('teacher feedback, correction, two support items, relogin and permission checks PASS')
