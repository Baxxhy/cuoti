"""Resource bundle provenance, review bindings and scope rules; no model calls."""
import copy,json,subprocess,sys,unittest
from pathlib import Path
from sczx_business.curated_resources import load_bundle,reviewed,digest
from sczx_business.experience_policy import diagnose,match_experiences,provenance

class CuratedBundleTests(unittest.TestCase):
 def test_19_subjects_have_three_distinct_reviewed_summaries(self):
  bundle,sources,review=load_bundle();from sczx_business.education import catalog
  self.assertEqual({r['subject'] for r in bundle['entries']},{s['value'] for s in catalog()['subjects']});self.assertEqual(len(bundle['entries']),57)
  for s in catalog()['subjects']:
   values=[r for r in bundle['entries'] if r['subject']==s['value']];self.assertEqual(len(values),3);self.assertEqual(len({r['experience']['strategy'] for r in values}),3)
  self.assertTrue(all(reviewed(r,sources[r['sourceId']],review) for r in bundle['entries']))
  self.assertIn('单人',review['reviewer']);self.assertNotIn('专家',review['reviewer'])
 def test_changed_content_or_source_does_not_inherit_human_approval(self):
  bundle,sources,review=load_bundle();row=bundle['entries'][0];source=sources[row['sourceId']]
  self.assertFalse(reviewed({**row,'title':'未复核改稿'},source,review));self.assertFalse(reviewed(row,{**source,'url':'https://example.org/not-original'},review))
 def test_unknown_rights_are_not_falsely_labelled_open_licence(self):
  _,sources,_=load_bundle()
  for source in sources.values():
   if source['license']=='unknown':self.assertEqual(source['reuseMode'],'summary_link_only')
  self.assertEqual(sources['music']['verification'],'license-only-content-not-reviewed')
 def test_reviewed_scope_is_exact_and_diagnostic_fallback_is_not_a_cause_label(self):
  bundle,sources,review=load_bundle();r=next(r for r in bundle['entries'] if r['subject']=='英语');p=provenance({'provenance':{'kind':'public','authorization':'internal','authorizationEvidence':'用户确认的中文摘要'}})
  doc={**r,'versionId':'test-version','knowledgeIds':[r['knowledgeId']],'provenance':p,'experienceReview':{'reviewerId':'test-admin','provenance':p,'applicability':r['applicability']}}
  d=diagnose('英语','I goed yesterday')
  decision=match_experiences([doc],d,'英语',r['grade'],[r['knowledgeId']]);self.assertTrue(decision['selected'][0]['diagnosticOnly']);self.assertEqual(d['possibleCauses'],[])
  for kwargs in [('数学',r['grade'],[r['knowledgeId']]),('英语','高一',[r['knowledgeId']]),('英语',r['grade'],['other'])]:self.assertTrue(match_experiences([doc],d,*kwargs)['fallback'])
  changed=copy.deepcopy(doc);changed['applicability']['requirements']=['必须有教师现场指导'];self.assertTrue(match_experiences([changed],d,'英语',r['grade'],[r['knowledgeId']])['fallback'])
 def test_pack_check_does_not_need_database_credentials(self):
  p=subprocess.run([sys.executable,'backend-business/scripts/seed_teaching_experiences.py','--check-only'],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['reviewedSummaries'],57)
