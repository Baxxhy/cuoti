"""Real Codex comparison on 25 frozen self-authored scenarios; no model grading."""
import os,sys,json,asyncio,copy,time,hashlib
from pathlib import Path
fx=json.loads(Path('/tmp/sczx-step12/browser-private.json').read_text());os.environ['SCZX_DATABASE_URL']=fx['url'];sys.path[:0]=['backend-business']
from sqlalchemy import select
from sczx_business.database import SessionLocal
from sczx_business.models import Account,StudentRecord
from sczx_business.tutoring import prepare,run,model_input,validate_result
from sczx_business.model_provider import ModelProvider
out=Path('/tmp/sczx-step12/evaluation');out.mkdir(exist_ok=True)
scenarios=[]
prompts={
'hint':['只改变等式一边也能相等吗？','3z=18，我不知道先做什么。','x减3为什么不能只在左边加3？','我不确定题意，能先问我需要哪些条件吗？','题图中减号有点模糊，确认后先给我提示。'],
'example':['请用另一道题说明两边同时加相同数。','请换一道乘除的例子，不要直接做这道检查题。','用不同数量说明天平两边一起变化。','我想看另一道逆运算例题，解释与当前题的联系。','用另一道除法例题说明非零条件。'],
'rephrase':['公式我还不懂，请用具体数量讲。','刚才的讲解太抽象，请用天平讲。','我知道要两边一起变，但不知道为什么，请换讲法。','不要重复同一句规则，先让我比较两种做法。','我不明白乘零为什么会丢失信息，请用对比讲。'],
'foundation':['相等是什么意思？先用一个小问题确认我的理解。','我分不清加法的逆运算，先补相关基础。','我忘了为什么不能除以零，先确认我的想法。','我不知道同样的变化指什么，请先用简单数量检查。','我只做错一次，请不要直接判断我没掌握。'],
'try':['我想自己试试，请保留之前帮助记录。','先不展开讲解，我自己写原题答案。','我准备独立完成下一道新题。','让我先解释等式两边共同做什么。','我想返回原题作答，不要继续给步骤。']}
with SessionLocal() as db:
 user=db.get(Account,'teaching-s0');rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id=='browser-t00',StudentRecord.student_id==user.id))
 for strategy,items in prompts.items():
  for index,prompt in enumerate(items):
   q=None if index==2 else [0,2,None,1,3][index];block='eq-balance' if q is None else 'eq-practice' if q<2 else 'eq-check'
   data=prepare(db,user,rec,{'strategy':strategy,'prompt':prompt,'question':q,'blockId':block})
   if strategy=='hint' and index==4:data['recognizedText']='题图经核对的测试文字：3z = 18；仅用于文字情境，真实OCR另做端到端验收。'
   scenarios.append({'id':'q'+str(len(scenarios)+1).zfill(2),'strategy':strategy,'prompt':prompt,'studentResponse':'我仍不明白为什么两边要做同一件事，请先确认相等的含义。' if index%2 else '我试着说明：两边数量原本相同，所以变化也应该相同。','expected':{'related':'围绕当前任务/题目','strategy':strategy,'noDirectOriginalAnswer':True,'noUnsupportedDiagnosis':True,'maxSteps':4,'math':'可核验关系不得错误','source':'只使用冻结公开来源'},'data':data})
(out/'scenarios.json').write_text(json.dumps(scenarios,ensure_ascii=False,indent=2));digest=hashlib.sha256((out/'scenarios.json').read_bytes()).hexdigest()
results=[];provider=ModelProvider();semaphore=asyncio.Semaphore(2)
class Counting:
 def __init__(self):self.calls=[]
 async def call(self,cap,data,**kwargs):
  started=time.perf_counter();entry={'capability':cap,'request':data};self.calls.append(entry)
  try:
   value,model,source=await provider.call(cap,data,**kwargs);entry.update(result=value,model=model,provider=source,elapsedMs=round((time.perf_counter()-started)*1000));return value,model,source
  except Exception as e:entry.update(error=str(e),elapsedMs=round((time.perf_counter()-started)*1000));raise

def save():
 (out/'results.json').write_text(json.dumps({'scenarioSha256':digest,'cases':25,'comparisonRows':len(results),'rows':results,'evaluation':'自动结构/数学/泄露检查，不是人工教学评判或课堂效果'},ensure_ascii=False,indent=2))
async def case(scenario):
 async with semaphore:
  previous=None
  for variant in ['B0','B1','B2','B3']:
   start=time.perf_counter();counter=Counting();data=copy.deepcopy(scenario['data']);data['history']=[]
   if variant in ['B2','B3'] and previous:
    data['history']=[{'student':scenario['prompt'],'strategy':scenario['strategy'],'representation':previous.get('representation','question'),'hint':previous.get('hint','')[:1000],'question':previous.get('question','')[:300]}];data['prompt']=scenario['studentResponse']
   if variant!='B3':data['context']['knowledge']=[];data['context']['prerequisites']=[];data['context']['teachingCases']=[]
   row={'scenario':scenario['id'],'variant':variant,'strategy':scenario['strategy'],'startedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'manualReview':None}
   try:
    if variant=='B0':
     request=model_input(data);request.pop('guidance');request.pop('strategy');request.pop('history');value,model,source=await counter.call('text',request)
     value={**value,'strategy':scenario['strategy'],'representation':'question','nextStrategy':'hint','prerequisiteId':'','usedCaseVersionIds':[]}
     try:validate_result(value,data);row['automaticGate']='pass'
     except Exception as e:row['automaticGate']='blocked: '+str(e)
    else:
     value,model,source=await run(data,counter,scenario['id']+'-'+variant);row['automaticGate']='pass'
    row.update(status='succeeded',result=value,model=model,provider=source)
    if variant=='B1':previous=value
   except Exception as e:row.update(status='failed',error=str(e))
   row.update(elapsedMs=round((time.perf_counter()-start)*1000),modelCalls=len(counter.calls),calls=counter.calls);results.append(row);save();print(scenario['id'],variant,row['status'],row['modelCalls'],flush=True)
async def main():
 try:await asyncio.gather(*(case(s) for s in scenarios))
 finally:await provider.close();save()
asyncio.run(main())
