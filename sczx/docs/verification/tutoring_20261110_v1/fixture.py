import os,sys,json,uuid,secrets,subprocess,copy
from pathlib import Path
from sqlalchemy import create_engine,text,select
from sqlalchemy.engine import URL
root=URL.create('mysql+pymysql',username='root',database='mysql',query={'unix_socket':'/tmp/sczx-mysql.sock'});name='sczx_test_tutoring_browser_'+uuid.uuid4().hex[:6]
with create_engine(root).connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4'))
os.environ['SCZX_DATABASE_URL']=root.set(database=name).render_as_string(hide_password=False)
subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd='backend-business',check=True,capture_output=True)
sys.path[:0]=['backend-business','backend-business/tests']
from test_teaching_mysql import create_accounts,fixture
from sczx_business.database import SessionLocal
from sczx_business.models import Account,Course,Lesson,LessonVersion,LessonContent,KnowledgePoint,LearningTask,ClassMember,StudentRecord,TeachingCase,CaseVersion
password=secrets.token_urlsafe(24);create_accounts(password);fx=fixture('browser')
with SessionLocal.begin() as db:
 point=db.get(KnowledgePoint,'browser-kp');point.prerequisites=['browser-base'];db.add(KnowledgePoint(id='browser-base',name='相等关系与基本运算',aliases=['数量相等'],prerequisites=[]));db.flush()
 db.add(Lesson(id='browser-lesson-two',course_id='browser-course',title='用逆运算解简单方程',position=2));db.flush()
 data=copy.deepcopy(fx['data']);data.update(title='用逆运算解简单方程',goal='用共同的逆运算消去常数，比较两边结果。',knowledgeIds=['browser-base'],prerequisiteIds=[],caseId=None,caseVersionId=None)
 for q in data['questions']:q['knowledgeIds']=['browser-base']
 db.add(LessonContent(lesson_id='browser-lesson-two',draft=None,status='published',reviewed=True));db.add(LessonVersion(id='browser-version-two',lesson_id='browser-lesson-two',number=1,data=data));db.flush()
 for ident in fx['tasks'][4:]:
  task=db.get(LearningTask,ident);task.lesson_id='browser-lesson-two';task.title=data['title'];task.snapshot={**copy.deepcopy(data),'lessonSnapshot':{**data,'versionId':'browser-version-two'}};task.questions=copy.deepcopy(data['questions'])
 for i,(title,content) in enumerate([('天平共同变化','用天平比较两边同时加入相同砝码后的数量，追问只动一边会怎样。'),('相等关系小检查','先比较两组数量是否相同，再比较同时增加相同数量后的关系。'),('逆运算对比','对照同时加与只加一边；用另一组数值举例，再返回原题解释。'),('非零除数条件','讨论等式两边同除一个非零数，区分乘零丢失信息与除零未定义。')]):
  ident='tutor-case-'+str(i);db.add(TeachingCase(id=ident,title=title,content=content,source='项目自编验收材料',status='published'));db.flush();db.add(CaseVersion(id='tutor-case-version-'+str(i),case_id=ident,number=1,data={'title':title,'content':content,'source':'项目自编验收材料','author':'','grade':'七年级','subject':'数学','knowledgeIds':['browser-kp' if i!=1 else 'browser-base'],'experience':{},'references':[],'legacy':True}))
 # Student10 gets one historical task, then leaves; do not remove any record.
 db.add(ClassMember(classroom_id=fx['classes'][0],student_id='teaching-s10'));db.flush()
 from sczx_business.teaching import assign
 assign(db,db.get(LearningTask,fx['tasks'][0]),'teaching-s10');db.flush();db.delete(db.get(ClassMember,(fx['classes'][0],'teaching-s10')))
fx['lessonTwo']='browser-lesson-two';path=Path('/tmp/sczx-step12/browser-private.json');path.write_text(json.dumps({'url':os.environ['SCZX_DATABASE_URL'],'password':password,**fx},ensure_ascii=False));path.chmod(0o600);print('Isolated tutoring browser dataset:',name)
