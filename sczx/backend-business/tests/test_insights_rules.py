import unittest,copy
from sczx_business.insights import metrics,latest_attempts,period,within
class InsightRulesTests(unittest.TestCase):
 def event(self,ident,**kw):return {'eventId':ident,'studentId':'s','taskId':'t','sourceType':'attempt','questionIndex':2,'questionKind':'check','occurredAt':'2020-11-11T08:00:00Z','verification':'verified_correct','helped':False,'timeReliable':True,**kw}
 def test_unique_key_includes_student_task_published_question(self):
  e=self.event('1');rows=[e,{**e,'eventId':'2','occurredAt':'2020-11-11T08:01:00Z'},{**e,'eventId':'3','studentId':'s2'},{**e,'eventId':'4','taskId':'t2'},{**e,'eventId':'5','questionIndex':3}];s=metrics(rows);self.assertEqual(s['attempts'],5);self.assertEqual(s['answeredQuestions'],4);self.assertEqual(s['independentCorrectStudents'],2)
 def test_tied_contradictory_results_not_arbitrary_success(self):
  rows=[self.event('a'),self.event('b',verification='verified_incorrect')];before=copy.deepcopy(rows);self.assertEqual(metrics(rows)['independentCorrectQuestions'],0);self.assertEqual(metrics(rows)['unverifiedQuestions'],1);self.assertEqual(rows,before)
 def test_latest_helped_or_unknown_not_earlier_independent_success(self):
  a=self.event('a');b=self.event('b',helped=True,occurredAt='2020-11-11T09:00:00Z');self.assertEqual(metrics([a,b])['independentCorrectQuestions'],0);b['helped']=False;b['verification']='unverified';self.assertEqual(metrics([a,b])['independentCorrectQuestions'],0)
 def test_practice_does_not_inflate_check_and_replacement_is_check(self):
  self.assertEqual(metrics([self.event('a',questionKind='practice')])['independentQuestions'],0);self.assertEqual(metrics([self.event('a',questionKind='replacement')])['independentQuestions'],1)
 def test_utc_closed_open_range_and_unknown_exclusion(self):
  lo,hi=period('2020-11-11','2020-11-11');self.assertTrue(within(self.event('a',occurredAt='2020-11-10T16:00:00Z'),lo,hi));self.assertFalse(within(self.event('a',occurredAt='2020-11-11T16:00:00Z'),lo,hi));self.assertFalse(within(self.event('a',timeReliable=False),lo,hi));self.assertTrue(within(self.event('a',timeReliable=False),None,None))
