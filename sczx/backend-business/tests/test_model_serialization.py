import unittest
from datetime import datetime
from sczx_business.models import ModelJob
from sczx_business.ai_routes import serialize
class ModelSerializationTests(unittest.TestCase):
 def test_retrieval_algorithm_variant_string_survives_listing_and_detail(self):
  row=ModelJob(id='retrieval-fixture',owner_id='actor',capability='retrieval',input={},result={'variant':'B4','items':[]},created_at=datetime(2026,11,12),updated_at=datetime(2026,11,12),attempt_number=1,retry_count=0)
  for detail in (False,True):self.assertEqual(serialize(row,detail)['result']['variant'],'B4')
 def test_math_variant_expected_answer_is_redacted_without_mutating_storage(self):
  row=ModelJob(id='wrong-fixture',owner_id='actor',capability='text',input={'mode':'variant'},result={'variant':{'equation':'x+3=8','expected':'5'}},created_at=datetime(2026,11,12),updated_at=datetime(2026,11,12),attempt_number=1,retry_count=0)
  self.assertNotIn('expected',serialize(row)['result']['variant']);self.assertEqual(row.result['variant']['expected'],'5')
 def test_candidate_explanation_has_real_lines_and_keeps_math_escape(self):
  from sczx_business.exams import candidate_explanation
  self.assertEqual(candidate_explanation('两边减5。\\n\\n分步解释：\\n1. 得x=7。\\n本题为待教师审核的候选题。'),'两边减5。\n\n分步解释：\n1. 得x=7。')
  self.assertEqual(candidate_explanation(r'x\neq 0'),r'x\neq 0')
