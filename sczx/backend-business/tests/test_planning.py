import copy,unittest
from sczx_business.planning_schemas import PlanningInput
from sczx_business.prepare_agent import validate_plan,infer_task,TOOLS,STEPS

class PlanningValidationTests(unittest.TestCase):
    def setUp(self):
        self.lesson={'blocks':[{'id':'intro'},{'id':'example'}]}
        self.evidence=[{'id':'source-1'}]
        self.plan={'title':'等式性质活动','goal':'理解共同运算','rationale':['通过比较和追问发现规则'],'blocks':[{'id':key,'title':'活动','content':'比较等式两边','evidenceIds':['source-1']} for key in ['intro','example']],'mathClaims':[]}
    def test_explicit_task_and_rule_recognition(self):
        self.assertEqual(infer_task('学生机械移项却不理解'),'misconception')
        self.assertEqual(infer_task('前置知识不牢，补基础'),'foundation')
        self.assertEqual(infer_task('设计天平预测活动'),'activity')
        self.assertEqual(infer_task('补基础','activity'),'activity')
        self.assertEqual(len(STEPS),6);self.assertEqual(len(TOOLS),6)
    def test_citation_and_block_contract(self):
        self.assertEqual(validate_plan(self.plan,self.lesson,self.evidence),self.plan)
        for change in ['unknown_ref','duplicate_ref','missing_block','duplicate_block','unknown_block']:
            plan=copy.deepcopy(self.plan)
            if change=='unknown_ref':plan['blocks'][0]['evidenceIds']=['missing']
            if change=='duplicate_ref':plan['blocks'][0]['evidenceIds']=['source-1','source-1']
            if change=='missing_block':plan['blocks'].pop()
            if change=='duplicate_block':plan['blocks'][1]['id']='intro'
            if change=='unknown_block':plan['blocks'][1]['id']='missing'
            with self.subTest(change=change),self.assertRaises(ValueError):validate_plan(plan,self.lesson,self.evidence)
    def test_partial_generation_only_accepts_target(self):
        plan={**self.plan,'blocks':[self.plan['blocks'][1]]}
        self.assertEqual(len(validate_plan(plan,self.lesson,self.evidence,'example')['blocks']),1)
        with self.assertRaises(ValueError):validate_plan(plan,self.lesson,self.evidence,'intro')
    def test_client_cannot_supply_server_context(self):
        with self.assertRaises(ValueError):PlanningInput.model_validate({'lessonId':'lesson','task':'设计活动','documents':[]})
