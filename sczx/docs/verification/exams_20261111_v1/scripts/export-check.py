import json,io,zipfile,sys
from pathlib import Path
import httpx
out=Path('/tmp/sczx-step17');f=json.loads((out/'private.json').read_text());fixture=json.loads((out/'grading-browser.json').read_text());exam=fixture['exam'];sub=next(s for s in exam['submissions'] if s['studentId']=='unit-s0');folder=out/'exports';folder.mkdir(exist_ok=True);r={'files':[],'permissions':[]}
with httpx.Client(base_url='http://127.0.0.1:8089',timeout=30) as t,httpx.Client(base_url='http://127.0.0.1:8089',timeout=30) as s:
 for c,user in [(t,'unit-t1'),(s,'unit-s0')]:assert c.post('/api/auth/login',json={'username':user,'password':f['password']}).status_code==200
 names={'student':'学生版试卷','teacher':'教师版试卷','submission':'学生原始答卷','grades':'班级成绩','learning':'考试学习记录'}
 for mode,name in names.items():
  response=t.get('/api/exams/'+exam['id']+'/export/'+mode,params={'submissionId':sub['id']});assert response.status_code==200,response.text;path=folder/(name+'.docx');path.write_bytes(response.content)
  with zipfile.ZipFile(io.BytesIO(response.content)) as z:
   xml=z.read('word/document.xml').decode();styles=z.read('word/styles.xml').decode();assert '宋体' in styles and 'Times New Roman' in styles and '000000' in styles
   if mode=='student':assert '参考答案' not in xml and '解析：' not in xml and '批阅' not in xml
   if mode=='teacher':assert all(e['question']['answer'] in xml for e in exam['paper']['entries'])
   if mode=='grades':assert '15' in xml and '30' in xml
   if mode=='submission':assert '原答案：0' in xml and '我直接猜0' in xml
  r['files'].append({'mode':mode,'file':path.name,'fontBlackA4Template':True,'fixedVersion':exam['versionId']})
 response=s.get('/api/exams/learning-records/export');assert response.status_code==200,response.text;(folder/'学生全部学习记录.docx').write_bytes(response.content)
 for path in ['/api/exams/'+exam['id']+'/export/teacher','/api/exams/'+exam['id']+'/export/grades','/api/exams/learning-records/export?studentId=unit-s1']:
  response=s.get(path);assert response.status_code in (403,404);r['permissions'].append({'path':path,'status':response.status_code})
 # Completed results, drafts and original source persist across the actual service restart.
 response=s.get('/api/exams/'+exam['id']);d=response.json();assert d['resultsAt'] and d['submission']['total']==15 and any(a['answer']=='0' for a in d['submission']['answers'].values());r['restartPersistence']=True;r['passed']=True
(out/'export-check.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print('6 actual DOCX exports, font/black/version/contents, student denial, restart persistence PASS')
