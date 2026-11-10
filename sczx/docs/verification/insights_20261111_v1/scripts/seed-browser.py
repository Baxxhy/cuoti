import os,sys,json,uuid,secrets,copy,subprocess
from pathlib import Path
from datetime import datetime,timedelta
from sqlalchemy import create_engine,text,select
name='sczx_test_insights_browser_'+uuid.uuid4().hex[:6]
with create_engine('mysql+pymysql://root@127.0.0.1:23317/mysql').connect() as c:c.execute(text('CREATE DATABASE '+name+' CHARACTER SET utf8mb4'))
os.environ['SCZX_DATABASE_URL']='mysql+pymysql://root@127.0.0.1:23317/'+name
sys.path[:0]=[str(Path('backend-business').resolve()),str(Path('backend-business/tests').resolve())]
subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd='backend-business',check=True)
from test_teaching_mysql import fixture,create_accounts
from sczx_business.database import SessionLocal
from sczx_business.models import *
from sczx_business.teaching import assign,now
from sczx_business.security import hash_password
password=secrets.token_urlsafe(24);create_accounts(password,'ops-');fx=fixture('ops','ops-')
with SessionLocal.begin() as db:
 db.add(Account(id='ops-admin',username='ops-admin',role='admin',display_name='运营验收员',password_hash=hash_password(password)));db.add(Account(id='ops-s11',username='ops-s11',role='student',display_name='历史同学',password_hash=hash_password(password)))
 db.add(ClassMember(classroom_id='ops-c2',student_id='ops-s10'));db.flush()
 for tid in fx['tasks'][4:]:assign(db,db.get(LearningTask,tid),'ops-s10')
 for tid in fx['tasks'][:2]:assign(db,db.get(LearningTask,tid),'ops-s11')
 for j in range(1,4):db.add(KnowledgePoint(id='ops-kp'+str(j),name=['','逆运算','非零条件','去括号'][j],prerequisites=['ops-kp'] if j==1 else []))
 for j in range(1,3):
  lid='ops-lesson'+str(j);db.add(Lesson(id=lid,course_id='ops-course',title=['','逆运算练习','条件与括号'][j]));db.flush();d=copy.deepcopy(fx['data']);d['knowledgeIds']=['ops-kp'+str(j)];d['prerequisiteIds']=['ops-kp'] if j==1 else []
  for q in d['questions']:q['knowledgeIds']=d['knowledgeIds']
  db.add(LessonContent(lesson_id=lid,status='published',reviewed=True));db.add(LessonVersion(id='ops-v'+str(j),lesson_id=lid,number=1,data=d));task=LearningTask(id='ops-target'+str(j),classroom_id='ops-c0',teacher_id='ops-t1',lesson_id=lid,title=d['title'] if 'title' in d else lid,snapshot={**d,'lessonSnapshot':{**d,'versionId':'ops-v'+str(j)}},questions=d['questions'],published_at=now());db.add(task);db.flush()
  for sid in ['ops-s0','ops-s1','ops-s2','ops-s9']:assign(db,task,sid)
 for sid in ['ops-s0','ops-s1']:
  rid=db.scalar(select(StudentRecord.id).where(StudentRecord.task_id=='ops-t00',StudentRecord.student_id==sid))
  for j,q in enumerate([0,2,2]):
   aid='ops-a-'+sid+'-'+str(j);db.add(Attempt(id=aid,record_id=rid,question=q,answer='2',reason='把右边的数直接相减了',correct=False,helped=False,verification={'status':'inconsistent'},created_at=datetime.utcnow()+timedelta(hours=8,minutes=-10+j)));db.flush()
   if j==1:db.add(WrongQuestion(id='ops-w-'+sid,owner_id=sid,record_id=rid,attempt_id=aid,prompt='3z=18',answer='2',reason='把18减3',details={'equation':'3z=18','knowledgeIds':['ops-kp'],'cause':'运算步骤错误','causeConfirmed':True}))
 rid=db.scalar(select(StudentRecord.id).where(StudentRecord.task_id=='ops-t00',StudentRecord.student_id=='ops-s2'));db.add(Attempt(id='ops-unverified',record_id=rid,question=3,answer='两边相乘',reason='未给出具体数值',verification={'status':'unverified'},correct=False,created_at=datetime.utcnow()+timedelta(hours=8,minutes=-5)))
 data={'title':'等式性质的天平追问','source':'第十五步自编案例，仅供工程验收','content':'让学生比较只改变左边和两边一起增加的区别。','grade':'七年级','subject':'数学','knowledgeIds':['ops-kp'],'experience':{'goal':'用相等关系解释共同运算','difficulty':'仅对右边运算','introduction':'比较两种天平变化'},'references':[]}
 db.add(TeachingCase(id='ops-case',title=data['title'],content=data['content'],source=data['source'],status='published'));db.flush();db.add(CaseVersion(id='ops-case-v1',case_id='ops-case',number=1,data=data))
 db.add(ModelJob(id='job-ops-failure',owner_id='ops-admin',capability='text',request_key='ops-fail',input_hash='e'*64,input={'prompt':'为什么两边应一起变化'},status='failed',error='验收夹具：外部服务暂时不可用',step='失败',attempt_number=1))
 for i,(sid,status) in enumerate([('ops-s0','pending'),('ops-s1','replied'),('ops-s2','closed')]):db.add(SupportIssue(id='ops-issue'+str(i),owner_id=sid,task_id='ops-t00',category='learning',text=['为什么同时加3？','除数可以为0吗？','括号怎么处理？'][i],status=status,reply='先确认除数不为0' if i==1 else '',resolved=i>0,created_at=now(),updated_at=now()))
 db.add(SupportIssue(id='ops-system',owner_id='ops-s0',category='system',text='反馈入口刷新状态核对',status='pending',created_at=now(),updated_at=now()))
p=Path('/tmp/sczx-step15/browser-private.json');p.write_text(json.dumps({'database':name,'databaseUrl':os.environ['SCZX_DATABASE_URL'],'password':password,'fixture':fx},ensure_ascii=False));p.chmod(0o600);print(name)
