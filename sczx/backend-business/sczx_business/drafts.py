"""Existing teacher draft writes share one optimistic revision and history boundary."""
import copy,io,uuid
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import Response
from sqlalchemy import select
from .database import get_db
from .models import LessonDraft,LessonDraftVersion
from .library_routes import account
router=APIRouter(prefix='/api/preparation')
FIELDS={'goal':'goal','studentBase':'student_base','dueDate':'due_date','blocks':'blocks','questions':'questions','caseId':'case_id','caseSnapshot':'case_snapshot','lessonSnapshot':'lesson_snapshot','planningDetails':'planning_details'}
def snapshot(row):
    return {'id':row.id,'lessonId':row.lesson_id,**{k:copy.deepcopy(getattr(row,v)) for k,v in FIELDS.items()},'revision':row.revision or 0}
def owned(db,user,lesson_id,lock=False):
    if user.role!='teacher':raise HTTPException(403,'请使用教师账号。')
    stmt=select(LessonDraft).where(LessonDraft.teacher_id==user.id,LessonDraft.lesson_id==lesson_id)
    return db.scalar(stmt.with_for_update() if lock else stmt)
def check_revision(row,revision):
    if (row.revision or 0)!=revision:raise HTTPException(409,'教案已在其他页面保存。请保留本地修改，重新读取最新版本后再编辑。')
def checkpoint(db,row,reason):
    db.flush()
    row.revision=(row.revision or 0)+1
    db.add(LessonDraftVersion(id='dv-'+uuid.uuid4().hex,draft_id=row.id,number=row.revision,data=snapshot(row),reason=reason))
def preserve_original(db,row):
    if not row.revision:checkpoint(db,row,'原有教案备份')
def normalized_details(db,value):
    if not value:return {}
    if not isinstance(value,dict):raise HTTPException(422,'教学安排格式无效。')
    result={}
    for key in ('focus','difficulty','teacherQuestions','studentResponses','adjustments'):
        text=value.get(key,'')
        if not isinstance(text,str) or len(text)>6000:raise HTTPException(422,'教学安排文本无效。')
        result[key]=text
    from .library import current_case
    refs=value.get('references',[])
    if not isinstance(refs,list) or len(refs)>8:raise HTTPException(422,'最多选择8个参考案例。')
    result['references']=[]
    for ref in refs:
        if not isinstance(ref,dict) or not ref.get('versionId'):raise HTTPException(422,'请选择固定案例版本。')
        item=current_case(db,ref.get('id'),ref['versionId'])
        if not item:raise HTTPException(422,'参考案例版本不存在。')
        if item['versionId'] not in {x['versionId'] for x in result['references']}:result['references'].append(item)
    return result
@router.get('/{lesson_id}/versions')
def versions(lesson_id:str,request:Request,db=Depends(get_db)):
    row=owned(db,account(request,db),lesson_id)
    if not row:return []
    return [{'id':v.id,'number':v.number,'reason':v.reason,'createdAt':v.created_at.isoformat()+'Z'} for v in db.scalars(select(LessonDraftVersion).where(LessonDraftVersion.draft_id==row.id).order_by(LessonDraftVersion.number.desc()))]
def selected(db,user,lesson_id,version_id=None,lock=False):
    row=owned(db,user,lesson_id,lock)
    if not row:raise HTTPException(404,'请先保存教案。')
    if not version_id:return row,snapshot(row)
    version=db.get(LessonDraftVersion,version_id)
    if not version or version.draft_id!=row.id:raise HTTPException(404,'教案版本不存在。')
    return row,copy.deepcopy(version.data)
@router.get('/{lesson_id}/versions/{version_id}')
def detail(lesson_id:str,version_id:str,request:Request,db=Depends(get_db)):
    return selected(db,account(request,db),lesson_id,version_id)[1]
@router.post('/{lesson_id}/restore')
def restore(lesson_id:str,body:dict,request:Request,db=Depends(get_db)):
    row,data=selected(db,account(request,db),lesson_id,body.get('versionId'),True)
    if not body.get('confirmed'):raise HTTPException(422,'请确认恢复将替换当前教案。')
    check_revision(row,body.get('revision'))
    preserve_original(db,row)
    for key,field in FIELDS.items():setattr(row,field,copy.deepcopy(data.get(key)))
    checkpoint(db,row,'恢复历史版本');db.commit();return snapshot(row)
def build_docx(data):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt
    doc=Document();style=doc.styles['Normal'];style.font.name='Microsoft YaHei';style.font.size=Pt(11)
    style.element.rPr.rFonts.set(qn('w:eastAsia'),'微软雅黑')
    lesson=data.get('lessonSnapshot') or {};details=data.get('planningDetails') or {}
    doc.add_heading(lesson.get('title','教案'),0)
    doc.add_paragraph(f"{lesson.get('grade','')} · {lesson.get('subject','')}　教案版本 {data.get('revision',0)} / 来源课时 v{lesson.get('version','未记录')}")
    def section(title,text):
        if text:doc.add_heading(title,1);[doc.add_paragraph(line) for line in str(text).splitlines()]
    section('教学目标',data.get('goal'));section('学生基础',data.get('studentBase'))
    for key,title in [('focus','教学重点'),('difficulty','教学难点'),('teacherQuestions','教师提问'),('studentResponses','学生可能回应'),('adjustments','教师调整')]:section(title,details.get(key))
    doc.add_heading('教学活动',1)
    for b in data.get('blocks',[]):
        doc.add_heading(b.get('title','活动'),2);doc.add_paragraph(b.get('content',''))
        for key,title in [('teacherQuestion','教师提问'),('studentResponse','学生回应'),('adjustment','调整建议')]:
            if b.get(key):doc.add_paragraph(title+'：'+b[key])
    doc.add_heading('例题与练习',1)
    for i,q in enumerate(data.get('questions',[]),1):
        doc.add_heading(f"{i}. {q.get('prompt','练习')}",2)
        for key,title in [('equation','题目'),('answer','参考答案'),('hint','提示'),('explanation','讲解')]:
            if q.get(key):doc.add_paragraph(title+'：'+str(q[key]))
    refs=[data.get('caseSnapshot'),*details.get('references',[])]
    seen=set()
    for c in refs:
        if not c or c.get('versionId') in seen:continue
        seen.add(c.get('versionId'));doc.add_heading('参考案例：'+c.get('title',''),1)
        doc.add_paragraph(f"版本 v{c.get('version','')}　{c.get('source','')}")
        for ref in c.get('references',[]):doc.add_paragraph(' · '.join(str(ref.get(k,'')) for k in ('materialTitle','label','quote') if ref.get(k)))
    for ref in data.get('agentSources',[]):
        doc.add_heading('生成内容参考原文',2);doc.add_paragraph(' · '.join(str(ref.get(k,'')) for k in ('title','label','content') if ref.get(k)))
    output=io.BytesIO();doc.save(output);return output.getvalue()
@router.get('/{lesson_id}/export')
def export(lesson_id:str,request:Request,versionId:str|None=None,db=Depends(get_db)):
    _,data=selected(db,account(request,db),lesson_id,versionId)
    from .models import ModelJob
    sources={}
    for block in data.get('blocks',[]):
        job=db.get(ModelJob,block.get('agentJobId')) if block.get('agentJobId') else None
        if job and job.owner_id==account(request,db).id:
            for evidence in (job.result or {}).get('evidence',[]):
                if evidence['id'] in block.get('agentEvidence',[]) and evidence.get('kind')=='material':sources[evidence['id']]=evidence
    data['agentSources']=list(sources.values())
    return Response(build_docx(data),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':'attachment; filename="lesson-plan.docx"'})
