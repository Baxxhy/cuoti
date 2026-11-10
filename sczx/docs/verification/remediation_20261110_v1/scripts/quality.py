import os,sys,json,asyncio,time,copy
from pathlib import Path
sys.path.insert(0,'backend-business')
from sczx_business.model_provider import ModelProvider
from sczx_business.tutoring import run,need_coverage
out=Path('/tmp/sczx-step13');scenarios=json.loads(Path('docs/verification/tutoring_20261110_v1/evaluation/scenarios.json').read_text());old=json.loads(Path('docs/verification/tutoring_20261110_v1/evaluation/results.json').read_text())
provider=ModelProvider();rows=[]
async def main():
 for ident in ['q12','q15','q18']:
  s=next(x for x in scenarios if x['id']==ident);before=next(x for x in old['rows'] if x['scenario']==ident and x['variant']=='B3');row={'id':ident,'prompt':s['prompt'],'before':before,'startedAt':time.time()}
  try:
   result,model,source=await run(copy.deepcopy(s['data']),provider,'step13-'+ident);row.update(after=result,model=model,provider=source,passed=not result['needCoverage']['missing'],humanReview='pending')
  except Exception as e:row.update(passed=False,error=str(e))
  rows.append(row);(out/'quality.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(ident,row.get('passed'),flush=True)
 await provider.close()
asyncio.run(main())
