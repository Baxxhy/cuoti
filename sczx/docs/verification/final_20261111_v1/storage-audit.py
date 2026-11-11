import json,tarfile,hashlib,importlib.util
from pathlib import Path
from sqlalchemy import create_engine,text
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());spec=importlib.util.spec_from_file_location('m','deploy/manage.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
# Compare original archive directly, without writing its private contents.
old={}
with tarfile.open(Path(f['formalBackup'])/'uploads.tar.gz') as t:
 for e in t:
  if e.isfile():old[e.name.removeprefix('uploads/')]={'bytes':e.size,'sha256':hashlib.sha256(t.extractfile(e).read()).hexdigest()}
now=m.file_manifest('/tmp/sczx-uploads');added={k:v for k,v in now.items() if k not in old};unchanged=all(now.get(k)==v for k,v in old.items());print('originalFilesUnchanged',unchanged,'added',len(added))
reports=[]
for label in ['initial','final']:
 test=json.loads((out/('tests-'+label+'.json')).read_text());e=create_engine('mysql+pymysql://root:'+f['mysqlPassword']+'@127.0.0.1:23320/'+test['database'])
 with e.connect() as c:rows=c.execute(text('SELECT storage_key,original_name FROM file_assets')).all()
 reports += [{'storageKey':r.storage_key,'testRun':label,'originalName':r.original_name} for r in rows if r.storage_key in added]
 e.dispose()
print('matchedTestUploads',len(reports));(out/'storage-audit.json').write_text(json.dumps({'originalFilesUnchanged':unchanged,'originalCount':len(old),'addedCount':len(added),'matches':reports,'addedDigests':added},indent=2))
