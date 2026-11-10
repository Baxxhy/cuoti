import os,sys,json,uuid,copy
from pathlib import Path
f=json.loads(Path('/tmp/sczx-step13/browser-private.json').read_text());os.environ['SCZX_DATABASE_URL']=f['url'];sys.path.insert(0,'backend-business')
from sczx_business.database import SessionLocal,engine
from sczx_business.models import ModelJob
from sczx_business.remediation import prepare
from sqlalchemy import select
assert engine.url.database.startswith('sczx_test_')
rows=json.loads(Path('/tmp/sczx-step13/real-cases.json').read_text());flow=json.loads(Path('/tmp/sczx-step13/browser-flow.json').read_text())
with SessionLocal.begin() as db:
 old=db.get(ModelJob,rows[0]['analysis']['id']);guid='job-'+uuid.uuid4().hex;oid='job-'+uuid.uuid4().hex
 db.add(ModelJob(id=guid,owner_id=old.owner_id,record_id=old.record_id,capability='text',request_key=uuid.uuid4().hex,input_hash=uuid.uuid4().hex,status='failed',error='受控中断：用于补救恢复验收，不代表真实服务故障',active_hash=None,input=copy.deepcopy(old.input)))
 db.add(ModelJob(id=oid,owner_id=old.owner_id,capability='ocr',file_id=flow['ocr']['fileId'],request_key=uuid.uuid4().hex,input_hash=uuid.uuid4().hex,status='failed',error='受控识别失败：用于恢复验收',active_hash=None,input={'wrongCapture':True}))
Path('/tmp/sczx-step13/fault-fixture.json').write_text(json.dumps({'wrongId':rows[0]['wrong']['id'],'modelJobId':guid,'ocrJobId':oid,'originalFileId':flow['jobs'][-2].get('fileId') if False else None,'cropFileId':flow['ocr']['fileId']},ensure_ascii=False));print('Two controlled failures seeded only in isolated DB')
