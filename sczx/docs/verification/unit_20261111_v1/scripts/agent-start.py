import json,sys,uuid,copy
from pathlib import Path
import httpx
root=Path('/root/Baxxhy/zhiwei/sczx');sys.path.insert(0,str(root/'scripts'))
from install_unit_content import call
fx=json.loads(Path('/tmp/sczx-step16/private.json').read_text());installed=json.loads(Path('/tmp/sczx-step16/content-installed.json').read_text());lid=installed['mapping']['lesson-simple']
with httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as c:
 assert c.post('/api/auth/login',json={'username':'unit-t1','password':fx['password']}).status_code==200
 lesson=call(c,'GET','/curriculum/lessons/'+lid);p=call(c,'GET','/platform?lessonId='+lid);d=p['lessonDraft'];d.update(lessonId=lid,goal=lesson['goal'],blocks=copy.deepcopy(lesson['blocks']),questions=copy.deepcopy(lesson['questions']),lessonSnapshot=lesson,caseId=lesson.get('caseId'),caseSnapshot=lesson.get('caseSnapshot'));d.setdefault('revision',0);call(c,'PUT','/platform',{'data':{'lessonDraft':d}})
 job=call(c,'POST','/ai/jobs',{'requestKey':uuid.uuid4().hex,'capability':'lesson_agent','data':{'lessonId':lid,'task':'为简单方程设计追问：学生只想移动符号，要求说明两边共同运算、非零条件，并代回原方程。保持本课题目不变。','taskType':'misconception','constraints':'使用当前课时与已选自编来源；不得用天平活动替代当前数值运算。文字具体、简洁。'}})
Path('/tmp/sczx-step16/agent-request.json').write_text(json.dumps({'id':job['id'],'lessonId':lid},ensure_ascii=False,indent=2));print(job['id'])
