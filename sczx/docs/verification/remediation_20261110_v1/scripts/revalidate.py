import os,sys,json
from pathlib import Path
fx=json.loads(Path('/tmp/sczx-step13/browser-private.json').read_text());os.environ['SCZX_DATABASE_URL']=fx['url'];sys.path.insert(0,'backend-business')
from sczx_business.database import SessionLocal
from sczx_business.models import ModelJob,FileAsset,WrongQuestion
from sczx_business.remediation import validate,serialize
from sczx_business.tutoring import validate_result,TutoringResult
from sqlalchemy import select
import hashlib
out=Path('/tmp/sczx-step13');checks=[]
with SessionLocal() as db:
 for job in db.scalars(select(ModelJob).where(ModelJob.status=='succeeded')).all():
  if not job.input.get('remediation'):continue
  try:
   data=job.input
   value=validate_result({k:v for k,v in job.result.items() if k in TutoringResult.model_fields},data) if data['mode']=='guidance' else validate({k:v for k,v in job.result.items() if k in ('cause','evidence','uncertainty','goal','steps','checkQuestion','strategy','mathClaims','variant')},data)
   checks.append({'jobId':job.id,'wrongId':data['wrongId'],'mode':data['mode'],'passed':True})
  except Exception as e:checks.append({'jobId':job.id,'mode':job.input['mode'],'passed':False,'error':str(e)})
 flow=json.loads((out/'browser-flow.json').read_text());w=db.get(WrongQuestion,flow['photoWrong']);details=w.details;files=[]
 for kind,fid in [('original',w.file_id),('crop',details['cropFileId'])]:
  f=db.get(FileAsset,fid);raw=(out/'uploads'/f.storage_key).read_bytes();files.append({'kind':kind,'fileId':fid,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 assert files[0]['sha256']==hashlib.sha256((out/'two-questions.png').read_bytes()).hexdigest();assert files[0]['fileId']!=files[1]['fileId']
 result={'allModelOutputsPassFinalGuards':all(x['passed'] for x in checks),'checks':checks,'originalUnchanged':True,'files':files,'confirmedText':details['confirmedText'],'ocrJobId':details['ocrJobId'],'rawOcr':db.get(ModelJob,details['ocrJobId']).result,'photoFinalStatus':serialize(db,w)['status']}
(out/'final-output-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('Final guards:',result['allModelOutputsPassFinalGuards'],'Outputs:',len(checks),'Original image intact')
assert result['allModelOutputsPassFinalGuards']
