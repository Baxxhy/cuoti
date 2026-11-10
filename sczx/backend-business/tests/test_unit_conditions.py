import unittest
from sczx_business.math_conditions import inspect_conditions,require_conditions
from sczx_business.unit_content import unit_bundle
from sczx_business.math_tools import solve_text_equation,compare_equivalence
from sczx_business.curriculum import assess_question
from sczx_business.model_provider import ModelError
class UnitMathTests(unittest.TestCase):
 def test_fourteen_math_condition_scenarios(self):
  cases=[('同加相同的数后两边相等。',False),('同减相同的数后两边相等。',False),('两边同乘0后仍相等，但丢失原方程信息，不能恢复原解。',False),('两边可以除以同一个数。',True),('两边除以非零数c。',False),('两边同时除以3，得到未知数。',False),('两边可以除以0。',True),('不能除以0。',False),('同乘0是等价变形。',True),('同乘0不会丢失原方程信息。',True),('移项是两边共同加减。',False),('去括号时每一项都要乘括号外的数。',False),('常数分母非零，两边每一项同乘非零公倍数。',False),('应用题条件不足，先补充条件再列式。',False)]
  for text,blocked in cases:
   with self.subTest(text=text):self.assertEqual(bool(inspect_conditions(text)['issues']),blocked)
 def test_observed_combined_division_rule_is_blocked_even_with_no_claims(self):
  with self.assertRaises(ModelError):require_conditions({'steps':['两边同时加上、减去、乘上或除以同一个数。'],'mathClaims':[]})
 def test_all_thirty_reference_answers_and_prose_conditions(self):
  for row in unit_bundle()['lessons']:
   self.assertFalse(inspect_conditions(row['data'])['issues'])
   for q in row['data']['questions']:
    solved,valid=solve_text_equation(q['equation']);self.assertTrue(valid,q);self.assertTrue(compare_equivalence(solved.split('=',1)[1],q['answer'])[0],q)
 def test_word_modeling_is_not_auto_correct_from_numeric_match(self):
  q=unit_bundle()['lessons'][3]['data']['questions'][0];correct=assess_question('5',q);self.assertEqual(correct['status'],'unverified');self.assertFalse(correct['correct']);self.assertTrue(correct['numericVerification']['correct']);self.assertEqual(assess_question('2',q)['status'],'inconsistent')
 def test_no_unique_solution_domain_and_substitution(self):
  for eq in ['0x=0','0x=1','x/x=1','x/0=3']:
   with self.subTest(eq=eq):self.assertFalse(solve_text_equation(eq)[1])
  for eq,answer in [('2(x-3)+4=10','6'),('(x+2)/4-(x-1)/6=1','4'),('-2x+5=13','-4')]:self.assertTrue(compare_equivalence(solve_text_equation(eq)[0].split('=')[1],answer)[0])

 def test_installer_rejects_changed_review_digest_before_any_write(self):
  import importlib.util
  from pathlib import Path
  path=Path(__file__).resolve().parents[2]/'scripts/install_unit_content.py'
  spec=importlib.util.spec_from_file_location('unit_installer',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with self.assertRaisesRegex(RuntimeError,'人工复核版本不一致'):
   module.install(object(),unit_bundle(),{'answer':'已阅读，认可五课与条件预期','contentFile':'docs/planning/第十六步单元内容草案_20261111_v1.json','sha256':'changed'})
