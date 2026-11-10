import json,uuid,time,sys
from pathlib import Path
import httpx
sys.path[:0]=['scripts','backend-business'];from install_unit_content import call
from sczx_business.math_tools import solve_text_equation
out=Path('/tmp/sczx-step16');fx=json.loads((out/'private.json').read_text());r={'queries':[]}
with httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as t,httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as s:
 for c,u in [(t,'unit-t1'),(s,'unit-s0')]:assert c.post('/api/auth/login',json={'username':u,'password':fx['password']}).status_code==200
 for lesson,q in [('equality','天平 两边 共同运算 非零'),('simple','逆运算 简单方程 代回'),('transform','括号 分母 公倍数'),('application','商品 运费 单位 数量关系'),('review','单元 复习 共同运算')]:
  result=call(t,'POST','/ai/search',{'query':q});r['queries'].append({'lesson':lesson,'query':q,'result':result})
 feedback=json.loads((out/'feedback-flow.json').read_text());wrongId=feedback['checks'][1]['wrongId'];w=call(s,'GET','/wrongs/'+wrongId);started=time.monotonic();j=call(s,'POST','/ai/jobs',{'recordId':w['recordId'],'capability':'text','requestKey':uuid.uuid4().hex,'data':{'remediation':True,'wrongId':wrongId,'mode':'variant','phase':'retest','prompt':'在教师订正安排后生成另一道可核验的新方程，保持原题乘加结构；数值与解均区别以往。'}})
 for _ in range(400):
  j=call(s,'GET','/ai/jobs/'+j['id'])
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.5)
 assert j['status']=='succeeded',j.get('error');equation=j['result']['variant']['equation'];solved,ok=solve_text_equation(equation);assert ok;attempt=call(s,'POST','/wrongs/'+wrongId+'/attempts',{'variantJobId':j['id'],'answer':solved.split('=',1)[1],'reason':'根据教师安排完成新的乘加方程，代回核对。','requestKey':uuid.uuid4().hex});assert attempt['correct'];sup=next(x for x in call(t,'GET','/teaching/tasks/'+feedback['taskId']+'/supplements') if x['id']==feedback['checks'][1]['supplementId']);assert sup['recipients'][0]['outcome']['newAttempts']>=1;assert sup['recipients'][0]['outcome']['independentPassed'];r.update(passed=True,job=j,seconds=round(time.monotonic()-started,3),actualEquation=equation,actualAnswer=attempt['answer'],supplement=sup);(out/'search-intervention.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print('5 course retrieval queries + fresh verified intervention evidence PASS')
