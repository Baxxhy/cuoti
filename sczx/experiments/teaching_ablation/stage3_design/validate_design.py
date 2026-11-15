"""Design-only checks. Does not implement or invoke the proposed Evaluator."""
import hashlib,json
from pathlib import Path
BASE=Path(__file__).resolve().parent;REPO=BASE.parents[2]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 c=json.loads((BASE/'contracts.json').read_text());checks={}
 checks['four_groups']=set(c['groups'])==set('ABCD')
 checks['information_matched_C_D']=all(c['groups'][g]['history'] and c['groups'][g]['retrieval'] for g in 'CD') and c['groups']['C']['policy'] and not c['groups']['D']['policy']
 checks['blind_field_sets_disjoint']=not set(c['evaluator_allowlist'])&set(c['evaluator_forbidden'])
 checks['no_actual_experiment_budget']=not c['execution_enabled'] and c['runtime']['generation_budget_this_phase']==0 and c['runtime']['evaluation_budget_this_phase']==0
 checks['independent_evaluator_not_fabricated']=c['runtime']['evaluator_model'] is None and c['runtime']['evaluator_status']=='unconfigured'
 checks['future_schedule_count']=c['runtime']['future_generation_trials']==16*4*3
 checks['reliability_categories']=set(['known_correct','known_wrong','insufficient_evidence','wrong_citation','cross_grade','wrong_intervention','invalid_history']).issubset(c['tests'])
 protected=json.loads((BASE/'protected-pilots.json').read_text());checks['old_pilot_bytes_preserved']=all((REPO/k).is_file() and digest(REPO/k)==h for k,h in protected.items())
 manifest=json.loads((BASE/'design-freeze.json').read_text());checks['design_freeze']=all((REPO/k).is_file() and digest(REPO/k)==h for k,h in manifest['files'].items())
 result={'scope':'static design-contract checks only; not evaluator reliability or effect validation','date':'2026-11-16','checks':checks,'protected_pilot_files':len(protected),'passed':all(checks.values()),'runtime_evaluator':'not_implemented','llm_evaluation_calls':0,'formal_experiment_calls':0}
 print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
