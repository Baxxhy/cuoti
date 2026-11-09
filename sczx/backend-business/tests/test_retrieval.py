import json,unittest
from pathlib import Path
from sczx_business.retrieval import retrieve,student_request,normalize_grade

class RetrievalRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.fixture=json.loads((Path(__file__).parent/'fixtures/retrieval_step8.json').read_text())
    def test_frozen_baseline_and_context_orders(self):
        f=self.fixture
        for variant in ['B0','B1','B2','B3']:
            for q in f['queries']:
                with self.subTest(variant=variant,query=q['id']):
                    actual=retrieve({'query':q['query'],'context':q['context'],'limit':20},f['corpus'],f['knowledge'],variant)
                    self.assertEqual([(d['id'],d['score']) for d in actual['items']],[tuple(x) for x in f['expected'][variant][q['id']]])
    def test_one_hop_toggle_and_wrong_topic(self):
        points=[{'id':'a','name':'等式性质','aliases':['两边同变'],'prerequisites':['b']},{'id':'b','name':'相等关系','prerequisites':['c']},{'id':'c','name':'数的概念','prerequisites':[]}]
        docs=[{'id':i,'title':'例子','content':'例子','knowledgeIds':[i]} for i in ['a','b','c']]
        self.assertEqual({x['id'] for x in retrieve({'query':'两边同变'},docs,points)['items']},{'a','b'})
        self.assertEqual([x['id'] for x in retrieve({'query':'两边同变','includePrerequisites':False},docs,points)['items']],['a'])
        self.assertEqual(retrieve({'query':'平面几何三角形','context':{'knowledgeIds':['a'],'grade':'七年级'}},docs,points)['items'],[])
        self.assertTrue(retrieve({'query':'为什么要这样做','context':{'knowledgeIds':['a']}},docs,points)['items'])
        self.assertEqual(retrieve({'filters':{'grade':'七年级'}},docs,points)['items'],[])
    def test_empty_long_context_and_invalid_grade(self):
        self.assertEqual(retrieve({},[])['items'],[])
        self.assertEqual(normalize_grade('99年级'),'')
        self.assertEqual(normalize_grade('初一'),'7')
        request=student_request({'goal':'学'*4000},{'prompt':'题'*5000},'观'*7000,'问'*12000,'识'*20000)
        self.assertEqual(len(request['query']),2000)
        self.assertEqual(retrieve(request,[])['items'],[])

if __name__=='__main__':unittest.main()
