import json,time,uuid,sys,copy
from pathlib import Path
from datetime import datetime,timezone,timedelta
import httpx
sys.path.insert(0,'scripts');from install_unit_content import call
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());report={'at':datetime.now(timezone.utc).isoformat(),'checks':[],'metrics':[]}
def save():(out/'exam-class-flows.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
def note(name,**data):report['checks'].append({'name':name,**data});save();print(name,flush=True)
def client(u):
 c=httpx.Client(base_url='https://127.0.0.1:9443',verify=f['tlsCert'],timeout=180);assert c.post('/api/auth/login',json={'username':'handoff-'+u,'password':f['password']}).status_code==200;return c
def api(c,method,path,body=None):
 t=time.monotonic();v=call(c,method,path,body);report['metrics'].append({'operation':method+' '+path,'seconds':round(time.monotonic()-t,4)});return v
t=client('t1');t2=client('t2');students=[client('s'+str(i)) for i in [1,2,5]];vids=[]
for eq,answer in [('2x+6=10','2'),('x+7=12','5')]:
 q=api(t,'POST','/exams/bank',{'data':{'prompt':'解方程并代回核对','equation':eq,'answer':answer,'explanation':'两边进行相同运算，除数不能为零。','knowledgeIds':['kp-equality'],'unitId':'unit-equation','source':'最终隔离验收自编题','kind':'calculation','difficulty':'easy','points':10}});q=api(t,'POST','/exams/bank/'+q['id']+'/review',{'revision':q['revision'],'confirmed':True});vids.append(q['versions'][0]['id'])
assembled=api(t,'POST','/exams/assemble',{'unitId':'unit-equation','knowledgeIds':['kp-equality'],'count':2,'total':20});assert assembled['sufficient'];paper=api(t,'POST','/exams/papers',{'title':'交付验收共同运算检查','unitId':'unit-equation','entries':[{'versionId':v['versionId'],'points':v['points']} for v in assembled['entries']]});paper=api(t,'POST','/exams/papers/'+paper['id']+'/review',{'revision':paper['revision'],'confirmed':True});pv=paper['versions'][0]['id'];now=datetime.now(timezone.utc);exam=api(t,'POST','/exams',{'versionId':pv,'classId':f['rooms'][0],'startsAt':(now-timedelta(minutes=1)).isoformat(),'endsAt':(now+timedelta(hours=6)).isoformat(),'minutes':120,'requestKey':uuid.uuid4().hex});eid=exam['id']
for i,s in enumerate(students):
 d=api(s,'POST','/exams/'+eid+'/start',{});assert all('answer' not in q['question'] for q in d['paper']['entries']);answers={q['versionId']:{'answer':'0' if i==0 else next(x['question']['answer'] for x in assembled['entries'] if x['versionId']==q['versionId']),'reason':'先同减常数，再除以非零系数。'} for q in d['paper']['entries']};d=api(s,'PUT','/exams/'+eid+'/answers',{'revision':d['submission']['revision'],'answers':answers});d=api(s,'POST','/exams/'+eid+'/submit',{'revision':d['submission']['revision'],'answers':answers});assert 'grades' not in d['submission']
d=api(t,'GET','/exams/'+eid)
for submission in d['submissions']:
 grades={q['versionId']:{'score':0 if submission['studentId']==f['users']['handoff-s1'] else q['points'],'comment':'已核对原始作答与过程。'} for q in d['paper']['entries']};api(t,'PUT','/exams/'+eid+'/submissions/'+submission['id']+'/grades',{'revision':submission['revision'],'grades':grades})
api(t,'POST','/exams/'+eid+'/results',{'confirmed':True});d=api(students[0],'GET','/exams/'+eid);assert d['submission']['total']==0 and all('answer' in q['question'] for q in d['paper']['entries']);note('exam-assemble-review-publish-draft-submit-grade-release',examId=eid,participants=3,studentTotal=0)
# Real two-student live replies; third cross-class member participates as well.
live=api(t,'POST','/live',{'classId':f['rooms'][0],'lessonId':f['lessons'][0]});live=api(t,'POST','/live/'+live['id']+'/push',{'revision':live['revision'],'question':0});aid=live['currentId']
for s in students[:2]:api(s,'POST','/live/'+live['id']+'/join',{});api(s,'PUT','/live/'+live['id']+'/activities/'+aid+'/answer',{'revision':0,'answer':'8','reason':'两边同时加3。','submit':True})
live=api(t,'GET','/live/'+live['id']);assert live['activities'][0]['stats']['submitted']==2;live=api(t,'POST','/live/'+live['id']+'/end',{'revision':live['revision']});assert live['taskId'];note('live-two-actual-students-ended-history',live=live)
api(t,'GET','/groups/suggestions?classId='+f['rooms'][0]+'&knowledgeId=kp-equality');group=api(t,'POST','/groups',{'classId':f['rooms'][0],'knowledgeId':'kp-equality','groups':[{'label':'订正巩固','studentIds':[f['users']['handoff-s1']],'versionId':pv},{'label':'独立练习','studentIds':[f['users']['handoff-s2']],'versionId':pv}]});group=api(t,'POST','/groups/'+group['id']+'/publish',{'revision':group['revision'],'confirmed':True});gt=next(x for x in group['tasks'] if x['title'].startswith('订正'));api(students[0],'POST','/records/'+gt['id']+'/attempts',{'question':0,'answer':'2','reason':'先减6再除2，代回。'});group=next(x for x in api(t,'GET','/groups') if x['id']==group['id']);note('groups-publish-and-real-followup',group=group)
case=f['case'];share=api(t,'POST','/community',{'kind':'case','sourceId':case['id'],'versionId':case['versionId'],'confirmed':True});api(t2,'PUT','/community/'+share['id']+'/bookmark',{'selected':True});share=api(t2,'POST','/community/'+share['id']+'/events',{'kind':'discussion','text':'先要求说清两边共同变化，保留不能除零的条件。'});assert share['snapshot']['versionId']==case['versionId'];note('community-source-version-preserved',shareId=share['id'])
# Concrete intervention references the actual original wrong, student performs new answer.
sup=api(t,'POST','/teaching/tasks/'+f['tasks'][0]['taskId']+'/supplements',{'kind':'correction','knowledgeId':'kp-equality','studentIds':[f['users']['handoff-s1']],'target':{'wrongId':f['wrong']['id'],'kind':'repair'},'content':'回看原答0，再做一次共同运算与代回核对。','requestKey':uuid.uuid4().hex});api(students[0],'POST','/teaching/supplements/'+sup['id']+'/start',{});api(students[0],'POST','/teaching/supplements/'+sup['id']+'/submit',{'response':'两边同时加3，x=8，8−3=5。'});api(t,'PUT','/teaching/supplements/'+sup['id']+'/students/'+f['users']['handoff-s1']+'/feedback',{'feedback':'已收到，继续核对新方程。'});note('intervention-sent-started-submitted-feedback',supplementId=sup['id'])
f.update(examId=eid,paperId=paper['id'],paperVersion=pv,liveId=live['id'],groupId=group['id'],shareId=share['id'],supplementId=sup['id'])
for p in [out/'private.json',Path(f['base'])/'private.json']:p.write_text(json.dumps(f));p.chmod(0o600)
report['passed']=True;save()
