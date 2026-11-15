import unittest,importlib.util,json,tempfile,asyncio
from pathlib import Path
sp=importlib.util.spec_from_file_location('runner',Path(__file__).with_name('run.py'));m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):self.c=json.loads((m.ROOT/'config.json').read_text());self.s=json.loads((m.ROOT/'scenarios/v1.json').read_text())['scenarios'];self.corpus=json.loads((m.ROOT/'scenarios/corpus.json').read_text())
 def test_frozen_and_balanced(self):
  m.integrity();self.assertEqual(len(self.s),16);self.assertEqual([sum(s['category']==k for s in self.s) for k in ['L','M','N','H']],[4]*4)
 def test_no_gold_and_identical_candidates(self):
  for s in self.s:
   built={g:m.build(s,g,self.c,self.corpus) for g in 'ABC'}
   for p,d,meta in built.values():self.assertNotIn('expected_strategy',d);self.assertNotIn('independent_rubric',d)
   self.assertNotIn('experiences',built['A'][1]);self.assertNotIn('learning_memory',built['B'][1]);self.assertEqual(built['B'][2]['candidateVersionIds'],built['C'][2]['candidateVersionIds'])
 def test_history_changes_policy(self):
  s={s['scenario_id']:s for s in self.s};self.assertEqual(m.build(s['L01'],'C',self.c,self.corpus)[1]['difficulty_evidence']['recommendedStrategy'],'hint');self.assertEqual(m.build(s['L02'],'C',self.c,self.corpus)[1]['difficulty_evidence']['recommendedStrategy'],'foundation')
 def test_append_only(self):
  with tempfile.TemporaryDirectory() as t:
   folder=Path(t);(folder/'trials').mkdir();asyncio.run(m.trial(folder,self.s[0],'A',0,self.c,self.corpus,'controlled'));p=folder/'trials/L01-A-0/result.json';b=p.read_bytes();asyncio.run(m.trial(folder,self.s[0],'A',0,self.c,self.corpus,'controlled'));self.assertEqual(b,p.read_bytes())
