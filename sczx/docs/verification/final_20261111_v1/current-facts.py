import json,httpx,sys
from pathlib import Path
sys.path.insert(0,'scripts');from install_unit_content import call
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());r={}
with httpx.Client(base_url='https://127.0.0.1:9443',verify=f['tlsCert']) as c:
 c.post('/api/auth/login',json={'username':'handoff-t1','password':f['password']});r['dashboard']=call(c,'GET','/teaching/dashboard?classId='+f['rooms'][0]);r['supplements']=call(c,'GET','/teaching/tasks/'+f['tasks'][0]['taskId']+'/supplements');r['group']=next(x for x in call(c,'GET','/groups') if x['id']==f['groupId']);r['teacherHelpJobs']=call(c,'GET','/ai/jobs?recordId='+f['recordId']);r['insights']=call(c,'GET','/insights?classId='+f['rooms'][0]);
with httpx.Client(base_url='https://127.0.0.1:9443',verify=f['tlsCert']) as c:
 c.post('/api/auth/login',json={'username':'handoff-s1','password':f['password']});r['examWrongCount']=sum(w.get('details',{}).get('examId')==f['examId'] for w in call(c,'GET','/wrongs'));r['unit']=call(c,'GET','/units/unit-equation/progress?classId='+f['rooms'][0]);r['wrong']=call(c,'GET','/wrongs/'+f['wrong']['id']);r['studentFeedback']=call(c,'GET','/platform')['records'][f['tasks'][0]['taskId']]['feedback'];assert r['unit']['completed']==5 and r['wrong']['status']=='retest_passed' and r['examWrongCount']>=1
(out/'current-facts.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print('actual unit5/5, retest, exam wrong, class/group/intervention evidence and UI feedback re-read PASS')
