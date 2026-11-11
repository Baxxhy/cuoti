import json,time,sys,uuid
from pathlib import Path
import httpx
sys.path[:0]=['scripts','backend-business'];from install_unit_content import call
from sczx_business.math_tools import solve_text_equation
out=Path('/tmp/sczx-step17');f=json.loads((out/'private.json').read_text());exam=json.loads((out/'teacher-browser.json').read_text())['examId'];report={'jobs':[],'examId':exam}
def save():(out/'exam-repair.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
def job(c,w,data):
 start=time.monotonic();j=call(c,'POST','/ai/jobs',{'requestKey':uuid.uuid4().hex,'capability':'text','recordId':w['recordId'],'data':{'remediation':True,'wrongId':w['id'],**data}})
 for _ in range(400):
  j=call(c,'GET','/ai/jobs/'+j['id'])
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.5)
 report['jobs'].append({'seconds':round(time.monotonic()-start,3),'job':j});save();assert j['status']=='succeeded',j.get('error');return j
with httpx.Client(base_url='http://127.0.0.1:8089',timeout=30) as s,httpx.Client(base_url='http://127.0.0.1:8089',timeout=30) as t:
 for c,name in [(s,'unit-s0'),(t,'unit-t1')]:assert c.post('/api/auth/login',json={'username':name,'password':f['password']}).status_code==200
 wrongs=call(s,'GET','/wrongs');w=next(w for w in wrongs if w['details'].get('examId')==exam);report['before']=w;assert w['answer']=='0';analysis=job(s,w,{'mode':'analysis','prompt':'只依据本题原答案分析。证据字段逐字复制原答案的单个字符0，不添加引号、前缀或改写。不可猜测学生能力。'});call(s,'PUT','/wrongs/'+w['id'],{'cause':analysis['result']['cause'],'causeConfirmed':True});job(s,w,{'mode':'guidance','parentJobId':analysis['id'],'strategy':'hint','prompt':'针对原错给一个共同运算提示，不公布原题答案。'})
 report['variants']=[]
 for phase in ['practice','retest']:
  v=job(s,w,{'mode':'variant','phase':phase,'prompt':'生成与原题同运算结构但数值和解不同的新题，保持非零条件。'});equation=v['result']['variant']['equation'];solved,valid=solve_text_equation(equation);assert valid;a=call(s,'POST','/wrongs/'+w['id']+'/attempts',{'variantJobId':v['id'],'answer':solved.split('=',1)[1],'reason':'工程验收：解实际新题并代回，不把答案直接用于原始答卷。','requestKey':uuid.uuid4().hex});assert a['correct'];report['variants'].append({'actualEquation':equation,'attempt':a});save()
 final=call(s,'GET','/wrongs/'+w['id']);assert final['status']=='retest_passed' and final['answer']=='0';report['after']=final;memory=call(s,'GET','/memory');events=[e for k in memory['items'] for e in k['evidence']];assert any(e.get('wrongId')==w['id'] and e.get('sourceType')=='repair' for e in events);report['studentMemory']=memory;teacher=call(t,'GET','/memory?studentId=unit-s0&classId=unit-c0');assert any(e.get('wrongId')==w['id'] and e.get('sourceType')=='repair' for k in teacher['items'] for e in k['evidence']);report['teacherMemory']=teacher;published=call(s,'GET','/exams/'+exam);assert any(a.get('answer')=='0' for a in published['submission']['answers'].values());report['originalExamAfterRepair']=published['submission'];report['passed']=True;save();print('exam source -> actual model remediation -> verified new variants -> memory and teacher trace PASS')
