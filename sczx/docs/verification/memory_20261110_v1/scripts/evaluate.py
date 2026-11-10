import sys,json,copy
from pathlib import Path
sys.path[:0]=['backend-business','backend-business/tests']
from test_learning_memory import CASES,CLOCK
from sczx_business.learning_memory import calculate
rows=[]
for ident,events,expected in CASES:
 last=events[-1] if events else None
 b0='none' if not last else 'independent' if last['verification']=='verified_correct' else 'strengthen' if last['verification']=='verified_incorrect' else 'insufficient'
 correct=sum(e['verification']=='verified_correct' for e in events);wrong=sum(e['verification']=='verified_incorrect' for e in events)
 b1='none' if not events else 'independent' if correct>=2 else 'strengthen' if wrong>=2 else 'insufficient'
 b2=calculate(copy.deepcopy(events),clock=CLOCK)
 rows.append({'id':ident,'facts':events,'expected':expected,'B0':b0,'B1':b1,'B2':b2,'matches':{'B0':b0==expected,'B1':b1==expected,'B2':b2['status']==expected}})
out=Path('/tmp/sczx-step14');(out/'rule-comparison.json').write_text(json.dumps({'clock':CLOCK.isoformat()+'Z','dataset':'14个规则情境，AI拟稿、用户预期复核另记','baselines':{'B0':'只看最近一次核验，不区分帮助','B1':'聚合正确/错误次数，不用帮助/复测/时间','B2':'本次证据规则'},'rows':rows,'matches':{b:sum(r['matches'][b] for r in rows) for b in ['B0','B1','B2']},'scope':'规则一致性比较，不是教育有效性或学习成绩评价'},ensure_ascii=False,indent=2));assert all(r['matches']['B2'] for r in rows);print('Fixed rule comparison:',{b:sum(r['matches'][b] for r in rows) for b in ['B0','B1','B2']})
