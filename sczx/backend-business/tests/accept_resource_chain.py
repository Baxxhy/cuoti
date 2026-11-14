"""Eight-subject real API/persistence chain. SCZX_RESOURCE_REAL=1 uses real Codex for both models."""
import asyncio,copy,json,os,secrets,sys,uuid
from pathlib import Path
from unittest.mock import patch
import httpx
from sqlalchemy import select
from sczx_business.main import app
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account,Course,Lesson,LessonContent,LessonVersion,Classroom,ClassMember,LearningTask,StudentRecord,ModelJob,ModelRun,Attempt
from sczx_business.security import hash_password
from sczx_business.curated_resources import import_resources,load_bundle
from sczx_business.teaching import assign
from sczx_business.model_jobs import execute

# Original small assessment materials, not claims about the source authors' original classrooms.
SAMPLES={
 '语文':('校门口的树下，午休时总坐着读书的同学。班级同学自发捡走树旁的纸屑。请找一句支持“同学爱护校园”的证据。','因为树很好看','雨后几位同学擦干操场长椅，方便别人坐下休息。哪一处行为能支持“同学关心他人”？','擦干长椅，方便别人休息'),
 '数学':('三根纸条长4厘米、5厘米、10厘米，能围成三角形吗？请说明依据。','能，因为有三根','三根纸条长3厘米、4厘米、5厘米，能围成三角形吗？说明依据。','能，任意两边之和大于第三边'),
 '英语':('我想表达昨天去了学校，写成 I goed to school yesterday. 请先引导我检查。','I goed to school yesterday.','用完整英语句子表达“我昨天看望了朋友”，并说明时间依据。','I visited my friend yesterday. 时间提示yesterday表示过去'),
 '物理':('书静止在水平桌面上。请画出书受到的力并说明施力物体，不把书施给桌面的力画在书上。','向右的力，因为看书时眼睛向右','悬挂在绳上的小球静止，说明小球受到哪些力及其方向。','重力向下，绳的拉力向上'),
 '化学':('粒子图中每个粒子都由一个A原子和一个B原子组成，全部粒子相同。它是化合物还是混合物？说明依据。','混合物，因为有A和B','粒子图中既有单独的A粒子又有单独的B粒子，二者未结合，判断物质分类并说明依据。','混合物；有两种物质的粒子，未组成同一种化合物'),
 '历史':('甲材料是一位亲历者事后写给家人的信，乙材料是多年后教材的介绍。判断材料价值前需要核对哪些出处信息？','亲历者说的全部是真的','新材料是一张事件发生时的宣传海报。写出判断其证据价值时应核对的两项信息和一项局限。','作者、时间或受众和目的；宣传目的可能影响其表述，不能代表全部事实'),
 '地理':('自编校园简图的上方表示北，教学楼在操场的右侧。请说明教学楼相对操场的方向，并解释参照依据。','在左边，因为我站在校门看','另一张自编简图上方表示北，图书馆在广场的下方。说明相对方位和参照依据。','图书馆在广场南方；依据图上上北下南的方向约定'),
 '生物学':('文字观察资料：甲植物叶脉平行，乙植物叶脉呈网状。请依据可观察特征给两株植物分组，不只按大小或个人喜好分类。','我喜欢的放一组，不喜欢的放一组','新观察资料：A植物叶脉平行，B植物叶脉呈网状，C植物叶脉平行。请给三株植物分组，并说明可复查的依据。','A和C归一组，B单列一组；依据实际记录中的叶脉特征，不能按喜好分组')}
TARGETS={'语文':'文本证据定位','数学':'三角形性质与解释','英语':'一般过去时','物理':'力的示意图','化学':'元素化合物与混合物','历史':'史料出处与可信度','地理':'地图图例与方向','生物学':'生物分类与特征'}

class ControlledResourceProvider:
 async def call(self,capability,data,**kwargs):
  if capability=='lesson_plan':
   return {'title':data['task'][:60],'goal':data['goal'],'rationale':['先确认当前困难，再用给定资源教法组织练习。'],'blocks':[{'id':b['id'],'title':b['title'],'content':data['experienceDecision']['selected'][0]['method'],'evidenceIds':[data['evidence'][0]['id']]} for b in data['blocks']],'mathClaims':[]},'controlled','controlled resource boundary'
  selected=data['context']['experienceDecision']['selected']
  return {'title':'先核对你的依据','hint':'请先说明你刚才怎样判断。','steps':[selected[0]['method']],'question':'哪一步是你最不确定的？','mathClaims':[],'strategy':data['strategy'],'representation':'text','nextStrategy':'rephrase','prerequisiteId':'','usedCaseVersionIds':[x['versionId'] for x in selected]},'controlled','controlled resource boundary'

async def acceptance(output,private=None):
 assert engine.url.database.startswith('sczx_test_')
 real=os.getenv('SCZX_RESOURCE_REAL')=='1';prefix='rc'+uuid.uuid4().hex[:7];password=secrets.token_urlsafe(24)
 with SessionLocal.begin() as db:
  for suffix,role in [('a','admin'),('t','teacher'),('s','student')]:db.add(Account(id=prefix+suffix,username=prefix+suffix,display_name='八科工程验收'+role,role=role,password_hash=hash_password(password)))
  db.flush();import_resources(db,prefix+'a',apply=True)
  bundle=load_bundle()[0];fixtures=[]
  selected_subjects=os.getenv('SCZX_RESOURCE_SUBJECTS','').split(',')
  for i,(subject,sample) in enumerate(SAMPLES.items()):
   if selected_subjects!=[''] and subject not in selected_subjects:continue
   row=next(x for x in bundle['entries'] if x['subject']==subject and x['topic']==TARGETS[subject]);ident=prefix+'-'+str(i);course=ident+'c';lesson=ident+'l';version=ident+'v';room=ident+'r';task=ident+'t'
   questions=[{'id':ident+'q'+str(n),'kind':'practice' if n==0 else 'replacement','prompt':sample[0] if n==0 else sample[2],'answer':'由教师核对原题解释' if n==0 else sample[3],'equation':'','responseType':'short_answer','gradingMode':'manual','knowledgeIds':[row['knowledgeId']],'options':[]} for n in range(2)]
   blocks=[{'id':ident+'intro','type':'explanation','title':row['topic'],'content':row['experience']['goal'],'required':True},{'id':ident+'practice','type':'practice','title':'先试一试','content':'保留你的原始答案与理由。','questionIds':[questions[0]['id']],'required':False},{'id':ident+'check','type':'check','title':'独立新题','content':'这道新题不提供提示，提交后由教师核对。','questionIds':[questions[1]['id']],'required':False}]
   data={'title':row['topic'],'grade':row['grade'],'subject':subject,'duration':30,'source':'八科隔离工程验收，原题为项目自编','goal':row['experience']['goal'],'knowledgeIds':[row['knowledgeId']],'prerequisiteIds':[],'caseId':None,'caseVersionId':None,'blocks':blocks,'questions':questions}
   db.add(Course(id=course,title=subject+'工程验收课程',grade=row['grade'],metadata_json={'subject':subject}));db.flush();db.add(Lesson(id=lesson,course_id=course,title=row['topic']));db.flush();db.add(LessonContent(lesson_id=lesson,draft=None,status='published',reviewed=True));db.add(LessonVersion(id=version,lesson_id=lesson,number=1,data=data));db.add(Classroom(id=room,teacher_id=prefix+'t',name=subject+'隔离验收班',grade=row['grade'],subject=subject));db.flush();db.add(ClassMember(classroom_id=room,student_id=prefix+'s'));db.flush()
   t=LearningTask(id=task,classroom_id=room,teacher_id=prefix+'t',lesson_id=lesson,title=row['topic'],snapshot={**copy.deepcopy(data),'lessonSnapshot':{**data,'versionId':version}},questions=questions);db.add(t);db.flush();assign(db,t,prefix+'s');db.flush();record=db.scalar(select(StudentRecord).where(StudentRecord.task_id==task,StudentRecord.student_id==prefix+'s')).id
   fixtures.append({'subject':subject,'row':row,'task':task,'lesson':lesson,'record':record,'block':blocks[1]['id'],'sample':sample})
 from sczx_business.model_provider import ModelProvider
 provider=ModelProvider() if real else ControlledResourceProvider();results=[];gate=asyncio.Semaphore(2)
 async def runjob(client,job):
  with SessionLocal.begin() as db:
   row=db.get(ModelJob,job['id']);row.status='running';row.attempt_number+=1;rid='run-'+uuid.uuid4().hex;db.add(ModelRun(id=rid,job_id=row.id,number=row.attempt_number))
  await execute(job['id'],rid)
  value=await request(client,'GET','/ai/jobs/'+job['id']);assert value['status']=='succeeded',value;return value
 async def request(c,method,path,body=None,status=200):
  response=await c.request(method,'/api'+path,json=body)
  if response.status_code==409 and '/confirm' in path and '并发' in response.text:
   await asyncio.sleep(.15);response=await c.request(method,'/api'+path,json=body)
  if response.status_code!=status:raise AssertionError(path+' '+str(response.status_code)+' '+response.text[:800])
  return response.json()
 async def login(c,suffix):c.cookies.clear();return await request(c,'POST','/auth/login',{'username':prefix+suffix,'password':password})
 async def one(f):
  async with gate:
   c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test')
   try:
    await login(c,'s');original=await request(c,'POST','/records/'+f['task']+'/attempts',{'question':0,'answer':f['sample'][1],'reason':'这是首次独立尝试，请根据实际依据引导'},201)
    payload={'capability':'text','recordId':f['record'],'requestKey':uuid.uuid4().hex,'data':{'guidance':True,'strategy':'hint','prompt':f['row']['experience']['difficulty']+'。请先帮我检查。','question':0,'blockId':f['block']}}
    job=await request(c,'POST','/ai/jobs',payload,201);selected=job['input']['context']['experienceDecision']['selected'];assert any(s['id']==f['row']['id'] for s in selected)
    guidance=await runjob(c,job);assert guidance['result']['usedCaseVersionIds'];assert all(s['provenance']['kind']=='public' for s in guidance['result']['experienceDecision']['selected'])
    retest=await request(c,'POST','/records/'+f['task']+'/attempts',{'question':1,'answer':f['sample'][3],'reason':'独立新题作答，无新增提示','helped':False},201)
    with SessionLocal() as db:independent=db.get(Attempt,retest['id']);assert independent.helped is False
    await login(c,'t');accessible=await request(c,'GET','/ai/jobs/'+job['id']);assert accessible['result']['usedCaseVersionIds']==guidance['result']['usedCaseVersionIds']
    prep=await request(c,'POST','/ai/jobs',{'capability':'lesson_agent','requestKey':uuid.uuid4().hex,'data':{'lessonId':f['lesson'],'task':f['row']['experience']['difficulty']+'，请用已有教法帮助学生并保留独立检查。'}},201)
    plan=await runjob(c,prep);assert any(s['id']==f['row']['id'] for s in plan['result']['experienceDecision']['selected'])
    state=await request(c,'GET','/ai/agent/draft-state?lessonId='+f['lesson']);confirmed=await request(c,'POST','/ai/agent/'+prep['id']+'/confirm',{'expectedDraftHash':state['draftHash'],'confirmed':True})
    teacherView=await request(c,'GET','/platform?lessonId='+f['lesson']);assert f['task'] in teacherView['studentRecords']
    feedback='工程验收反馈：新题作答已保存；开放题仍需教师依据材料核对，不能仅凭提交认定掌握。'
    await request(c,'PUT','/records/'+f['record']+'/feedback',{'feedback':feedback});await login(c,'s');saved=await request(c,'GET','/platform?lessonId='+f['lesson']);assert saved['records'][f['task']]['feedback']==feedback
    result={'subject':f['subject'],'status':'passed','sourceId':f['row']['sourceId'],'resourceId':f['row']['id'],'originalAttempt':original,'guidance':guidance,'independentRetest':{**retest,'helped':False,'actualLearningOutcome':'未测量；这是模拟账号提交，开放题待教师评阅'},'teacherPlan':plan,'confirmed':confirmed,'teacherReadActualJob':True,'teacherSawRecord':True,'studentSawFeedback':True}
   except Exception as error:result={'subject':f['subject'],'status':'failed','error':type(error).__name__+': '+str(error)[:2200]}
   finally:await c.aclose()
   results.append(result);Path(output).write_text(json.dumps({'mode':'real Codex student guidance and teacher plan' if real else 'controlled models; real MySQL/API','results':results},ensure_ascii=False,indent=2));print(f['subject'],result['status'],flush=True)
 with patch('sczx_business.model_jobs.provider',provider):await asyncio.gather(*(one(f) for f in fixtures))
 if hasattr(provider,'close'):await provider.close()
 if private:Path(private).write_text(json.dumps({'prefix':prefix,'password':password,'fixtures':[{k:v for k,v in f.items() if k in ('subject','task','lesson','record','block')} for f in fixtures]}));os.chmod(private,0o600)
 return all(r['status']=='passed' for r in results)

if __name__=='__main__':
 output=sys.argv[1];private=os.getenv('SCZX_RESOURCE_PRIVATE')
 raise SystemExit(0 if asyncio.run(acceptance(output,private)) else 1)
