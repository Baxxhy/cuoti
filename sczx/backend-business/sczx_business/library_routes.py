import copy
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy import select, func
from .database import get_db
from .models import FileAsset, SourceMaterial, MaterialUnit, ModelJob, TeachingCase, CaseVersion, CaseDraftContent
from .library import uid, enqueue, reference, validate_references, current_case, draft_json, create_draft, latest_version, published_unit

router = APIRouter(prefix='/api/library')


def account(request, db, admin=False):
    from .main import current_user
    user = current_user(request, db)
    if admin and user.role != 'admin': raise HTTPException(403, '此操作需要管理账号。')
    return user


def unit_json(db, unit):
    job = db.get(ModelJob, unit.job_id) if unit.job_id else None
    return {'id': unit.id, 'materialId': unit.material_id, 'position': unit.position, 'label': unit.label, 'kind': unit.kind, 'text': unit.text, 'originalText': unit.original_text, 'imageUrl': '/api/files/'+unit.image_file_id if unit.image_file_id else None, 'details': unit.details, 'jobId': unit.job_id, 'status': 'ready' if unit.text.strip() else job.status if job else 'empty', 'error': job.error if job else ''}


def material_json(db, material, detail=False):
    units = [unit_json(db, u) for u in db.scalars(select(MaterialUnit).where(MaterialUnit.material_id == material.id).order_by(MaterialUnit.position)).all()]
    job = db.get(ModelJob, material.parse_job_id) if material.parse_job_id else None
    ready = sum(u['status']=='ready' for u in units)
    expected = material.metadata_json.get('expectedUnits',len(units))
    state = 'ready' if units and ready==expected and ((job and job.status=='succeeded') or material.metadata_json.get('curatedSummary')) else 'processing' if (job and job.status in ('queued','running')) or any(u['status'] in ('queued','running') for u in units) else 'partial' if ready else 'failed' if job and job.status=='failed' else 'empty'
    asset = db.get(FileAsset, material.file_id)
    return {'id': material.id, 'title': material.title, 'metadata': material.metadata_json, 'fileId': material.file_id, 'fileName': asset.original_name, 'status': state, 'ready': ready, 'total': expected, 'parseJobId': material.parse_job_id, 'parseStatus': job.status if job else '', 'error': job.error if job else '', **({'units': units} if detail else {})}


@router.get('/materials')
def materials(request: Request, db=Depends(get_db)):
    account(request, db, True)
    return [material_json(db, m) for m in db.scalars(select(SourceMaterial).order_by(SourceMaterial.created_at.desc())).all()]


@router.post('/materials', status_code=201)
async def upload(request: Request, file: UploadFile=File(...), title: str=Form(''), author: str=Form(''), sourceUrl: str=Form(''), sourceNote: str=Form(''), grade: str=Form(''), subject: str=Form(''), db=Depends(get_db)):
    user = account(request, db, True)
    suffix = Path(file.filename or '').suffix.lower()
    types = {'.pdf':'application/pdf', '.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg'}
    if suffix not in types: raise HTTPException(415,'请选择PDF、DOCX、PNG或JPEG。')
    content = await file.read(30*1024*1024+1)
    if not content or len(content)>30*1024*1024: raise HTTPException(413,'文件为空或超过30MB。')
    from .model_jobs import storage_dir
    key = uid('source'); storage_dir().mkdir(parents=True,exist_ok=True); (storage_dir()/key).write_bytes(content)
    asset = FileAsset(id=uid('file'), owner_id=user.id, original_name=Path(file.filename).name[:255], content_type=types[suffix], size=len(content), storage_key=key)
    db.add(asset); db.flush()
    material = SourceMaterial(id=uid('material'), owner_id=user.id, file_id=asset.id, title=(title.strip() or asset.original_name)[:240], metadata_json={'author':author[:200], 'sourceUrl':sourceUrl[:2000], 'sourceNote':sourceNote[:2000], 'grade':grade[:100], 'subject':subject[:100]})
    db.add(material); db.flush()
    job = enqueue(db,user.id,'document_parse',{'materialId':material.id},asset.id); material.parse_job_id=job.id
    db.commit()
    return material_json(db,material,True)


@router.get('/materials/{material_id}')
def material_detail(material_id: str, request: Request, db=Depends(get_db)):
    account(request,db,True); material=db.get(SourceMaterial,material_id)
    if not material: raise HTTPException(404,'材料不存在。')
    return material_json(db,material,True)


@router.put('/materials/{material_id}')
def material_update(material_id: str, body: dict, request: Request, db=Depends(get_db)):
    account(request,db,True); material=db.get(SourceMaterial,material_id)
    if not material: raise HTTPException(404,'材料不存在。')
    material.title=str(body.get('title',material.title))[:240]
    material.metadata_json={**material.metadata_json,**{k:str(body.get('metadata',material.metadata_json).get(k,''))[:2000] for k in ('author','sourceUrl','sourceNote','grade','subject')}}
    db.commit();return material_json(db,material,True)


@router.get('/units/{unit_id}')
def source_unit(unit_id: str, request: Request, db=Depends(get_db)):
    user=account(request,db);unit=db.get(MaterialUnit,unit_id)
    if not unit or (user.role!='admin' and not published_unit(db,unit_id)):raise HTTPException(404,'原文位置不存在或尚未发布。')
    material=db.get(SourceMaterial,unit.material_id)
    return {**unit_json(db,unit),'materialTitle':material.title,'metadata':material.metadata_json,'originalUrl':'/api/files/'+material.file_id}


@router.put('/units/{unit_id}')
def edit_unit(unit_id: str, body: dict, request: Request, db=Depends(get_db)):
    account(request,db,True);unit=db.get(MaterialUnit,unit_id)
    if not unit:raise HTTPException(404,'原文位置不存在。')
    text=body.get('text')
    if not isinstance(text,str) or not text.strip() or len(text)>100000:raise HTTPException(422,'请填写有效原文，最多10万字。')
    if text != unit.text:
        unit.details={**unit.details,'revisions':[*unit.details.get('revisions',[]),{'text':unit.text,'at':datetime.utcnow().isoformat()+'Z'}]}
    unit.text=text;db.commit();return unit_json(db,unit)


@router.post('/extract',status_code=201)
def extract(body: dict, request: Request, db=Depends(get_db)):
    user=account(request,db,True);ids=body.get('unitIds',[])
    if not isinstance(ids,list) or not 1<=len(ids)<=8 or len(set(ids))!=len(ids):raise HTTPException(422,'请选择1至8个原文片段。')
    units=[]
    for ident in ids:
        unit=db.get(MaterialUnit,ident)
        if not unit or not unit.text.strip():raise HTTPException(422,'所选片段未完成识别，请先修订原文。')
        units.append({'id':unit.id,'text':unit.text,'label':unit.label,'materialId':unit.material_id})
    if sum(len(u['text']) for u in units)>24000:raise HTTPException(422,'本次原文超过24000字，请分批整理案例。')
    label='、'.join(dict.fromkeys(db.get(SourceMaterial,u['materialId']).title for u in units))[:160]
    job=enqueue(db,user.id,'case_extract',{'units':units,'label':label});db.commit();return {'jobId':job.id}


@router.get('/cases')
def cases(request: Request, db=Depends(get_db)):
    account(request,db,True)
    return [draft_json(db,c) for c in db.scalars(select(TeachingCase).order_by(TeachingCase.updated_at.desc())).all()]


@router.post('/cases',status_code=201)
def new_case(body: dict, request: Request, db=Depends(get_db)):
    account(request,db,True)
    refs=[]
    for ident in body.get('unitIds',[])[:8]:
        unit=db.get(MaterialUnit,ident)
        if unit and unit.text.strip():refs.append(reference(db,unit))
    draft=create_draft(db,{'title':body.get('title','新教学案例'),'content':'','source':'','author':'','grade':body.get('grade',''),'subject':body.get('subject',''),'experience':{},'references':refs})
    db.commit();return draft_json(db,db.get(TeachingCase,draft.case_id))


@router.get('/cases/{case_id}')
def case_detail(case_id: str, request: Request, db=Depends(get_db)):
    account(request,db,True);case=db.get(TeachingCase,case_id)
    if not case:raise HTTPException(404,'案例不存在。')
    return draft_json(db,case)


@router.post('/cases/{case_id}/revise')
def revise(case_id: str, request: Request, db=Depends(get_db)):
    account(request,db,True);case=db.get(TeachingCase,case_id)
    if not case:raise HTTPException(404,'案例不存在。')
    draft=db.get(CaseDraftContent,case_id)
    if not draft:
        version=latest_version(db,case_id)
        db.add(CaseDraftContent(case_id=case_id,data=copy.deepcopy(version.data) if version else {'title':case.title,'content':case.content,'source':case.source,'experience':{},'references':[]},reviewed=False));db.commit()
    return draft_json(db,case)


@router.put('/cases/{case_id}/draft')
def save_draft(case_id: str, body: dict, request: Request, db=Depends(get_db)):
    account(request,db,True);draft=db.get(CaseDraftContent,case_id)
    if not draft:raise HTTPException(409,'请先创建修订草稿。')
    data=body.get('data',{})
    if not isinstance(data,dict) or not isinstance(data.get('title'),str) or len(data.get('title',''))>240 or not isinstance(data.get('content'),str):raise HTTPException(422,'案例内容格式无效。')
    from .library import validate_knowledge
    try:validate_knowledge(db,data)
    except ValueError as e:raise HTTPException(422,str(e)) from None
    # 状态与审核由服务端控制；编辑任何正文/来源字段都会撤销原审核。
    server_fields={'experienceReview','reviewed','updatedAt'}
    changed={k:v for k,v in data.items() if k not in server_fields}!={k:v for k,v in draft.data.items() if k not in server_fields}
    data=copy.deepcopy(data)
    from .experience_policy import validate_experience
    try:validate_experience(data)
    except ValueError as e:raise HTTPException(422,str(e)) from None
    for field in server_fields:data.pop(field,None)
    if not changed and draft.data.get('experienceReview'):data['experienceReview']=copy.deepcopy(draft.data['experienceReview'])
    if changed and data.get('verification'):
        data['verification']={**data['verification'],'status':'unverified','claims':[{**c,'status':'unverified'} for c in data['verification'].get('claims',[])]}
    draft.data=data
    draft.reviewed=False if changed else draft.reviewed
    db.commit();return draft_json(db,db.get(TeachingCase,case_id))


@router.post('/cases/{case_id}/verify')
def verify_math(case_id: str, request: Request, db=Depends(get_db)):
    account(request,db,True);draft=db.get(CaseDraftContent,case_id)
    if not draft:raise HTTPException(404,'草稿不存在。')
    from .ai_schemas import MathClaim
    from .model_jobs import math_check
    try:
        values=draft.data.get('experience',{}).get('mathClaims',[])
        if len(values)>12:raise ValueError()
        claims=[MathClaim.model_validate(c).model_dump() for c in values]
    except (ValueError,TypeError):raise HTTPException(422,'数学表达格式无效。') from None
    draft.data={**draft.data,'verification':math_check(claims)};draft.reviewed=False;db.commit()
    return draft_json(db,db.get(TeachingCase,case_id))


@router.post('/cases/{case_id}/review')
def review(case_id: str, request: Request, db=Depends(get_db)):
    actor=account(request,db,True);draft=db.get(CaseDraftContent,case_id)
    if not draft:raise HTTPException(404,'草稿不存在。')
    from .experience_policy import validate_experience
    try:
        p=validate_experience(draft.data)
        validate_references(db,draft.data.get('references',[]))
    except ValueError as e:raise HTTPException(422,str(e)) from None
    draft.data={**draft.data,'experienceReview':{'reviewerId':actor.id,'reviewedAt':datetime.utcnow().isoformat()+'Z','provenance':p,'applicability':copy.deepcopy(draft.data.get('applicability'))}}
    draft.reviewed=True;db.commit();return {'reviewed':True}


@router.post('/cases/{case_id}/publish')
def publish_case(case_id: str, request: Request, db=Depends(get_db)):
    account(request,db,True);case=db.scalar(select(TeachingCase).where(TeachingCase.id==case_id).with_for_update());draft=db.scalar(select(CaseDraftContent).where(CaseDraftContent.case_id==case_id).with_for_update())
    if case and not draft and case.status=='published':
        db.commit();return draft_json(db,case)
    if not case or not draft:raise HTTPException(404,'请先创建案例草稿。')
    data=copy.deepcopy(draft.data)
    from .library import validate_knowledge
    try:validate_knowledge(db,data)
    except ValueError as e:raise HTTPException(422,str(e)) from None
    if not draft.reviewed or not str(data.get('title','')).strip() or not str(data.get('content','')).strip():raise HTTPException(422,'请填写标题、正文，并保存后完成原文核对。')
    if not data.get('references') and not data.get('legacy'):raise HTTPException(422,'请关联至少一处原文。')
    try:validate_references(db,data.get('references',[]))
    except ValueError as error:raise HTTPException(422,str(error)) from None
    from .models import KnowledgePoint
    data['knowledgeLinks']=[{'id':ident,'name':db.get(KnowledgePoint,ident).name} for ident in data.get('knowledgeIds',[])]
    last=db.scalar(select(CaseVersion).where(CaseVersion.case_id==case_id).order_by(CaseVersion.number.desc()).with_for_update().limit(1))
    version=CaseVersion(id=uid('version'),case_id=case_id,number=last.number+1 if last else 1,data=copy.deepcopy(data))
    db.add(version);case.title=data['title'];case.content=data['content'];case.source=data.get('source','');case.status='published';db.delete(draft)
    db.commit();return draft_json(db,case)


@router.post('/cases/{case_id}/withdraw')
def withdraw(case_id: str, request: Request, db=Depends(get_db)):
    account(request,db,True);case=db.get(TeachingCase,case_id)
    if not case:raise HTTPException(404,'案例不存在。')
    case.status='withdrawn';db.commit();return draft_json(db,case)


@router.get('/cases/{case_id}/knowledge-suggestions')
def knowledge_suggestions(case_id:str,request:Request,db=Depends(get_db)):
    account(request,db,True);case=db.get(TeachingCase,case_id)
    if not case:raise HTTPException(404,'案例不存在。')
    from .retrieval import identify_knowledge,knowledge_documents
    draft=db.get(CaseDraftContent,case_id);data=draft.data if draft else current_case(db,case_id) or {}
    experience=data.get('experience') or {}
    text=' '.join([data.get('title',''),experience.get('goal',''),experience.get('difficulty',''),*experience.get('knowledgePoints',[])])
    return {'suggestions':identify_knowledge(text,knowledge_documents(db)),'confirmedIds':data.get('knowledgeIds',[])}


@router.get('/experience-coverage')
def experience_coverage(request:Request,db=Depends(get_db)):
    account(request,db,True)
    from .curated_resources import coverage
    return coverage(db)
