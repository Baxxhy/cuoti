"""Source/difficulty policy checks; synthetic fixtures are not teacher evaluation."""
import copy,unittest
from sczx_business.experience_policy import provenance,validate_experience,diagnose,match_experiences
from sczx_business.education import catalog,profile

def candidate(subject='语文'):
    p=provenance({'provenance':{'kind':'team','author':'项目自编夹具','evidence':'本测试自编','authorization':'internal','authorizationEvidence':'仅供本地工程验收'}})
    return {'id':'case-test','versionId':'version-test','version':1,'subject':subject,'grade':'七年级','knowledgeIds':['kp-test'],'provenance':p,'experienceReview':{'reviewerId':'admin-test','provenance':p},'experience':{'difficulty':'找不到文本证据','diagnosis':'请学生指出文本依据','strategy':'先划出一句原文，再把原文与观点逐项对应','effectCheck':'换一段材料独立寻找证据'}}

class ExperiencePolicyTests(unittest.TestCase):
    def diagnosis(self,prompt='找不到文本证据',memory=None):return diagnose('语文',prompt,'我的答案','缺少依据',memory,'attempt-test',profile('语文')['diagnosticDimensions'])
    def match(self,doc):return match_experiences([doc],self.diagnosis(),'语文','七年级',['kp-test'])
    def test_catalog_and_subject_specific_dimensions(self):
        c=catalog();self.assertEqual(len(c['subjects']),19);self.assertEqual(len(c['responseTypes']),13);self.assertEqual(sum(len(x['grades']) for x in c['stages']),6)
        self.assertEqual(len({tuple(profile(x)['diagnosticDimensions']) for x in ['语文','数学','物理','历史']}),4)
        for x in c['subjects']:self.assertTrue(profile(x['value'])['diagnosticDimensions'])
    def test_legacy_and_malformed_provenance_read_unknown_without_mutation(self):
        for d in [{},{'provenance':{'kind':'bad'}}]:
            before=copy.deepcopy(d);self.assertEqual(provenance(d)['kind'],'unknown');self.assertEqual(d,before)
        with self.assertRaises(ValueError):validate_experience({'provenance':{'kind':'bad'}})
    def test_false_teacher_or_permission_claim_rejected(self):
        for p in [{'kind':'teacher'},{'kind':'public','authorization':'redistribution_confirmed'}]:
            with self.assertRaises(ValueError):validate_experience({'provenance':p})
    def test_real_evidence_and_uncertainty_no_cause_inference(self):
        d=self.diagnosis();self.assertEqual(d['possibleCauses'],[]);self.assertEqual(d['recommendedStrategy'],'hint');self.assertEqual(d['observations'][0]['id'],'attempt-test');self.assertTrue(d['confirmationQuestion'])
    def test_only_verified_unhelped_history_changes_strategy(self):
        facts=[{'evidenceId':'e'+str(i),'verification':'verified','helped':False,'outcome':'independent_incorrect'} for i in range(2)]
        self.assertEqual(self.diagnosis(memory=facts)['recommendedStrategy'],'foundation')
        for override in [{'helped':True},{'verification':'unverified'}]:self.assertEqual(self.diagnosis(memory=[{**x,**override} for x in facts])['recommendedStrategy'],'hint')
        self.assertEqual(self.diagnosis(prompt='换一种讲法',memory=facts)['recommendedStrategy'],'rephrase')
    def test_eligible_team_experience_traceable_and_not_claimed_teacher(self):
        doc=candidate();before=copy.deepcopy(doc);r=self.match(doc);self.assertFalse(r['fallback']);s=r['selected'][0];self.assertEqual(s['versionId'],'version-test');self.assertEqual(s['provenance']['kind'],'team');self.assertTrue(s['matchedDifficultyTerms']);self.assertIn('attempt-test',s['evidenceIds']);self.assertEqual(doc,before)
        # Long full-source excerpts may be trimmed, but the supplied selected method/version remains valid evidence.
        from sczx_business.tutoring import model_input,validate_result
        request={'guidance':True,'strategy':'hint','prompt':'请指出证据','history':[],'context':{'teachingCases':[{**doc,'retrievalText':'长原文'*10000}],'experienceDecision':r,'prerequisites':[]},'_validation':{'answer':'','equation':''}}
        self.assertEqual(model_input(request)['context']['teachingCases'],[])
        output={'title':'寻找证据','hint':'先划原句','steps':['说明原句支持的观点'],'question':'哪句最直接？','strategy':'hint','representation':'text','usedCaseVersionIds':['version-test']}
        self.assertEqual(validate_result(output,request)['sources'][0]['versionId'],'version-test')
    def test_unreviewed_changed_source_or_ai_never_promoted(self):
        for change in [{'experienceReview':{}},{'provenance':{'kind':'ai_candidate'}},{'provenance':{'kind':'teacher','author':'未核实','evidence':'自称'}}]:
            self.assertTrue(self.match({**candidate(),**change})['fallback'])
    def test_hard_filters_conditions_and_difficulty_reject(self):
        for change in [{'subject':'数学'},{'grade':'高一'},{'knowledgeIds':['other']},{'experience':{'difficulty':'历史因果','strategy':'比较史料'}},{'experience':{**candidate()['experience'],'boundary':'必须先掌握材料甲'}}]:
            r=self.match({**candidate(),**change});self.assertTrue(r['fallback']);self.assertTrue(r['rejected'])
        self.assertTrue(match_experiences([candidate()],self.diagnosis(),'','',[])['fallback'])
    def test_four_categories_can_use_same_framework(self):
        for subject in ['语文','数学','物理','历史']:
            d=diagnose(subject,'找不到文本证据',dimensions=profile(subject)['diagnosticDimensions']);r=match_experiences([candidate(subject)],d,subject,'七年级',['kp-test']);self.assertEqual(len(r['selected']),1)
