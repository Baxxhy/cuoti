import asyncio,json,uuid,time
from pathlib import Path
import httpx
fx=json.loads(Path('/tmp/sczx-step13/browser-private.json').read_text());out=Path('/tmp/sczx-step13');rows=[]
async def main():
 async with httpx.AsyncClient(base_url='http://127.0.0.1:8013',timeout=30) as c:
  await c.post('/api/auth/login',json={'username':'teaching-s0','password':fx['password']})
  async def job(w,mode,**data):
   r=await c.post('/api/ai/jobs',json={'capability':'text','recordId':w['recordId'],'requestKey':uuid.uuid4().hex,'data':{'wrongId':w['id'],'mode':mode,**data}});r.raise_for_status();jid=r.json()['id']
   for _ in range(600):
    j=(await c.get('/api/ai/jobs/'+jid)).json()
    if j['status'] in ['succeeded','failed','cancelled']:break
    await asyncio.sleep(.5)
   return j
  cases=[('E01','x-3=5','2','我把右边5减去3'),('E02','3x=18','15','我把18减去3'),('E03','x/4=3','3/4','两边都除以4'),('E04','2(x-1)=10','4','先减去1再除以2'),('E05','为什么除数不能为零','','不知道乘法与除法的关系'),('E06','不同的数乘零为什么丢失信息','','我觉得还可以除以零恢复'),('E09','已知x+y=3，求x','','条件是不是不够')]
  for ident,prompt,answer,reason in cases:
   r=await c.post('/api/wrongs',json={'prompt':prompt,'equation':prompt,'answer':answer,'reason':reason,'requestKey':uuid.uuid4().hex,'knowledgeIds':['browser-kp']});r.raise_for_status();w=r.json();row={'id':ident,'wrong':w,'analysis':await job(w,'analysis')};rows.append(row);(out/'real-cases.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(ident,'analysis',row['analysis']['status'],flush=True)
   if ident in ['E01','E02','E03','E04','E09']:
    row['variant']=await job(w,'variant');print(ident,'variant',row['variant']['status'],flush=True)
    if row['variant']['status']=='succeeded':
     from sys import path
     path.insert(0,'backend-business');from sczx_business.math_tools import solve_text_equation
     equation=row['variant']['result']['variant']['equation'];solved,known=solve_text_equation(equation)
     row['attempt']=(await c.post('/api/wrongs/'+w['id']+'/attempts',json={'variantJobId':row['variant']['id'],'answer':solved.split('=',1)[1],'reason':'隔离验收输入；参考答案由程序求解','requestKey':uuid.uuid4().hex})).json()
   if ident=='E01':
    row['followup']=await job(w,'guidance',strategy='continue',prompt='我还是不明白，为什么减3后还要加回去？',parentJobId=row['analysis']['id']);print('E01 followup',row['followup']['status'],flush=True)
   (out/'real-cases.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
asyncio.run(main())
