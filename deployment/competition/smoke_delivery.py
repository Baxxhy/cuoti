"""Run against the dedicated delivery container only; never a student's database."""
import json,sys,time,uuid,urllib.request,urllib.error
from pathlib import Path
base=sys.argv[1];out=Path(sys.argv[2]);records=[]
def req(method,path,payload=None,token=None):
 h={'Content-Type':'application/json'}
 if token:h['Authorization']='Bearer '+token
 r=urllib.request.urlopen(urllib.request.Request(base+path,method=method,headers=h,data=None if payload is None else json.dumps(payload).encode()),timeout=300)
 body=json.load(r)
 assert body.get('success'),(path,body.get('error'))
 return body['data']
def passed(name):records.append({'check':name,'result':'passed'});out.write_text(json.dumps(records,ensure_ascii=False,indent=2));print(name+': passed',flush=True)
assert urllib.request.urlopen(base).status==200
assert json.load(urllib.request.urlopen(base+'/readyz'))['status']=='database_ready'
passed('前端页面与数据库就绪')
email='delivery-'+uuid.uuid4().hex[:10]+'@example.test';pw='Delivery-Test-2026!'
u=req('POST','/api/v1/auth/register',{'email':email,'password':pw,'name':'交付验收学生','grade':'初一'});t=u['access_token'];passed('学生注册')
v=req('POST','/api/v1/auth/login',{'email':email,'password':pw});assert v['id']==u['id'];passed('重新登录')
q=req('POST','/api/v1/questions/manual',{'subject':'数学','question_text':'解方程：3x+2=17','student_answer':'19/3','student_steps':['3x=17+2','x=19/3']},t)
qid=q['id'];detail=req('GET','/api/v1/questions/'+qid,token=t);passed('手动录题与查询')
bank=req('GET','/api/v1/study-bank',token=t);assert bank['total']==24;passed('独立演示题库24题')
for mode in ('practice','exam'):
 s=req('POST','/api/v1/study-sessions',{'mode':mode,'subject':'数学','count':3,'minutes':10},t)
 path='/api/v1/study-sessions/'+s['id']
 saved=req('PATCH',path,{'version':s['version'],'answers':[{'id':i['id'],'answer':['A']} for i in s['items']]},t)
 result=req('POST',path+'/submit',{'version':saved['version']},t)
 assert result['status']=='submitted' and result['results']['correct']==3,result.get('results')
 same=req('POST',path+'/submit',{'version':saved['version']},t);assert same['results']==result['results']
 passed(('题库练习' if mode=='practice' else '模拟考试')+'保存交卷及重复提交')
for path in ['/api/v1/knowledge/cards','/api/v1/dashboard','/api/v1/reviews/today','/api/v1/analytics/overview']:
 req('GET',path,token=t)
passed('知识首页复习与报告接口')
# Only the separate test working directory receives this credential for restart checks.
state=out.with_suffix('.private.json');state.write_text(json.dumps({'email':email,'password':pw,'qid':qid}));state.chmod(0o600)
if '--ai' in sys.argv:
 a=req('POST','/api/v1/questions/'+qid+'/analyze',token=t)
 passed('真实AI题目分析并保存')
 d=req('POST','/api/v1/questions/'+qid+'/diagnose',token=t)
 passed('真实AI错因诊断并保存')
print('验收记录已写入',flush=True)
