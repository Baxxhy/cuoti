"""Local runner must refuse production targets and foreign MySQL listeners."""
import importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('sczx_local',ROOT/'scripts/local.py');local=importlib.util.module_from_spec(spec);spec.loader.exec_module(local)
class LocalEntrypointsTests(unittest.TestCase):
 def test_foreign_mysql_listener_is_not_reused_or_stopped(self):
  with tempfile.TemporaryDirectory() as t:
   v={'home':t,'mysqlPort':23321}
   with patch.object(local,'mysql_ready',return_value=False),patch.object(local,'free',return_value=False),patch.object(local.subprocess,'Popen') as launch,patch.object(local.subprocess,'run') as command:
    with self.assertRaisesRegex(RuntimeError,'其他进程'):local.mysql_start(v)
    launch.assert_not_called();command.assert_not_called();self.assertFalse((Path(t)/'mysql/data').exists())
 def test_production_database_configuration_is_rejected_before_database_access(self):
  with tempfile.TemporaryDirectory() as t:
   home=Path(t);cfg={'SCZX_ENV':'production','SCZX_DATABASE_URL':'mysql+pymysql://root@127.0.0.1:23317/sczx','SCZX_STORAGE_DIR':t,'SCZX_FRONTEND_DIST':t,'SCZX_RELEASE_PYTHON':'/usr/bin/python3','SCZX_RELEASE_STATE':t}
   (home/'local.env').write_text('\n'.join(k+'='+v for k,v in cfg.items()))
   with patch.object(local.release,'db_engine') as db:
    with self.assertRaisesRegex(RuntimeError,'其他数据库'):local.config({'home':t,'database':'sczx'})
    db.assert_not_called()
