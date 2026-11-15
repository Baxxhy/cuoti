"""Run integrity, descriptive grouping, and human-review completion audit. No automatic pedagogy scores."""
import json,collections,hashlib
from pathlib import Path

def summarize(folder):
 folder=Path(folder);data=json.loads((folder/'summary.json').read_text());run=json.loads((folder/'run.json').read_text());scenarios=json.loads((folder.parents[1]/'scenarios/v1.json').read_text())['scenarios'];meta={s['scenario_id']:s for s in scenarios};groups={}
 for axis in ['subject','category','history_type']:
  values=collections.defaultdict(lambda:collections.Counter())
  for r in data['by_scenario']:
   s=meta[r['scenario_id']];label=s.get(axis) if axis!='history_type' else ('has_history' if s['history'] else 'no_history');values[label][r['group']+':scheduled']+=1;values[label][r['group']+':'+r['status']]+=1
  groups[axis]={k:dict(v) for k,v in values.items()}
 result={'descriptive_groups':groups,'denominator':run['expectedTrials'],'human_metrics':'待至少两名合格评阅者独立评分；缺失不按0分处理','independent_question_performance':None,'real_student_participants':0,'inference':'工程验证不能证明C优于A/B，不能估计课堂效果或统计显著性'}
 (folder/'descriptive-statistics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':
 import sys;summarize(sys.argv[1])
