import importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('sczx_deploy_manage',ROOT/'deploy/manage.py');manage=importlib.util.module_from_spec(spec);spec.loader.exec_module(manage)
class ReleaseToolsTests(unittest.TestCase):
 def config(self,folder):return {'SCZX_ENV':'staging','SCZX_DATABASE_URL':'mysql+pymysql://root@127.0.0.1:3306/sczx_test_release_gate','SCZX_STORAGE_DIR':str(folder/'uploads'),'SCZX_FRONTEND_DIST':str(folder/'front'),'SCZX_RELEASE_PYTHON':os.sys.executable,'SCZX_RELEASE_STATE':str(folder/'state')}
 def test_exiting_empty_command_is_gone_but_unrelated_pid_is_refused(self):
  with tempfile.TemporaryDirectory() as t:
   base=Path(t);cfg=self.config(base);state=Path(cfg['SCZX_RELEASE_STATE']);state.mkdir();(state/'process.json').write_text(json.dumps({'pid':4321}));proc=base/'proc/4321';proc.mkdir(parents=True);(proc/'stat').write_text('4321 (python) S rest');(proc/'cmdline').write_bytes(b'')
   with patch.object(manage,'Path',side_effect=lambda p:base/'proc' if str(p)=='/proc' else Path(p)),patch.object(manage.os,'kill') as signal:
    self.assertIsNone(manage.pid_info(cfg)[1]);signal.assert_called_once_with(4321,0)
    (proc/'cmdline').write_bytes(b'python\0unrelated-program\0')
    with self.assertRaisesRegex(RuntimeError,'PID身份不符'):manage.pid_info(cfg)
 def test_configuration_only_parses_does_not_create_paths(self):
  with tempfile.TemporaryDirectory() as t:
   base=Path(t);cfg=self.config(base);p=base/'private.env';p.write_text('\n'.join(k+'='+v for k,v in cfg.items()));loaded=manage.configuration(p);self.assertFalse((base/'state').exists());self.assertEqual(loaded['SCZX_ENV'],'staging')
 def test_preflight_does_not_create_state_or_call_migration(self):
  with tempfile.TemporaryDirectory() as t:
   cfg=self.config(Path(t));state={'heads':['0013_teaching_insights'],'otherSessions':[],'activeModelJobs':0,'tables':['alembic_version']}
   with patch.object(manage,'database_state',return_value=state),patch.object(manage,'process_writers',return_value=[]),patch.object(manage,'release_identity',return_value={'fixed':False}),patch.object(manage.subprocess,'run') as execute:
    report=manage.preflight(cfg);self.assertEqual(report['plan'],['0014_examinations','0015_classroom_community','0016_offline_drafts','0017_case_bookmarks']);self.assertFalse(report['sideEffects']);execute.assert_not_called();self.assertFalse(Path(cfg['SCZX_RELEASE_STATE']).exists())
 def test_start_mismatch_refuses_without_implicit_migration(self):
  with tempfile.TemporaryDirectory() as t:
   cfg=self.config(Path(t));Path(cfg['SCZX_FRONTEND_DIST']).mkdir();(Path(cfg['SCZX_FRONTEND_DIST'])/'index.html').write_text('fixed app')
   with patch.object(manage,'preflight',return_value={'current':'0013_teaching_insights','target':'0016_offline_drafts','runtimeIssues':[]}),patch.object(manage.subprocess,'Popen') as launch:
    with self.assertRaisesRegex(RuntimeError,'start不会迁移'):manage.start_checks(cfg)
    launch.assert_not_called();self.assertFalse(Path(cfg['SCZX_RELEASE_STATE']).exists())
 def test_formal_target_requires_approval_even_if_mislabeled_staging(self):
  with tempfile.TemporaryDirectory() as t:
   cfg=self.config(Path(t));cfg['SCZX_DATABASE_URL']='mysql+pymysql://root@127.0.0.1:3306/sczx'
   self.assertTrue(manage.protected(cfg))
   with self.assertRaisesRegex(RuntimeError,'批准记录'):manage.approval(cfg,'migrate','0016_offline_drafts')
 def test_mysql_credentials_not_command_line_and_no_newline_injection(self):
  with tempfile.TemporaryDirectory() as t:
   cfg=self.config(Path(t));cfg['SCZX_DATABASE_URL']='mysql+pymysql://test:synthetic-secret@127.0.0.1:3306/sczx_test_release_gate';file,name=manage.mysql_options(cfg,t);self.assertEqual(file.stat().st_mode&0o777,0o600);self.assertEqual(name,'sczx_test_release_gate');cfg['SCZX_DATABASE_URL']='mysql+pymysql://test:bad%0Aoption@127.0.0.1:3306/sczx_test_release_gate'
   with self.assertRaises(ValueError):manage.mysql_options(cfg,t)
 def test_external_connection_or_model_job_blocks_mutations(self):
  with tempfile.TemporaryDirectory() as t:
   cfg=self.config(Path(t))
   for state in [{'otherSessions':[{'id':7}],'activeModelJobs':0},{'otherSessions':[],'activeModelJobs':1}]:
    with patch.object(manage,'database_state',return_value=state),patch.object(manage,'process_writers',return_value=[]):
     with self.assertRaisesRegex(RuntimeError,'其他连接'):manage.quiescent(cfg)
 def test_start_can_recover_orphan_job_but_never_bypass_other_writers(self):
  with tempfile.TemporaryDirectory() as t:
   cfg=self.config(Path(t));orphan={'otherSessions':[],'activeModelJobs':1}
   with patch.object(manage,'database_state',return_value=orphan),patch.object(manage,'process_writers',return_value=[]):
    manage.quiescent(cfg,allow_interrupted_jobs=True)
    with self.assertRaisesRegex(RuntimeError,'其他连接'):manage.quiescent(cfg)
   for sessions,writers in [([{'id':7}],[]),([],[{'pid':8}])]:
    with patch.object(manage,'database_state',return_value={**orphan,'otherSessions':sessions}),patch.object(manage,'process_writers',return_value=writers):
     with self.assertRaisesRegex(RuntimeError,'其他连接'):manage.quiescent(cfg,allow_interrupted_jobs=True)
 def test_release_tamper_detected_and_does_not_guess_parent_git_head(self):
  with tempfile.TemporaryDirectory() as t:
   base=Path(t);cfg=self.config(base);(base/'frontend/dist').mkdir(parents=True);page=base/'frontend/dist/index.html';page.write_text('known');cfg['SCZX_FRONTEND_DIST']=str(page.parent);(base/'release-manifest.json').write_text(json.dumps({'sczxCommit':'1'*40,'tree':'2'*40,'files':{'frontend/dist/index.html':manage.sha(page)}}))
   with patch.object(manage,'ROOT',base):
    self.assertEqual(manage.release_identity(cfg)['sczxCommit'],'1'*40);page.write_text('changed')
    with self.assertRaisesRegex(RuntimeError,'文件不一致'):manage.release_identity(cfg)
 def test_direct_production_migrate_command_refused(self):
  import subprocess,sys
  for action,settings in [('migrate',{'SCZX_ENV':'production'}),('seed',{'SCZX_ENV':'production'}),('migrate',{'SCZX_ENV':'staging','SCZX_DATABASE_URL':'mysql+pymysql://root@127.0.0.1:23317/sczx'})]:
   r=subprocess.run([sys.executable,'-m','sczx_business.commands',action],cwd=ROOT/'backend-business',env={**os.environ,**settings},text=True,capture_output=True);self.assertNotEqual(r.returncode,0);self.assertIn('不直接migrate head',r.stderr+r.stdout)
 def test_production_application_refuses_insecure_cookie_or_auto_schema(self):
  import subprocess,sys
  for secure,automatic in [('false','false'),('true','true')]:
   r=subprocess.run([sys.executable,'-c','from sczx_business.main import startup; startup()'],cwd=ROOT/'backend-business',env={**os.environ,'SCZX_ENV':'production','SCZX_COOKIE_SECURE':secure,'SCZX_AUTO_CREATE_SCHEMA':automatic},text=True,capture_output=True);self.assertNotEqual(r.returncode,0);self.assertIn('禁止自动建表',r.stderr)
 def test_package_uses_sczx_root_tree_from_parent_git_repository(self):
  import subprocess
  with tempfile.TemporaryDirectory() as tmp:
   parent=Path(tmp)/'parent';root=parent/'sczx';(root/'backend-business').mkdir(parents=True);(root/'backend-business/app.py').write_text('source')
   (root/'frontend/src').mkdir(parents=True);js=root/'frontend/src/app.js';js.write_text('const app=1');dist=root/'frontend/dist';dist.mkdir();(dist/'index.html').write_text('compiled app');(dist/'build-info.json').write_text(json.dumps({'sources':{'frontend/src/app.js':manage.sha(js)}}))
   def git(*args):return subprocess.check_output(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',*args],cwd=parent,text=True).strip()
   git('init','-q');git('add','sczx/backend-business','sczx/frontend/src');git('commit','-qm','parent fixture');tree=git('rev-parse','HEAD:sczx');revision=git('commit-tree',tree,'-m','sczx root fixture')
   with patch.object(manage,'ROOT',root):result=manage.package(revision,dist,Path(tmp)/'release')
   released=Path(result['release']);self.assertTrue((released/'backend-business/app.py').is_file());self.assertFalse((released/'sczx').exists());self.assertEqual(json.loads((released/'release-manifest.json').read_text())['sczxCommit'],revision)
