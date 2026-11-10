import json,statistics,time
from pathlib import Path
from sqlalchemy import create_engine,text
import httpx
out=Path('/tmp/sczx-step16');fx=json.loads((out/'private.json').read_text());r={'files':[]};image=next(x['job']['fileId'] for x in json.loads((out/'model-unit.json').read_text())['cases'] if x['key'].endswith(':ocr'));path='/api/files/'+image
for username,expected in [(None,401),('unit-s1',200),('unit-t1',200),('unit-t2',403),('unit-s4',403)]:
 with httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as c:
  if username:assert c.post('/api/auth/login',json={'username':username,'password':fx['password']}).status_code==200
  response=c.get(path);assert response.status_code==expected,(username,response.status_code);r['files'].append({'user':username or 'anonymous','status':response.status_code,'bytes':len(response.content) if response.status_code==200 else None})
engine=create_engine(fx['url'])
with engine.connect() as c:
 r['modelJobs']=[dict(row._mapping) for row in c.execute(text('SELECT capability,status,COUNT(*) AS count FROM model_jobs GROUP BY capability,status'))];assert c.execute(text("SELECT COUNT(*) FROM model_jobs WHERE status IN ('queued','running')")).scalar()==0;r['schema']=c.execute(text('SELECT version_num FROM alembic_version')).scalar()
r.update(passed=True,productionURL='http://127.0.0.1:8087',frontEnd='Vite production build, same origin static mount',noPublicTargetConfigured=True);(out/'runtime-check.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print('file owner/teacher/cross-class/anonymous permissions and idle persistent runtime PASS')
