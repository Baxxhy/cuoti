import unittest
from pydantic import ValidationError
from sczx_business.knowledge_validation import KnowledgeCatalogInput, validate_catalog

class KnowledgeValidationTests(unittest.TestCase):
    def check(self,points):
        parsed=KnowledgeCatalogInput.model_validate({'points':points})
        validate_catalog([p.model_dump() for p in parsed.points])
    def test_invalid_types_never_reach_sets_or_orm(self):
        for key,values in {'id':[[],{},1,True,None,'x'*41],'name':[[],{},1,False,None],'aliases':[None,{},'alias',[[]],[{}],[1]],'prerequisites':[None,{},'prior',[[]],[{}],[1],[True]]}.items():
            for value in values:
                with self.subTest(key=key,value=value),self.assertRaises(ValidationError):
                    self.check([{'id':'a','name':'相等',key:value}])
    def test_conflicts_missing_edges_and_cycles(self):
        for points in [
            [{'id':'a','name':'相等'},{'id':'a','name':'运算'}],
            [{'id':'a','name':'相等'},{'id':'b','name':'相等'}],
            [{'id':'a','name':'相等','aliases':['共同变化','共同变化']}],
            [{'id':'a','name':'相等','aliases':['运算']},{'id':'b','name':'运算'}],
            [{'id':'a','name':'相等','prerequisites':['missing']}],
            [{'id':'a','name':'相等','prerequisites':['b']},{'id':'b','name':'运算','prerequisites':['a']}],
        ]:
            with self.subTest(points=points),self.assertRaises(ValueError):self.check(points)
    def test_valid_missing_optional_fields_and_unicode_collisions(self):
        self.check([{'id':'a','name':'相等'},{'id':'b','name':'运算','aliases':['共同变化'],'prerequisites':['a']}])
        with self.assertRaises(ValueError):self.check([{'id':'a','name':'Ａ'},{'id':'b','name':'a'}])

if __name__=='__main__':unittest.main()
