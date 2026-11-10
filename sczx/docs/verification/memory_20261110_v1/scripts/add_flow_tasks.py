import os,sys,json,copy
from pathlib import Path
f=json.loads(Path('/tmp/sczx-step14/browser-private.json').read_text());os.environ['SCZX_DATABASE_URL']=f['url'];sys.path.insert(0,'backend-business')
from sczx_business.database import SessionLocal,engine
from sczx_business.models import Lesson,LessonContent,LessonVersion,LearningTask,ClassMember
from sczx_business.teaching import assign
from sqlalchemy import select
assert engine.url.database.startswith('sczx_test_')
with SessionLocal.begin() as db:
 for suffix,title,kp in [('b','等式性质的后续课时','browser-kp'),('c','含括号方程的前置检查','memory-kp-inverse')]:
  lid='memory-flow-lesson-'+suffix;tid='memory-task-'+suffix
  if db.get(LearningTask,tid):continue
  source=db.get(LearningTask,'browser-t00');data=copy.deepcopy(source.snapshot.get('lessonSnapshot') or f['data']);data.update(title=title,knowledgeIds=[kp],prerequisiteIds=['browser-kp'] if suffix=='c' else ['browser-base'])
  for q in data['questions']:q['knowledgeIds']=[kp]
  db.add(Lesson(id=lid,course_id='browser-course',title=title,position=5 if suffix=='b' else 6));db.flush();db.add(LessonContent(lesson_id=lid,status='published',reviewed=True));db.add(LessonVersion(id=lid+'-v1',lesson_id=lid,number=1,data=data));db.flush()
  task=LearningTask(id=tid,classroom_id='browser-c0',teacher_id='teaching-t1',lesson_id=lid,title=title,snapshot={**copy.deepcopy(data),'lessonSnapshot':{**copy.deepcopy(data),'versionId':lid+'-v1'}},questions=copy.deepcopy(data['questions']),due_date='');db.add(task);db.flush()
  for m in db.scalars(select(ClassMember).where(ClassMember.classroom_id=='browser-c0')).all():assign(db,task,m.student_id)
print('Added new immutable flow tasks: B shares A knowledge; C depends on A. No prior snapshot modified.')
