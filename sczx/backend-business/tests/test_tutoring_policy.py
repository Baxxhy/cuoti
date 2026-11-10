"""Actual answers, rather than client completion flags, gate task submission."""
import unittest
from types import SimpleNamespace
from sczx_business.curriculum import completion_missing
class PracticeCompletionTests(unittest.TestCase):
    def test_fake_practice_and_check_marks_cannot_replace_answers(self):
        task=SimpleNamespace(snapshot={'lessonSnapshot':{'versionId':'fixed'},'blocks':[{'id':'practice','type':'practice','title':'随堂练习','required':True,'questionIds':['p']},{'id':'check','type':'check','title':'独立检查','required':True,'questionIds':['c']}]},questions=[{'id':'p'},{'id':'c'}])
        rec=SimpleNamespace(drafts={'blocks':{'practice':{'completed':True},'check':{'completed':True}}})
        self.assertEqual(completion_missing(task,rec,[]),['随堂练习','独立检查'])
        self.assertEqual(completion_missing(task,rec,[SimpleNamespace(question=0)]),['独立检查'])
        self.assertEqual(completion_missing(task,rec,[SimpleNamespace(question=0),SimpleNamespace(question=1)]),[])
    def test_oversized_sources_are_bounded_without_mutating_original_evidence(self):
        import copy,json
        from sczx_business.tutoring import model_input
        value={'guidance':True,'strategy':'hint','prompt':'原始问题','question':0,'blockId':'b','recognizedText':'核对后的完整文字','context':{'question':{'equation':'3z=18'},'block':{'content':'原始材料'*15000},'teachingCases':[{'versionId':'v1','content':'案例原文'*12000,'references':[{'unitId':'u','quote':'真实引用'*10000}]}]},'history':[{'student':'学生回应'*5000,'hint':'旧提示'*5000,'question':'追问'} for _ in range(4)],'_validation':{'answer':'6'}}
        original=copy.deepcopy(value);request=model_input(value)
        self.assertLessEqual(len(json.dumps(request,ensure_ascii=False)),24000);self.assertEqual(request['recognizedText'],value['recognizedText']);self.assertEqual(request['context']['question']['equation'],'3z=18');self.assertNotIn('_validation',request);self.assertEqual(value,original)
