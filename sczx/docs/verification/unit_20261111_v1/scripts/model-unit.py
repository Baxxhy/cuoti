import json,time,uuid,sys,traceback
from pathlib import Path
import httpx
root=Path('/root/Baxxhy/zhiwei/sczx');sys.path[:0]=[str(root/'backend-business'),str(root/'scripts')]
from install_unit_content import call
out=Path('/tmp/sczx-step16');fx=json.loads((out/'private.json').read_text());tasks=json.loads((out/'tasks.json').read_text())['t1'];bundle=json.loads((root/'docs/planning/第十六步单元内容草案_20261111_v1.json').read_text());by_id={l['id']:l['data'] for l in bundle['lessons']};tracefile=out/'model-unit.json';report=json.loads(tracefile.read_text()) if tracefile.exists() else {'startedAt':time.time(),'cases':[],'errors':[]}
def save():tracefile.write_text(json.dumps(report,ensure_ascii=False,indent=2))
def job(c,key,body):
 old=next((x for x in report['cases'] if x['key']==key and x.get('job',{}).get('status')=='succeeded'),None)
 if old:return old['job']
 start=time.monotonic();value=call(c,'POST','/ai/jobs',{'requestKey':uuid.uuid4().hex,**body})
 for _ in range(360):
  value=call(c,'GET','/ai/jobs/'+value['id'])
  if value['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.5)
 item={'key':key,'seconds':round(time.monotonic()-start,3),'job':value};report['cases'].append(item);save();print(key,value['status'],item['seconds'],flush=True)
 if value['status']!='succeeded':raise RuntimeError(key+': '+value.get('error',''))
 return value
with httpx.Client(base_url='http://127.0.0.1:8087',timeout=30) as c:
 c.post('/api/auth/login',json={'username':'unit-s1','password':fx['password']});platform=call(c,'GET','/platform')
 for row in tasks:
  name=row['sourceId'];task=row['taskId'];rec=platform['records'][task];record=rec['id'];q=by_id[name]['questions'][2];base={'guidance':True,'question':2}
  try:
   hint=job(c,name+':text-hint',{'capability':'text','recordId':record,'data':{**base,'strategy':'hint','prompt':'我不清楚当前这道题第一步的依据，请只给一个可操作提示，保留非零条件。'}})
   example=job(c,name+':example',{'capability':'text','recordId':record,'data':{**base,'strategy':'example','parentJobId':hint['id'],'prompt':'请换用不同数值举例，解释当前问题涉及的数量或运算关系，不给原题答案。'}})
   rephrase=job(c,name+':rephrase',{'capability':'text','recordId':record,'data':{**base,'strategy':'rephrase','parentJobId':example['id'],'prompt':'我仍没明白，请使用和刚才不同的表示方式解释当前步骤，不给原题答案。'}})
   job(c,name+':foundation',{'capability':'text','recordId':record,'data':{**base,'strategy':'foundation','prompt':'请回到当前题目真正需要的一层前置知识，先问一个基础问题。'}})
   job(c,name+':try',{'capability':'text','recordId':record,'data':{**base,'strategy':'try','parentJobId':rephrase['id'],'prompt':'我准备自己试试，保留之前获得帮助的事实。'}})
   path=out/(name+'-question.png')
   with path.open('rb') as f:r=c.post('/api/files',files={'file':(path.name,f,'image/png')})
   assert r.status_code==201,r.text;asset=r.json()
   ocr=job(c,name+':ocr',{'capability':'ocr','recordId':record,'fileId':asset['id'],'data':{'question':2}})
   # The engineering fixture explicitly confirms against its own original screenshot;
   # raw OCR and any corrected text remain separately recorded, not human quality labels.
   job(c,name+':ocr-confirmed-guidance',{'capability':'text','recordId':record,'data':{**base,'strategy':'hint','prompt':'我已对照原题核对识别文字，请从当前课时给下一步提示。','ocrJobId':ocr['id'],'confirmed':True,'recognizedText':q['prompt']+'\n'+q['equation'],'confirmedEquation':q['equation']}})
  except Exception as e:report['errors'].append({'lesson':name,'error':str(e)});save();print('ERROR',name,str(e),flush=True)
 report['completedAt']=time.time();save()
if report['errors']:sys.exit(1)
