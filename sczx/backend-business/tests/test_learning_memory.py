import unittest,copy
from datetime import datetime,timedelta
from sczx_business.learning_memory import calculate,rules
CLOCK=datetime(2026,11,10,12)
def fact(index,outcome='independent_correct',days=0,question=None):
 correct=outcome in ('independent_correct','helped_correct','retest_passed');unknown=outcome in ('unverified','legacy_repair','teacher_confirmation')
 return {'evidenceId':'e'+str(index),'sourceId':str(index),'sourceType':'repair' if outcome in ('retest_passed','retest_failed','legacy_repair') else 'teacher_confirmation' if outcome=='teacher_confirmation' else 'attempt','questionKey':question or str(index),'outcome':outcome,'verification':'unverified' if unknown else 'verified_correct' if correct else 'verified_incorrect','helped':outcome.startswith('helped_'),'occurredAt':(CLOCK-timedelta(days=days,minutes=20-index)).isoformat()+'Z'}
CASES=[('C01',[], 'none'),('C02',[fact(1)],'insufficient'),('C03',[fact(1,'independent_incorrect')],'insufficient'),('C04',[fact(1,'helped_correct')],'insufficient'),('C05',[fact(1,'independent_incorrect'),fact(2,'independent_incorrect')],'strengthen'),('C06',[fact(1,'independent_incorrect'),fact(2,'retest_passed')],'improving'),('C07',[fact(1,'independent_incorrect'),fact(2,'retest_failed')],'strengthen'),('C08',[fact(1,'unverified')],'insufficient'),('C09',[fact(1,'teacher_confirmation')],'insufficient'),('C10',[fact(1,'legacy_repair')],'insufficient'),('C11',[fact(1),fact(2)],'independent'),('C12',[fact(1,days=8),fact(2,days=8)],'review_due'),('C13',[fact(1),fact(2,'independent_incorrect'),fact(3)],'improving'),('C14',[fact(1,'helped_correct'),fact(2,'helped_correct')],'insufficient')]
class MemoryRuleTests(unittest.TestCase):
 def test_fixed_scenarios(self):
  for ident,events,expected in CASES:
   with self.subTest(case=ident):self.assertEqual(calculate(events,clock=CLOCK)['status'],expected)
 def test_distinct_questions_and_configured_time(self):
  events=[fact(1,question='same'),fact(2,question='same')];self.assertEqual(calculate(events,clock=CLOCK)['status'],'insufficient')
  config={**rules(),'reviewDays':10};self.assertEqual(calculate([fact(1,days=8),fact(2,days=8)],config,CLOCK)['status'],'independent')
  unknown=[fact(1,days=8),fact(2,days=8)]
  for e in unknown:e['timeReliable']=False
  self.assertEqual(calculate(unknown,clock=CLOCK)['status'],'independent')
 def test_does_not_mutate_sources(self):
  before=copy.deepcopy(CASES);[calculate(e,clock=CLOCK) for _,e,_ in CASES];self.assertEqual(before,CASES)

 def test_same_timestamp_conflict_does_not_invent_progress(self):
  a=fact(1);b=fact(2,'independent_incorrect');b['occurredAt']=a['occurredAt'];self.assertEqual(calculate([a,b],clock=CLOCK)['status'],'insufficient')
