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
from .docx_export import build_docx

def export_data(db,user,lesson_id,version_id):
    _,data=selected(db,user,lesson_id,version_id)
    from .models import ModelJob
    sources={};cases={}
    for block in data.get('blocks',[]):
        job=db.get(ModelJob,block.get('agentJobId')) if block.get('agentJobId') else None
        if job and job.owner_id==user.id:
            for evidence in (job.result or {}).get('evidence',[]):
                if evidence['id'] in block.get('agentEvidence',[]) and evidence.get('kind')=='material':
                    sources[evidence['id']]=evidence
                    for case in (job.result or {}).get('cases',[]):
                        if case['versionId']==evidence.get('caseVersionId'):cases[case['versionId']]=case
    data['agentSources']=list(sources.values());data['agentCases']=list(cases.values())
    return data

@router.get('/{lesson_id}/export-options')
def export_options(lesson_id:str,request:Request,versionId:str|None=None,db=Depends(get_db)):
    from .teaching_quality import editorial_marks,cleaned_copy
    data=export_data(db,account(request,db),lesson_id,versionId);clean=cleaned_copy(data)
    marks=editorial_marks(data)
    for item in marks:
        node=clean
        for key in item['field'].split('.'):node=node[int(key)] if isinstance(node,list) else node.get(key,'')
        item['proposed']=node
    return {'revision':data['revision'],'markers':marks,'defaultMode':'formal'}

@router.get('/{lesson_id}/export')
def export(lesson_id:str,request:Request,versionId:str|None=None,mode:str='formal',cleanEditorial:bool=False,db=Depends(get_db)):
    if mode not in ('formal','trace'):raise HTTPException(422,'请选择正式教案或完整溯源版。')
    data=export_data(db,account(request,db),lesson_id,versionId)
    return Response(build_docx(data,mode,cleanEditorial),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':'attachment; filename="lesson-plan-'+mode+'.docx"'})
