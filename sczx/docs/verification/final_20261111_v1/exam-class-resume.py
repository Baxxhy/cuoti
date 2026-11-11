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
old=json.loads((out/'exam-class-flows.json').read_text());report=old;eid=next(x['examId'] for x in old['checks'] if x['name'].startswith('exam-'));d=api(t,'GET','/exams/'+eid);paper=next(p for p in api(t,'GET','/exams/papers') if p['draft']['title']=='交付验收共同运算检查');pv=paper['versions'][0]['id'];live=next(x['live'] for x in old['checks'] if x['name'].startswith('live-'))
api(t,'GET','/groups/suggestions?classId='+f['rooms'][0]+'&knowledgeId=kp-equality');group=api(t,'POST','/groups',{'classId':f['rooms'][0],'knowledgeId':'kp-equality','groups':[{'label':'巩固','studentIds':[f['users']['handoff-s1']],'versionId':pv},{'label':'拓展','studentIds':[f['users']['handoff-s2']],'versionId':pv}]});group=api(t,'POST','/groups/'+group['id']+'/publish',{'revision':group['revision'],'confirmed':True});gt=next(x for x in group['tasks'] if x['title'].startswith('巩固'));api(students[0],'POST','/records/'+gt['id']+'/attempts',{'question':0,'answer':'2','reason':'先减6再除2，代回。'});group=next(x for x in api(t,'GET','/groups') if x['id']==group['id']);note('groups-publish-and-real-followup',group=group)
case=f['case'];share=api(t,'POST','/community',{'kind':'case','sourceId':case['id'],'versionId':case['versionId'],'confirmed':True});api(t2,'PUT','/community/'+share['id']+'/bookmark',{'selected':True});share=api(t2,'POST','/community/'+share['id']+'/events',{'kind':'discussion','text':'先要求说清两边共同变化，保留不能除零的条件。'});assert share['snapshot']['versionId']==case['versionId'];note('community-source-version-preserved',shareId=share['id'])
# Concrete intervention references the actual original wrong, student performs new answer.
sup=api(t,'POST','/teaching/tasks/'+f['tasks'][0]['taskId']+'/supplements',{'kind':'correction','knowledgeId':'kp-equality','studentIds':[f['users']['handoff-s1']],'target':{'wrongId':f['wrong']['id'],'kind':'repair'},'content':'回看原答0，再做一次共同运算与代回核对。','requestKey':uuid.uuid4().hex});api(students[0],'POST','/teaching/supplements/'+sup['id']+'/start',{});api(students[0],'POST','/teaching/supplements/'+sup['id']+'/submit',{'response':'两边同时加3，x=8，8−3=5。'});api(t,'PUT','/teaching/supplements/'+sup['id']+'/students/'+f['users']['handoff-s1']+'/feedback',{'feedback':'已收到，继续核对新方程。'});note('intervention-sent-started-submitted-feedback',supplementId=sup['id'])
f.update(examId=eid,paperId=paper['id'],paperVersion=pv,liveId=live['id'],groupId=group['id'],shareId=share['id'],supplementId=sup['id'])
for p in [out/'private.json',Path(f['base'])/'private.json']:p.write_text(json.dumps(f));p.chmod(0o600)
report['passed']=True;save()
