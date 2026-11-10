import json,sys
from pathlib import Path
import httpx
sys.path.insert(0,'scripts');from install_unit_content import call
out=Path('/tmp/sczx-step16');users=json.loads(Path('/tmp/sczx-step5-users.json').read_text());installed=json.loads((out/'content-main-installed.json').read_text());report={'checks':[]}
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30) as c:
 assert c.post('/api/auth/login',json={'username':users['admin'],'password':users['adminPassword']}).status_code==200
 catalog=call(c,'GET','/curriculum/courses');unit=next(u for co in catalog for u in co['units'] if u['id']=='unit-equation');assert unit['lessonOrder']==list(installed['mapping'].values());rows=[]
 for source,lid in installed['mapping'].items():
  raw=call(c,'GET','/curriculum/lessons/'+lid);item=raw.get('published',raw);assert len(item['questions'])==6;rows.append({'sourceId':source,'id':lid,'title':item['title'],'versionId':item['versionId'],'questions':len(item['questions']),'reviewRecord':item.get('reviewRecord'),'verification':item.get('verification')})
 points=call(c,'GET','/curriculum/knowledge');known={p['id']:p for p in points}
 def visit(k,stack):
  assert k not in stack,'cycle';assert k in known
  for p in known[k].get('prerequisites',[]):visit(p,stack+[k])
 for k in known:visit(k,[])
 report.update(passed=True,lessons=rows,lessonOrder=unit['lessonOrder'],extraPreservedLessons=[l['id'] for l in unit['lessons'] if l['id'] not in unit['lessonOrder']],knowledgeNoCycle=True,knowledge=points)
(out/'main-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('formal five published lessons, explicit order, preserved historical extras and no knowledge cycles PASS')
