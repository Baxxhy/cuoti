import unittest
from sczx_business.equality_guidance import numeric_equality_example,validate_equality_explanation
from sczx_business.model_provider import ModelError
class EqualityGuidanceTests(unittest.TestCase):
 def test_explicit_numeric_example_keeps_both_original_sides(self):
  value=numeric_equality_example('为什么等式两边都减去同一个负数仍相等？请用5=5、c=-2说明。')
  self.assertEqual(value['leftExpression'],'(5)-(-2)');self.assertEqual(value['rightExpression'],'(5)-(-2)')
  self.assertIsNone(numeric_equality_example('解3x+5=20，原答x=6。'));self.assertIsNone(numeric_equality_example('两边减c，请用5=6，c=-2说明。'))
 def test_observed_operand_mixup_and_one_sided_question_are_rejected(self):
  example=numeric_equality_example('两边都减去c，请用5=5、c=-2说明')
  with self.assertRaises(ModelError):validate_equality_explanation({'hint':'把5和−2都减去−2，会分别得到什么？','steps':[]},example)
  with self.assertRaises(ModelError):validate_equality_explanation({'steps':['两边都减去−2。'],'question':'5−(−2)和5分别等于多少？'},example)
  validate_equality_explanation({'steps':['左边5−(−2)=7，右边5−(−2)=7。'],'question':'为什么两边都得到7？'},example)
 def test_deliberate_single_side_comparison_is_allowed(self):
  example=numeric_equality_example('两边加c，5=5，c=-2')
  validate_equality_explanation({'hint':'如果只改变一边，试着对比。','question':'5+(-2)和5分别等于多少？'},example)
