import json,hashlib,shutil,tarfile,sys,importlib.util
from pathlib import Path
from sqlalchemy import create_engine,text
out=Path('/tmp/sczx-local-final');f=json.loads(Path('/tmp/sczx-step20/private.json').read_text());audit=json.loads(Path('docs/verification/final_20261111_v1/storage-audit.json').read_text());root=Path('/tmp/sczx-uploads');dest=Path(f['base'])/'tests/retained-misplaced-uploads';dest.mkdir(parents=True,exist_ok=True);dest.chmod(0o700);keys=set(audit['addedDigests']);assert keys=={r['storageKey'] for r in audit['matches']} and len(keys)==6
spec=importlib.util.spec_from_file_location('m','deploy/manage.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);cfg=m.configuration(f['demoEnv']);formal={**cfg,'SCZX_DATABASE_URL':'mysql+pymysql://root@127.0.0.1:23317/sczx'};before=m.database_digest(formal);original={}
with tarfile.open(Path(f['formalBackup'])/'uploads.tar.gz') as tar:
 for p in tar:
  if p.isfile():original[p.name.removeprefix('uploads/')]={'bytes':p.size,'sha256':hashlib.sha256(tar.extractfile(p).read()).hexdigest()}
assert len(original)==82;assert all(m.file_manifest(root).get(k)==v for k,v in original.items());e=create_engine(formal['SCZX_DATABASE_URL'])
with e.connect() as c:
 for k in keys:assert c.execute(text('SELECT COUNT(*) FROM file_assets WHERE storage_key=:k'),{'k':k}).scalar()==0
for k in keys:assert m.file_manifest(root)[k]==audit['addedDigests'][k] and not (dest/k).exists()
manifest={'at':m.utc(),'authorization':'用户明确批准，仅可逆整理这6个测试文件','files':[{'from':str(root/k),'to':str(dest/k),**audit['addedDigests'][k]} for k in sorted(keys)],'status':'prepared'};private=dest/'move-manifest.json';m.write_json(private,manifest);moved=[]
try:
 for k in sorted(keys):shutil.move(root/k,dest/k);(dest/k).chmod(0o600);moved.append(k);assert m.sha(dest/k)==audit['addedDigests'][k]['sha256']
 assert m.file_manifest(root)==original and m.database_digest(formal)==before
except Exception:
 for k in reversed(moved):
  if not (root/k).exists():shutil.move(dest/k,root/k)
 raise
manifest.update(status='completed',all82OriginalBytesUnchanged=True,allFormalRowsUnchanged=True,filesDeleted=0,formalReferences=0,rollback='逐项核对目标摘要，原路径不存在时移回；只处理本清单6文件，不覆盖已有文件');m.write_json(private,manifest);(out/'d05-resolution.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print('D05 PASS:6 approved test files reversibly retained;82 originals and all formal rows unchanged')
