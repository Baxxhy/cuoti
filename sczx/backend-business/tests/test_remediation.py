import unittest
from sczx_business.grading import assess_repair
from sczx_business.remediation import validate
from sczx_business.tutoring import need_coverage
from sczx_business.visualization import specification,apply,VisualizationSpec
from sczx_business.model_provider import ModelError
class RemediationTests(unittest.TestCase):
 def test_actual_equation_and_unknown(self):
  for eq,answer in [('x-3=5','8'),('3x=18','6'),('x/4=3','12'),('2(x-1)=10','6')]:
   self.assertEqual(assess_repair(answer,eq)['status'],'verified_correct')
   self.assertEqual(assess_repair('7',eq)['status'],'verified_incorrect')
  self.assertEqual(assess_repair('7')['status'],'unverified')
  self.assertEqual(assess_repair('6','3x=18','7')['status'],'unverified')
  self.assertEqual(assess_repair('2','x+y=3')['status'],'unverified')
 def test_topic_coverage_prevents_known_off_topic(self):
  for prompt in ['请用天平讲','乘零为什么丢失信息，请用对比讲','为什么不能除以零']:
   self.assertTrue(need_coverage(prompt,'两边同时加1，再消去w/4。')['missing'])
  for prompt,text in [('请用天平讲','天平左盘和右盘各放5个砝码，再两边各拿走1个。'),('乘零为什么丢失信息','不同的数乘0都得到0，不能还原原数。'),('为什么不能除以零','除以0要找乘0得到原数的数；非零数时不存在，0时结果不唯一。')]:self.assertFalse(need_coverage(prompt,text)['missing'])
 def test_variant_rejects_wrong_unknown_and_identical(self):
  def data(eq):return {'mode':'variant','context':{'question':{'equation':eq}},'previousEquations':[]}
  def result(eq,answer):return {'variant':{'prompt':'求解','equation':eq,'expected':answer,'rationale':'保留逆运算结构改变数值'},'mathClaims':[]}
  self.assertEqual(validate(result('4x=20','5'),data('3x=18'))['variantVerification']['status'],'verified')
  for r,d in [(result('4x=20','6'),data('3x=18')),(result('3x=18','6'),data('3x=18')),(result('3x=18','6'),data('条件未知')),(result('a-3=5','8'),data('x-3=5')),(result('x/4=3','12'),data('3x=18')),(result('x+3=8','5'),data('3x=18'))]:
   with self.assertRaises(ModelError):validate(r,d)
 def test_visualization_single_both_boundary_and_schema(self):
  spec=specification({'type':'balance','base':5,'step':1,'max':5});state=spec['initial']
  self.assertEqual(apply(spec,state,'left_add'),{'left':6,'right':5})
  self.assertEqual(apply(spec,state,'both_subtract'),{'left':4,'right':4})
  with self.assertRaises(ValueError):apply(spec,{'left':0,'right':0},'left_subtract')
  with self.assertRaises(ValueError):VisualizationSpec.model_validate({**spec,'javascript':'alert(1)'})
  with self.assertRaises(ValueError):specification({'type':'balance','base':True,'step':1,'max':5})
