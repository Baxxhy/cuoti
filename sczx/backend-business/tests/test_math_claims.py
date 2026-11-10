import unittest
from sczx_business.model_jobs import math_check
class MathClaimTests(unittest.TestCase):
    def test_expressions_equations_conditions_and_errors_are_distinct(self):
        check=lambda a,b:math_check([{'left':a,'right':b}])['status']
        self.assertEqual(check('x+1-1','x'),'verified')
        self.assertEqual(check('x-3=5','x=8'),'verified')
        self.assertEqual(check('x-3=5','x=9'),'inconsistent')
        self.assertEqual(check('a=b 且 c≠0','a/c=b/c'),'unverified')
        self.assertEqual(check('a=b','ac=bc'),'unverified')
        self.assertEqual(check('1','2'),'inconsistent')
