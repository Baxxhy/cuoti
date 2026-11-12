import copy,unittest
from types import SimpleNamespace
from sczx_business.education import catalog,question_errors,assess_general,linear_context
from sczx_business.subject_prompts import instruction
from sczx_business.curriculum import content_errors,student_content,assess_question
from sczx_business.remediation import validate

class MultiSubjectTests(unittest.TestCase):
 def test_catalog_supports_both_stages_and_common_subjects(self):
  data=catalog();self.assertEqual(data['stages'][1]['grades'],['高一','高二','高三']);self.assertTrue({'语文','英语','物理','化学','生物学','历史','地理','思想政治','信息技术'}<={s['value'] for s in data['subjects']})
 def test_subject_prompt_never_injects_equation_rules_into_other_subjects(self):
  for subject in [s['value'] for s in catalog()['subjects'] if s['value']!='数学']+['自定义学科']:
   prompt=instruction({'guidance':True,'context':{'lesson':{'subject':subject,'grade':'高一'},'question':{'prompt':'分析材料','equation':''}}});self.assertIn(subject,prompt);self.assertNotIn('同乘0会丢失',prompt);self.assertNotIn('请写下两边共同',prompt)
 def test_linear_addon_is_scoped_by_actual_subject_and_equation(self):
  data={'context':{'lesson':{'subject':'数学','grade':'七年级'},'question':{'equation':'2x+3=11'}}};self.assertTrue(linear_context(data));self.assertIn('同乘0会丢失',instruction(data));data['context']['lesson']['subject']='物理';self.assertFalse(linear_context(data));self.assertNotIn('同乘0会丢失',instruction(data))
 def test_subjective_answers_are_not_programmatically_marked_wrong(self):
  for answer in ['有证据的不同表达','2','print(1)']:
   value=assess_question(answer,{'prompt':'解释材料','answer':'参考要点','responseType':'essay','gradingMode':'manual'});self.assertEqual(value['status'],'unverified');self.assertFalse(value['correct'])
 def test_objective_choice_multiple_and_judgement(self):
  self.assertTrue(assess_general('B',{'responseType':'single_choice','answer':'B'})['correct']);self.assertFalse(assess_general('A',{'responseType':'single_choice','answer':'B'})['correct']);self.assertTrue(assess_general('C,A',{'responseType':'multiple_choice','answer':'A,C'})['correct']);self.assertFalse(assess_general('A',{'responseType':'multiple_choice','answer':'A,C'})['correct']);self.assertTrue(assess_general('true',{'responseType':'true_false','answer':'正确'})['correct'])
 def test_text_matching_is_explicit_and_can_preserve_case_rules(self):
  self.assertFalse(assess_general('paris',{'gradingMode':'exact','answer':'Paris'})['correct']);self.assertTrue(assess_general('paris',{'gradingMode':'exact','answer':'Paris','caseSensitive':False})['correct'])
 def test_choice_references_must_belong_to_actual_options(self):
  q={'prompt':'选择','answer':'C','responseType':'single_choice','options':[{'id':'A','text':'甲'},{'id':'B','text':'乙'}]};self.assertTrue(question_errors(q));q['answer']='B';self.assertFalse(question_errors(q))
 def test_non_equation_lesson_can_be_published_without_math(self):
  db=SimpleNamespace(scalars=lambda *_:SimpleNamespace(all=lambda:[]));q={'id':'reading','kind':'check','prompt':'用原文支持观点','answer':'指出文本证据并解释','responseType':'reading','gradingMode':'manual'};lesson={'title':'阅读与证据','goal':'用材料说明观点','grade':'高一','subject':'语文','source':'自编测试材料','duration':30,'blocks':[{'id':'intro','type':'explanation','title':'阅读','content':'一段自编材料。'},{'id':'check','type':'check','title':'独立练习','content':'引用材料作答。','questionIds':['reading']}],'questions':[q]};self.assertEqual(content_errors(db,lesson),[])
 def test_student_view_preserves_options_but_not_reference_answers(self):
  source={'questions':[{'answer':'B','acceptedAnswers':['B'],'rubric':'评分依据','responseType':'single_choice','options':[{'id':'B','text':'正文','isCorrect':True}]}]};old=copy.deepcopy(source);student=student_content(source);self.assertNotIn('answer',student['questions'][0]);self.assertNotIn('rubric',student['questions'][0]);self.assertNotIn('isCorrect',student['questions'][0]['options'][0]);self.assertEqual(source,old)
 def test_general_variant_is_submittable_without_false_automatic_verification(self):
  value=validate({'variant':{'prompt':'换一段材料说明人物变化','expected':'结合材料陈述依据','rationale':'保持证据说明目标','equation':'','responseType':'reading','gradingMode':'manual','options':[],'rubric':''},'mathClaims':[]},{'mode':'variant','context':{'subject':'语文','grade':'高一','question':{'prompt':'原来的阅读题','equation':''}}});self.assertTrue(value['variantVerification']['submissionAllowed']);self.assertEqual(value['variantVerification']['status'],'unverified')
 def test_non_linear_mathematics_can_use_teacher_review(self):
  self.assertEqual(assess_question('分类讨论见解答',{'equation':'x^2=4','answer':'2或-2','gradingMode':'manual','responseType':'proof'})['status'],'unverified');self.assertTrue(assess_question('4',{'equation':'x+1=5','answer':'4'})['correct'])

 def test_model_options_and_response_types_have_strict_schema(self):
  from sczx_business.remediation import VariantResult
  from sczx_business.exam_schemas import ExamCandidate
  from sczx_business.codex_provider import strict_schema
  from pydantic import ValidationError
  for model in (VariantResult,ExamCandidate):
   schema=strict_schema(model.model_json_schema());self.assertEqual(set(schema['$defs']['ChoiceOption']['properties']),{'id','text'});self.assertIn('reading',schema['$defs'].get('Variant',schema)['properties']['responseType']['enum'])
  with self.assertRaises(ValidationError):VariantResult.model_validate({'variant':{'prompt':'材料题','expected':'要点','rationale':'同一目标','responseType':'阅读理解'}})
 def test_tutoring_options_do_not_carry_reference_flags(self):
  from sczx_business.tutoring import public_fields,PUBLIC_QUESTION
  value=public_fields({'options':[{'id':'A','text':'甲','correct':True}]},PUBLIC_QUESTION);self.assertEqual(value['options'],[{'id':'A','text':'甲'}])

 def test_student_paper_keeps_choice_text_without_reference_flags(self):
  from sczx_business.exams import student_paper
  paper={'title':'英语试卷','total':10,'entries':[{'versionId':'v1','points':10,'question':{'prompt':'选择复数','options':[{'id':'A','text':'books','correct':True}],'answer':'A','responseType':'single_choice'}}]};result=student_paper(paper)['entries'][0]['question'];self.assertEqual(result['options'],[{'id':'A','text':'books'}]);self.assertNotIn('answer',result)
