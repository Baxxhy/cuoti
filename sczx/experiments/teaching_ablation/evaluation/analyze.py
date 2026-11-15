import json,hashlib,csv,statistics
from pathlib import Path

def analyze(folder,scenarios):
 run=json.loads((folder/'run.json').read_text());rows=[];mapping={};blind=[]
 for key in run['schedule']:
  p=folder/'trials'/key;result=json.loads((p/'result.json').read_text()) if (p/'result.json').exists() else {'status':'interrupted','latency_seconds':None};sid,g,rep=key.split('-');bid=hashlib.sha256((folder.name+':'+key).encode()).hexdigest()[:16];mapping[bid]={'scenario_id':sid,'group':g,'replicate':rep}
  rows.append({'trial':key,'scenario_id':sid,'group':g,**result});s=next(s for s in scenarios if s['scenario_id']==sid)
  blind.append({'blind_id':bid,'context':{k:s[k] for k in ('subject','grade','question','original_answer','difficulty','known_evidence','history','public_knowledge','independent_question','independent_rubric','expected_strategy','strategy_rationale','forbidden')},'status':result['status'],'response':result.get('output')})
 summary={}
 for g in 'ABC':
  group=[r for r in rows if r['group']==g];times=[r['latency_seconds'] for r in group if r['latency_seconds'] is not None];summary[g]={'scheduled':len(group),'succeeded':sum(r['status']=='succeeded' for r in group),'failed_or_missing':sum(r['status']!='succeeded' for r in group),'mean_latency_seconds':statistics.mean(times) if times else None,'model_strategy_choices':{k:sum((r.get('output') or {}).get('strategy')==k for r in group) for k in ['hint','example','foundation','rephrase','try']},'failure_rate':sum(r['status']!='succeeded' for r in group)/len(group) if group else None,'strategy_appropriateness':None,'difficulty_accuracy':None,'content_error_rate':None,'citation_correctness':None,'differentiation_success':None,'independent_performance':None,'cost':None,'review_status':'pending two qualified independent reviewers'}
 pairs=[]
 for sid in {s['scenario_id']:s for s in scenarios}:
  s=next(x for x in scenarios if x['scenario_id']==sid)
  if s.get('pair_id'):
   for g in 'ABC':
    for rep in range(run['config']['pilot_replicates'] if run['pilot'] else run['config']['replicates']):
     ids=[hashlib.sha256((folder.name+':'+key).encode()).hexdigest()[:16] for key in [f"{s['pair_id']}-{g}-{rep}",f"{sid}-{g}-{rep}"]]
     if all(i in mapping for i in ids):pairs.append({'pair_id':hashlib.sha256(str(ids).encode()).hexdigest()[:12],'blind_ids':ids})
 (folder/'blind-pairs.json').write_text(json.dumps(pairs,indent=2))
 # Derived artifacts may be regenerated; source inputs/results are never overwritten.
 for name,value in [('summary.json',{'groups':summary,'denominator':run['expectedTrials'],'human_rated':0,'by_scenario':rows}),('blind-packet.json',sorted(blind,key=lambda b:b['blind_id'])),('unblinding-key.json',mapping)]: (folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
 fields=['blind_id','reviewer_id','subject_qualification','difficulty_identification','strategy_0_1_2','content_correctness','citation_quality','differentiation','independent_score','evidence_quote','reason']
 for reviewer in ['reviewer1','reviewer2']:
  path=folder/(reviewer+'.csv')
  if not path.exists():
   with path.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({'blind_id':b['blind_id']} for b in blind)
