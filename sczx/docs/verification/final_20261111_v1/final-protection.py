import json,importlib.util,hashlib
from pathlib import Path
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());spec=importlib.util.spec_from_file_location('m','deploy/manage.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);cfg=m.configuration(f['migrationEnv']);cfg.update(SCZX_DATABASE_URL='mysql+pymysql://root@127.0.0.1:23317/sczx',SCZX_STORAGE_DIR='/tmp/sczx-uploads');old=json.loads((out/'migration-drill.json').read_text());state=m.database_state(cfg);tables=m.database_digest(cfg);files=m.file_manifest(cfg['SCZX_STORAGE_DIR']);import tarfile
originals={}
with tarfile.open(Path(f['formalBackup'])/'uploads.tar.gz') as archive:
 for item in archive:
  if item.isfile():originals[item.name.removeprefix('uploads/')]={'bytes':item.size,'sha256':hashlib.sha256(archive.extractfile(item).read()).hexdigest()}
digest=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest();assert state['heads']==['0013_teaching_insights'] and tables==old['originalTables'] and all(files.get(k)==v for k,v in originals.items());(out/'formal-protection-final.json').write_text(json.dumps({'at':m.utc(),'formalVersion':state['heads'][0],'allOriginalRowsUnchanged':True,'originalFileCount':len(originals),'currentFileCount':len(files),'extraFilesPendingApproval':len(files)-len(originals),'allOriginalFileBytesUnchanged':True,'formalMigration':False,'formalServiceSwitch':False,'publicPortOpened':False},indent=2));print('formal0013 all original rows and82files unchanged')
