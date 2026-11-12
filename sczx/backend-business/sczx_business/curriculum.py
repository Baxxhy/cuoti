"""课程内容、知识依赖和不可变课时版本。"""
import copy
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from .database import get_db
from .knowledge_validation import KnowledgeCatalogInput, validate_catalog
from .models import Course, CourseUnit, Lesson, LessonContent, LessonVersion, KnowledgePoint
from .library import uid, current_case
from .library_routes import account
from .math_tools import solve_text_equation, compare_equivalence
router=APIRouter(prefix='/api/curriculum')


def published_lesson(db, lesson_id, version_id=None):
    content=db.get(LessonContent,lesson_id)
    version=db.get(LessonVersion,version_id) if version_id else db.scalar(select(LessonVersion).where(LessonVersion.lesson_id==lesson_id).order_by(LessonVersion.number.desc()).limit(1))
    if not version or version.lesson_id!=lesson_id or (not version_id and (not content or content.status!='published')):return None
    return {**copy.deepcopy(version.data),'unitId':db.get(Lesson,lesson_id).unit_id,'lessonId':lesson_id,'versionId':version.id,'version':version.number,'publishedAt':version.published_at.isoformat()+'Z'}


def student_content(data):
    result=copy.deepcopy(data)
    sources={b.get('id'):b for b in (data.get('lessonSnapshot') or {}).get('blocks',[])}
    for q in result.get('questions',[]):
        for key in ('answer','hint','explanation','feedback','teacherNote','verification'):q.pop(key,None)
    for b in result.get('blocks',[]):
        source=sources.get(b.get('id'),{}) if b.get('agentJobId') else {}
        for field,public in [('studentContent','content'),('studentTitle','title')]:
            value=b.get(field,source.get(field,source.get(public)))
            if isinstance(value,str) and value.strip():b[public]=value
            b.pop(field,None)
        for key in ('teacherNote','teacherQuestion','studentResponse','adjustment','agentEvidence','agentJobId'):b.pop(key,None)
    result.pop('planningDetails',None)
    result.pop('caseSnapshot',None)
    return result


def lesson_json(db,lesson,admin=False):
    content=db.get(LessonContent,lesson.id)
    published=published_lesson(db,lesson.id)
    versions=db.scalars(select(LessonVersion).where(LessonVersion.lesson_id==lesson.id).order_by(LessonVersion.number.desc())).all() if admin else []
    return {'id':lesson.id,'title':lesson.title,'courseId':lesson.course_id,'unitId':lesson.unit_id,'position':lesson.position,'status':content.status if content else 'draft','published':published if admin else student_content(published) if published else None,**({'draft':content.draft if content else None,'lastPublished':published_lesson(db,lesson.id,versions[0].id) if versions and not published else None,'reviewed':content.reviewed if content else False,'versions':[{'id':v.id,'number':v.number} for v in versions]} if admin else {})}


def content_errors(db,data):
    errors=[]
    for k in ('title','goal','grade','subject','source'):
        if not isinstance(data.get(k),str) or not data[k].strip():errors.append(f'{k}：请填写内容')
    if not isinstance(data.get('duration'),(int,float)) or not 1<=data['duration']<=240:errors.append('duration：时长应为1至240分钟')
    ids={p.id for p in db.scalars(select(KnowledgePoint)).all()}
    for k in ('knowledgeIds','prerequisiteIds'):
        if not isinstance(data.get(k,[]),list) or any(i not in ids for i in data.get(k,[])):errors.append(k+'：存在无效知识点')
    blocks=data.get('blocks',[]);questions=data.get('questions',[])
    if not isinstance(blocks,list) or not blocks:errors.append('blocks：至少需要一个内容块');blocks=[]
    if not isinstance(questions,list):errors.append('questions：题目格式无效');questions=[]
    blockids=set();qids=set();checks=0
    for index,q in enumerate(questions):
        if not isinstance(q,dict):errors.append(f'题目{index+1}格式无效');continue
        if not q.get('id') or q['id'] in qids:errors.append(f'题目{index+1}：ID缺失或重复')
        qids.add(q.get('id'))
        if q.get('kind')=='check':checks+=1
        if q.get('kind') not in ('practice','check','replacement'):errors.append(f'题目{index+1}：用途无效')
        if not q.get('prompt') or not q.get('answer') or not q.get('equation') or not q.get('hint'):errors.append(f'题目{index+1}：请填写题干、算式、答案和提示')
        if re.search(r'/\s*\(?\s*0\s*\)?(?:\s|$|[+\-*/=])',str(q.get('equation',''))):errors.append(f'题目{index+1}：除数不能为零')
        solved,checked=solve_text_equation(str(q.get('equation','')))
        equal,parsed=compare_equivalence(solved.split('=',1)[-1],str(q.get('answer',''))) if checked and ',' not in solved else (False,False)
        if not checked or not parsed or not equal:errors.append(f'题目{index+1}：方程与答案无法核对，请使用可验证的单解方程')
    for index,b in enumerate(blocks):
        if not isinstance(b,dict):errors.append(f'内容块{index+1}格式无效');continue
        if not b.get('id') or b['id'] in blockids:errors.append(f'内容块{index+1}：ID缺失或重复')
        blockids.add(b.get('id'))
        if b.get('type') not in ('explanation','example','activity','practice','check'):errors.append(f'内容块{index+1}：不支持的类型')
        if not b.get('title') or not str(b.get('content','')).strip():errors.append(f'内容块{index+1}：标题或正文为空')
        for field in ('studentContent','studentTitle'):
            if field in b and (not isinstance(b[field],str) or not b[field].strip()):errors.append(f'内容块{index+1}：学生标题或正文为空')
        if any(q not in qids for q in b.get('questionIds',[])):errors.append(f'内容块{index+1}：引用题目不存在')
        if b.get('type') in ('practice','check') and not b.get('questionIds'):errors.append(f'内容块{index+1}：请选择题目')
        if b.get('type')=='activity':
            a=b.get('activity') or {}
            try:
                from .visualization import specification
                specification(a)
            except (ValueError,TypeError):errors.append(f'内容块{index+1}：互动参数不符合VisualizationSpec')
    if not checks:errors.append('questions：至少需要一道独立检查题')
    if data.get('caseId'):
        if not current_case(db,data['caseId'],data.get('caseVersionId')):errors.append('caseId：案例已撤回或版本不存在')
    from .math_conditions import inspect_conditions
    errors.extend(i["message"] for i in inspect_conditions(data)["issues"])
    return list(dict.fromkeys(errors))


@router.get('/courses')
def catalog(request:Request,db=Depends(get_db)):
    user=account(request,db);admin=user.role=='admin';result=[]
    for course in db.scalars(select(Course).order_by(Course.id)).all():
        units=[]
        for unit in db.scalars(select(CourseUnit).where(CourseUnit.course_id==course.id).order_by(CourseUnit.position)).all():
            lessons=[lesson_json(db,l,admin) for l in db.scalars(select(Lesson).where(Lesson.unit_id==unit.id).order_by(Lesson.position)).all()]
            if not admin:lessons=[l for l in lessons if l['published']]
            if admin or lessons:
                from .unit_learning import lesson_order
                order=lesson_order(db,unit);planned=bool((course.metadata_json or {}).get('unitPlans',{}).get(unit.id));units.append({'id':unit.id,'title':unit.title,'position':unit.position,'lessonOrder':order,'hasPlan':planned,'lessons':sorted(lessons,key=lambda l:(order.index(l['id']) if l['id'] in order else len(order),l['position'],l['id']))})
        if admin or units:result.append({'id':course.id,'title':course.title,'grade':course.grade,'metadata':course.metadata_json or {},'units':units})
    return sorted(result,key=lambda c:((c['metadata'] or {}).get('position') or 0,c['id']))


@router.post('/courses',status_code=201)
def create_course(body:dict,request:Request,db=Depends(get_db)):
    account(request,db,True)
    title=str(body.get('title','')).strip()
    if not title:raise HTTPException(422,'请填写课程名称。')
    row=Course(id=uid('course'),title=title[:200],grade=str(body.get('grade','七年级'))[:80],metadata_json={'subject':body.get('subject','数学')});db.add(row);db.commit();return {'id':row.id}


@router.put('/courses/{ident}')
def edit_course(ident:str,body:dict,request:Request,db=Depends(get_db)):
    account(request,db,True);row=db.get(Course,ident)
    if not row:raise HTTPException(404,'课程不存在。')
    if not str(body.get('title','')).strip():raise HTTPException(422,'请填写课程名称。')
    metadata=body.get('metadata') or {}
    if not isinstance(metadata,dict):raise HTTPException(422,'课程元数据无效。')
    plans=metadata.get('unitPlans',{})
    if not isinstance(plans,dict):raise HTTPException(422,'单元顺序格式无效。')
    for unit_id,order in plans.items():
        unit=db.get(CourseUnit,unit_id)
        if not unit or unit.course_id!=ident or not isinstance(order,list) or any(not isinstance(i,str) for i in order) or len(order)!=len(set(order)) or any(not db.get(Lesson,l) or db.get(Lesson,l).unit_id!=unit_id for l in order):raise HTTPException(422,'单元顺序必须引用本单元真实课时且不能重复。')
    row.title=str(body['title'])[:200];row.grade=str(body.get('grade',''))[:80];row.metadata_json=body.get('metadata') or {};db.commit();return {'saved':True}


@router.post('/units',status_code=201)
def create_unit(body:dict,request:Request,db=Depends(get_db)):
    account(request,db,True)
    if not db.get(Course,body.get('courseId')) or not str(body.get('title','')).strip():raise HTTPException(422,'请选择课程并填写单元名称。')
    row=CourseUnit(id=uid('unit'),course_id=body['courseId'],title=body['title'][:200],position=int(body.get('position',0)));db.add(row);db.commit();return {'id':row.id}


@router.put('/units/{ident}')
def edit_unit(ident:str,body:dict,request:Request,db=Depends(get_db)):
    account(request,db,True);row=db.get(CourseUnit,ident)
    if not row:raise HTTPException(404,'单元不存在。')
    if not str(body.get('title','')).strip():raise HTTPException(422,'请填写单元名称。')
    row.title=str(body['title'])[:200];row.position=int(body.get('position',0));db.commit();return {'saved':True}


@router.post('/lessons',status_code=201)
def create_lesson(body:dict,request:Request,db=Depends(get_db)):
    account(request,db,True);unit=db.get(CourseUnit,body.get('unitId'))
    if not unit or not str(body.get('title','')).strip():raise HTTPException(422,'请选择单元并填写课时名称。')
    row=Lesson(id=uid('lesson'),course_id=unit.course_id,unit_id=unit.id,title=body['title'][:200],position=int(body.get('position',0)));db.add(row);db.flush()
    db.add(LessonContent(lesson_id=row.id,draft={'title':row.title,'grade':'七年级','subject':'数学','source':'','goal':'','duration':30,'knowledgeIds':[],'prerequisiteIds':[],'blocks':[],'questions':[]}));db.commit();return lesson_json(db,row,True)


@router.get('/lessons/{ident}')
def lesson_detail(ident:str,request:Request,versionId:str|None=None,db=Depends(get_db)):
    user=account(request,db);lesson=db.get(Lesson,ident)
    if not lesson:raise HTTPException(404,'课时不存在。')
    if user.role=='admin' and not versionId:return lesson_json(db,lesson,True)
    data=published_lesson(db,ident,versionId)
    if not data:raise HTTPException(404,'课时尚未发布或已停用。')
    return data if user.role=='teacher' else student_content(data)


@router.put('/lessons/{ident}')
def save_lesson(ident:str,body:dict,request:Request,db=Depends(get_db)):
    account(request,db,True);lesson=db.get(Lesson,ident);content=db.get(LessonContent,ident)
    if not lesson or not content:raise HTTPException(404,'课时不存在。')
    if 'data' not in body and 'position' in body:
        lesson.position=int(body['position']);db.commit();return lesson_json(db,lesson,True)
    data=body.get('data')
    if not isinstance(data,dict) or not isinstance(data.get('blocks',[]),list) or not isinstance(data.get('questions',[]),list):raise HTTPException(422,'课时格式无效。')
    data=copy.deepcopy(data);data.pop('verification',None);data.pop('reviewRecord',None)
    if content.draft!=data:content.reviewed=False
    content.draft=data
    lesson.position=int(body.get('position',lesson.position))
    # Published catalog title belongs to the published version, not an unpublished draft.
    if content.status!='published':lesson.title=str(data.get('title',lesson.title))[:200]
    db.commit();return lesson_json(db,lesson,True)


@router.post('/lessons/{ident}/{action}')
def lesson_action(ident:str,action:str,request:Request,db=Depends(get_db)):
    account(request,db,True);content=db.scalar(select(LessonContent).where(LessonContent.lesson_id==ident).with_for_update());lesson=db.get(Lesson,ident)
    if not content:raise HTTPException(404,'课时不存在。')
    if action=='revise':
        if content.draft is None:content.draft=published_lesson(db,ident) or published_lesson(db,ident,db.scalar(select(LessonVersion.id).where(LessonVersion.lesson_id==ident).order_by(LessonVersion.number.desc()).limit(1)))
        content.reviewed=False
    elif action in ('verify','review','publish'):
        if content.draft is None and action=='publish' and content.status=='published':db.commit();return lesson_json(db,lesson,True)
        if not content.draft:raise HTTPException(422,'请先创建课时草稿。')
        errors=content_errors(db,content.draft)
        if errors:raise HTTPException(422,'；'.join(errors))
        if action=='review':
            from .math_conditions import inspect_conditions
            actor=account(request,db,True);data=copy.deepcopy(content.draft);data['reviewRecord']={'actorId':actor.id,'at':datetime.utcnow().isoformat()+'Z','scope':'内容、条件与数量关系人工核对','conditions':inspect_conditions(data)};content.draft=data;content.reviewed=True
        if action=='publish':
            if not content.reviewed:raise HTTPException(422,'请先完成内容和数学核对。')
            data=copy.deepcopy(content.draft)
            if data.get('caseId'):data['caseSnapshot']=current_case(db,data['caseId'],data.get('caseVersionId'));data['caseVersionId']=data['caseSnapshot']['versionId']
            data['verification']={'status':'verified','scope':'所列单解方程与参考答案；正文和教学方法仍经人工核对'}
            for k in ('versionId','version','publishedAt','lessonId'):data.pop(k,None)
            last=db.scalar(select(LessonVersion).where(LessonVersion.lesson_id==ident).order_by(LessonVersion.number.desc()).with_for_update().limit(1))
            db.add(LessonVersion(id=uid('lessonversion'),lesson_id=ident,number=last.number+1 if last else 1,data=data));content.status='published';content.draft=None;lesson.title=data['title']
    elif action=='withdraw':content.status='withdrawn'
    else:raise HTTPException(404,'操作不存在。')
    db.commit();return lesson_json(db,lesson,True)


@router.get('/knowledge')
def knowledge(request:Request,db=Depends(get_db)):
    account(request,db);return [{'id':p.id,'name':p.name,'aliases':p.aliases or [],'prerequisites':p.prerequisites} for p in db.scalars(select(KnowledgePoint)).all()]


@router.put('/knowledge')
def save_knowledge(body:KnowledgeCatalogInput,request:Request,db=Depends(get_db)):
    account(request,db,True)
    points=[p.model_dump() for p in body.points]
    try:validate_catalog(points)
    except ValueError as error:raise HTTPException(422,str(error)) from None
    graph={p['id']:p['prerequisites'] for p in points}
    if any(p.id not in graph for p in db.scalars(select(KnowledgePoint)).all()):raise HTTPException(422,'已存在知识点需保留，避免历史引用丢失。')
    for p in points:
        row=db.get(KnowledgePoint,p['id'])
        if not row:row=KnowledgePoint(id=p['id']);db.add(row)
        row.name=p['name'][:160];row.prerequisites=p.get('prerequisites',[]);row.aliases=[a.strip() for a in p.get('aliases',[])]
    db.commit();return knowledge(request,db)


def apply_template(db,lesson):
    version=published_lesson(db,lesson.id)
    if not version:return {'lessonId':lesson.id,'caseId':None,'caseSnapshot':None,'lessonSnapshot':None,'goal':'','studentBase':'','dueDate':'','blocks':[],'questions':[]}
    return {'lessonId':lesson.id,'caseId':version.get('caseId'),'caseSnapshot':version.get('caseSnapshot'),'lessonSnapshot':version,'goal':version['goal'],'studentBase':'','dueDate':'','blocks':version['blocks'],'questions':version['questions']}


def completion_missing(task,record,attempts):
    if not task.snapshot.get('lessonSnapshot'):return []
    done=(record.drafts or {}).get('blocks',{})
    required=[b for b in task.snapshot.get('blocks',[]) if b.get('required')]
    missing=[]
    for b in required:
        if b.get('type') in ('practice','check'):
            ids=b.get('questionIds',[])
            answered={task.questions[a.question].get('id') for a in attempts if 0<=a.question<len(task.questions)}
            if any(i not in answered for i in ids):missing.append(b['title'])
        elif not done.get(b['id'],{}).get('completed'):missing.append(b['title'])
    return missing


def assess_question(answer,question):
    from .grading import assess
    result=assess(answer,question.get('answer',''),question.get('equation',''))
    if result['status']=='unverified':result['message']='暂时无法核对该输入，请用可读数学表达式填写；解释仍保留供教师查看。'
    elif result['correct']:result['message']='数值或表达式正确。解释是否充分由教师结合过程核对。'
    elif re.search(r'/\s*0(?:\D|$)',answer):result['message']='除数不能为零，请检查运算条件。'
    else:
        result['message']=next((f['message'] for f in question.get('feedback',[]) if f.get('answer')==answer),'请检查左右两边是否进行了相同运算，再核对计算。')
    if question.get('requiresTeacherReview') and result['correct']:
        result={'status':'unverified','correct':False,'numericVerification':result,'message':'数值与参考方程相符；设元、列式和情境条件仍需教师核对。','scope':'应用题文字建模不自动判定正确'}
    return result


@router.post('/tasks/{task_id}/questions/{index}/hint')
def hint(task_id:str,index:int,request:Request,db=Depends(get_db)):
    from .models import LearningTask,StudentRecord,HelpRecord,Attempt
    user=account(request,db)
    from .teaching import ensure_write
    ensure_write(db,user,task_id)
    record=db.scalar(select(StudentRecord).where(StudentRecord.task_id==task_id,StudentRecord.student_id==user.id));task=db.get(LearningTask,task_id)
    if not record or not task or not 0<=index<len(task.questions):raise HTTPException(404,'题目不存在。')
    text=task.questions[index].get('hint','请检查等式两边是否进行相同运算。')
    db.add(HelpRecord(id=uid('help'),record_id=record.id,question=index,kind='提示',message=text,attempt_number=len(db.scalars(select(Attempt).where(Attempt.record_id==record.id)).all())+1));db.commit()
    return {'hint':text,'questionId':task.questions[index].get('id')}
