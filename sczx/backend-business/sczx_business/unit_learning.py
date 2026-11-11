"""Unit continuity derived solely from existing assigned tasks and records."""
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from .database import get_db
from .models import CourseUnit,Course,Lesson,LearningTask,StudentRecord
from .teaching import user_for,member,personal_status,cutoff,iso
router=APIRouter(prefix='/api/units')

def lesson_order(db,unit):
    course=db.get(Course,unit.course_id)
    ids=(course.metadata_json or {}).get('unitPlans',{}).get(unit.id,[])
    actual={l.id for l in db.scalars(select(Lesson).where(Lesson.unit_id==unit.id))}
    return [i for i in ids if i in actual] if ids else [l.id for l in db.scalars(select(Lesson).where(Lesson.unit_id==unit.id).order_by(Lesson.position,Lesson.id))]

@router.get('/{ident}/progress')
def progress(ident:str,request:Request,classId:str|None=None,db=Depends(get_db)):
    user=user_for(request,db);unit=db.get(CourseUnit,ident)
    if not unit or user.role!='student':raise HTTPException(404,'没有找到本人的单元学习。')
    if classId:
        own=db.scalar(select(StudentRecord.id).join(LearningTask).where(StudentRecord.student_id==user.id,LearningTask.classroom_id==classId).limit(1))
        if not own and not member(db,classId,user.id):raise HTTPException(404,'没有找到本人的班级单元。')
    from .curriculum import published_lesson
    rows=[]
    for lesson_id in lesson_order(db,unit):
        published=published_lesson(db,lesson_id)
        # Exams, group practice and live history share a lesson ID, but do not
        # replace the student's assigned curriculum lesson or its completion.
        query=select(LearningTask,StudentRecord).join(StudentRecord,StudentRecord.task_id==LearningTask.id).where(LearningTask.lesson_id==lesson_id,LearningTask.source.in_(['published','legacy-demo']),StudentRecord.student_id==user.id).order_by(LearningTask.published_at.desc(),LearningTask.id)
        if classId:query=query.where(LearningTask.classroom_id==classId)
        pairs=db.execute(query).all()
        writable=[(t,r) for t,r in pairs if member(db,t.classroom_id,user.id)]
        chosen=(writable or pairs)[0] if pairs else None
        if not published and not chosen:continue
        task,record=chosen if chosen else (None,None);active=bool(chosen and member(db,task.classroom_id,user.id))
        rows.append({'lessonId':lesson_id,'title':task.title if task else published['title'],'taskId':task.id if task else None,'versionId':(task.snapshot.get('lessonSnapshot') or {}).get('versionId') if task else published['versionId'],'classId':task.classroom_id if task else None,'completed':bool(record and record.completed),'readOnly':bool(record and not active),'status':personal_status(record,cutoff(task.due_date),active) if record else '尚未分配','submittedAt':iso(record.submitted_at) if record else None,'target':'/learn?task='+task.id if task else None})
    return {'id':unit.id,'title':unit.title,'lessons':rows,'completed':sum(r['completed'] for r in rows),'assigned':sum(bool(r['taskId']) for r in rows),'total':len(rows),'scope':'本人已分配任务；完成不等于独立正确'}
