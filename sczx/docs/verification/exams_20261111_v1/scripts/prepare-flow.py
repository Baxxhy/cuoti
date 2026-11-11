import sys,json,uuid,time
from pathlib import Path
import httpx
sys.path.insert(0,'scripts');from install_unit_content import call
out=Path('/tmp/sczx-step17');f=json.loads((out/'private.json').read_text());installed=json.loads((out/'content-installed.json').read_text());r={'bank':[]}
with httpx.Client(base_url='http://127.0.0.1:8089',timeout=30) as c:
 assert c.post('/api/auth/login',json={'username':'unit-t1','password':f['password']}).status_code==200
 call(c,'POST','/exams/bank/import',{'lessonId':'lesson-simple'})
 for prompt,eq,ans,kid,kind in [('共同运算求解','2x+6=10','2','kp-equality','calculation'),('加法方程求解','x+7=12','5','kp-linear-simple','calculation'),('三件商品加一次运费共21元，求每件单价。','3x+6=21','5','kp-linear-model','application')]:
  data={'prompt':prompt,'equation':eq,'answer':ans,'explanation':'两边进行相同运算；同除必须非零，结果代回原式。','knowledgeIds':[kid],'unitId':'unit-equation','kind':kind,'source':'项目自编考试验收'};q=call(c,'POST','/exams/bank',{'data':data});q=call(c,'POST','/exams/bank/'+q['id']+'/review',{'revision':q['revision'],'confirmed':True});r['bank'].append(q)
 r['candidate']=call(c,'POST','/ai/jobs',{'capability':'text','requestKey':uuid.uuid4().hex,'data':{'examCandidate':True,'unitId':'unit-equation','knowledgeIds':['kp-equality'],'kind':'calculation','difficulty':'easy'}})
(out/'flow-fixture.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print('real course-source bank imports + reviewed questions + queued candidate')
