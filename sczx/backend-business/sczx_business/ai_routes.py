import copy
import asyncio
import hashlib
import json
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .ai_schemas import JobInput, CAPABILITIES
from .database import get_db, SessionLocal
from .models import Attempt, FileAsset, LearningTask, ModelJob, ModelRun, ModelEvent, StudentRecord, HelpRecord
from .model_jobs import event, provider, help_record_id
from .retrieval import search, published_documents, retrieve, knowledge_documents, validate_request, student_request

router = APIRouter(prefix="/api/ai")


def user_for(request, db):
    from .main import current_user
    return current_user(request, db)


def can_read(db, user, job):
    if job.owner_id == user.id: return True
    if user.role == "admin": return job.capability in ("document_parse","document_ocr","case_extract")
    record = db.get(StudentRecord, job.record_id) if job.record_id else None
    task = db.get(LearningTask, record.task_id) if record else None
    return user.role == "teacher" and task and task.teacher_id == user.id


def job_for(db, user, job_id):
    job = db.get(ModelJob, job_id)
    if not job or not can_read(db, user, job): raise HTTPException(404, "没有找到此运行任务。")
    return job


def serialize(job, detail=True):
    def public_context(value):
        if isinstance(value,list):return [public_context(v) for v in value]
        if isinstance(value,dict):return {k:public_context(v) for k,v in value.items() if k not in ('answer','hint','teacherNote','feedback','explanation')}
        return value
    exposed=copy.deepcopy(job.input)
    exposed.pop("_validation",None)
    exposed.pop("_requestFingerprint",None)
    if 'context' in exposed:exposed['context']=public_context(exposed['context'])
    result = copy.deepcopy(job.result)
    if result and result.get("variant"):
        result["variant"].pop("expected",None)
    if result and not detail and "vectors" in result: result = {k:v for k,v in result.items() if k != "vectors"}
    return {"id":job.id,"mode":job.input.get("mode"),"wrongId":job.input.get("wrongId"),"phase":job.input.get("phase"),"capability":job.capability,"lessonId":job.input.get("lessonId"),"summary":job.input.get("label") or job.input.get("task", "")[:64],"recordId":job.record_id,"fileId":job.file_id,"helpRecordId":help_record_id(job.id) if job.capability=="text" and job.record_id and job.status=="succeeded" and job.input.get("strategy")!="try" and (not job.input.get("remediation") or job.input.get("mode")=="guidance") else None,"question":job.input.get("question"),"blockId":job.input.get("blockId"),"strategy":job.input.get("strategy"),"prompt":job.input.get("prompt"),"parentJobId":job.input.get("parentJobId"),"recognizedText":job.input.get("recognizedText"),"status":job.status,"step":job.step,"error":job.error,"result":result,"attemptNumber":job.attempt_number,"retryCount":job.retry_count,"createdAt":job.created_at.isoformat()+"Z","updatedAt":job.updated_at.isoformat()+"Z", **({"input":exposed} if detail else {})}


@router.get("/capabilities")
def capabilities(request: Request, db=Depends(get_db)):
    user = user_for(request, db)
    if user.role != "admin": raise HTTPException(403,"仅管理员可查看服务配置状态。")
    entries = provider.configured()
    from .codex_provider import UNSUPPORTED
    cli = os.getenv("SCZX_MODEL_TRANSPORT", "codex_cli") == "codex_cli"
    results = []
    for cap in CAPABILITIES:
        latest = db.scalar(select(ModelJob).where(ModelJob.capability==cap, ModelJob.status.in_(["succeeded","failed"])).order_by(ModelJob.updated_at.desc()).limit(1))
        results.append({"capability":cap,"configured":bool(entries[cap]),"unavailableReason":UNSUPPORTED.get(cap, "") if cli else "","transport":"algorithm" if cap=="retrieval" else "codex_cli" if cli else "http","models":entries[cap],"lastStatus":latest.status if latest else None,"lastJobId":latest.id if latest else None,"lastError":latest.error if latest else ""})
    return results


def search_spec(body,db):
    from pydantic import ValidationError
    try:return validate_request(body,knowledge_documents(db))
    except (ValueError,ValidationError) as error:
        raise HTTPException(422,'检索参数无效：'+str(error).split('\n')[0]) from None


@router.get('/search-options')
def search_options(request:Request,db=Depends(get_db)):
    user_for(request,db)
    from .retrieval import SCENARIOS,normalize_grade
    docs=published_documents(db)
    return {'knowledge':knowledge_documents(db),'grades':sorted({normalize_grade(d.get('grade')) for d in docs if normalize_grade(d.get('grade'))},key=int),'subjects':sorted({d['subject'] for d in docs if d.get('subject')}),'scenarios':[{'value':k,'label':v} for k,v in SCENARIOS.items()]}


@router.get('/search')
def search_cases(request:Request,q:str='',db=Depends(get_db)):
    user_for(request,db)
    spec=search_spec({'query':q},db)
    result=retrieve(spec,published_documents(db),knowledge_documents(db))
    if result['mode']=='browse':result['items']=result['candidateItems']
    result.pop('candidateItems',None)
    return result


@router.post('/search')
def structured_search(body:dict,request:Request,db=Depends(get_db)):
    user=user_for(request,db)
    if user.role not in ('admin','teacher'):raise HTTPException(403,'请通过自己的学习任务获取指导。')
    spec=search_spec(body,db)
    if spec['rerank']:raise HTTPException(422,'语义重排请通过后台检索任务发起。')
    result=retrieve(spec,published_documents(db),knowledge_documents(db));result.pop('candidateItems',None)
    return result


@router.get("/cases/{case_id}")
def read_case(case_id: str, request: Request, db=Depends(get_db)):
    user_for(request, db)
    from .models import TeachingCase
    from .library import current_case
    item = current_case(db, case_id, request.query_params.get("versionId"))
    if not item: raise HTTPException(404, "案例不存在或尚未发布。")
    return item


@router.get("/jobs")
def jobs(request: Request, recordId: str | None = None, capability: str | None = None, db=Depends(get_db)):
    user = user_for(request, db)
    query = select(ModelJob)
    if recordId: query=query.where(ModelJob.record_id==recordId)
    if capability: query=query.where(ModelJob.capability==capability)
    if user.role == "student": query=query.where(ModelJob.owner_id==user.id)
    elif user.role == "admin":query=query.where((ModelJob.owner_id==user.id) | ModelJob.capability.in_(["document_parse","document_ocr","case_extract"]))
    elif user.role == "teacher":
        query=query.outerjoin(StudentRecord,ModelJob.record_id==StudentRecord.id).outerjoin(LearningTask,StudentRecord.task_id==LearningTask.id).where((LearningTask.teacher_id==user.id) | (ModelJob.owner_id==user.id))
    return [serialize(item,False) for item in db.scalars(query.order_by(ModelJob.created_at.desc()).limit(60)).all()]


@router.post("/jobs",status_code=201)
def create_job(payload: JobInput, request: Request, db=Depends(get_db)):
    user = user_for(request, db)
    data = payload.data.copy()
    record = db.get(StudentRecord,payload.recordId) if payload.recordId else None
    if user.role=="student" and record and record.student_id==user.id:
        from .teaching import ensure_write
        ensure_write(db,user,record.task_id)
    if payload.capability=='text' and user.role=='student' and record and not payload.data.get('wrongId'):
        from .tutoring import request_fingerprint
        existing=db.scalar(select(ModelJob).where(ModelJob.owner_id==user.id,ModelJob.request_key==payload.requestKey))
        if existing:
            if existing.input.get('_requestFingerprint')!=request_fingerprint(payload):raise HTTPException(409,'同一请求标识对应不同指导内容。')
            return serialize(existing)
    wrong_item=None
    if data.get('wrongId'):
        from .remediation import access
        wrong_item=access(db,user,str(data['wrongId']),True)
        if payload.capability!='text' or payload.recordId!=wrong_item.record_id:raise HTTPException(422,'错题指导记录关联不一致。')
    if wrong_item:
        pass
    elif payload.capability=='ocr' and user.role=='student' and data.get('wrongCapture') is True and not payload.recordId:
        pass
    elif payload.capability=="text" and data.get("examCandidate"):
        if user.role!="teacher" or payload.recordId or payload.fileId:raise HTTPException(403,"请使用教师题库入口。")
        from .exam_schemas import BankInput
        from .models import CourseUnit,KnowledgePoint
        if not db.get(CourseUnit,data.get("unitId")) or not data.get("knowledgeIds") or any(not db.get(KnowledgePoint,k) for k in data["knowledgeIds"]):raise HTTPException(422,"请选择真实单元和知识点。")
        if data.get("kind") not in ("calculation","application","explanation") or data.get("difficulty") not in ("easy","medium","hard"):raise HTTPException(422,"请选择题型和难度。")
        data={k:data[k] for k in ("examCandidate","unitId","knowledgeIds","kind","difficulty")};data["prompt"]="生成一道符合以上约束、等待人工审核的候选题。"
    elif payload.capability == "lesson_agent":
        if user.role != "teacher" or payload.recordId or payload.fileId:raise HTTPException(403,"请使用教师备课入口。")
        from .prepare_agent import build_input
        data=build_input(db,user,data)
    elif payload.capability == "retrieval":
        if payload.recordId: raise HTTPException(422, "案例检索不关联学生学习记录。")
        if user.role not in ("admin", "teacher"): raise HTTPException(403, "请从教师案例入口检索。")
    elif user.role != "admin":
        if user.role != "student" or not record or record.student_id != user.id: raise HTTPException(403,"请选择自己的学习记录。")
        if payload.capability not in ("text","ocr"): raise HTTPException(403,"此能力通过管理员验证入口使用。")
    elif payload.recordId and not record: raise HTTPException(404,"学习记录不存在。")
    file_id = payload.fileId
    if payload.capability in ("ocr","asr") and not file_id: raise HTTPException(422,"请先上传文件。")
    if data.get("ocrJobId"):
        original = job_for(db,user,str(data["ocrJobId"]))
        if original.owner_id!=user.id or original.record_id!=payload.recordId or original.capability!="ocr" or original.status!="succeeded" or data.get("confirmed") is not True:
            raise HTTPException(422,"请先核对并确认对应识别结果。")
        if not str(data.get("recognizedText","")).strip(): raise HTTPException(422,"请填写确认后的题目。")
        file_id=original.file_id
    if file_id:
        asset=db.get(FileAsset,file_id)
        if not asset or asset.owner_id!=user.id: raise HTTPException(404,"没有找到此账号上传的文件。")
        if payload.capability=="ocr" and not asset.content_type.startswith("image/"): raise HTTPException(422,"请选择题图。")
        if payload.capability=="asr" and not asset.content_type.startswith("audio/"): raise HTTPException(422,"请选择音频文件。")
    if payload.capability == "retrieval":
        spec=search_spec(data,db)
        if not spec['query'] and not spec['filters']['knowledgeIds']:raise HTTPException(422,'请填写教学问题或选择知识点。')
        data={**spec,'documents':published_documents(db),'knowledge':knowledge_documents(db)}
    if payload.capability=="text" and not wrong_item:
        prompt=data.get("prompt","")
        prompt=prompt.strip() if isinstance(prompt,str) else ""
        if not prompt: raise HTTPException(422,"请填写问题。")
        data["prompt"]=prompt[:12000]
        if record:
            task=db.get(LearningTask,record.task_id)
            question=data.get("question")
            if question is not None and (isinstance(question,bool) or not isinstance(question,int) or not 0<=question<len(task.questions)):
                raise HTTPException(422,"当前题目不存在。")
            from .curriculum import student_content
            public_snapshot=student_content(task.snapshot)
            data["context"]={"lesson":public_snapshot,"question":student_content({'questions':[task.questions[question]]})['questions'][0] if question is not None else None,"observation":record.observation}
            recognized = data.get("recognizedText", "")
            specification=student_request(task.snapshot,task.questions[question] if question is not None else None,record.observation,prompt,recognized if isinstance(recognized,str) else '')
            points=knowledge_documents(db);known={p['id'] for p in points}
            for key in ('knowledgeIds','prerequisiteIds'):specification['context'][key]=[i for i in specification['context'][key] if i in known]
            retrieval=retrieve(specification,published_documents(db),points)
            data['context']['teachingCases']=retrieval['items']
            data['context']['retrieval']={k:v for k,v in retrieval.items() if k not in ('items','candidateItems')}
            data['retrievalContext']=specification
            data["attemptNumber"]=len(db.scalars(select(Attempt.id).where(Attempt.record_id==record.id)).all())+1
            # Requesting help immediately marks the current pending attempt as helped.
            if question is not None:
                drafts=dict(record.drafts or {})
                check=dict(drafts.get("check") or {})
                if check.get("question")==question:
                    check["helped"]=True
                    drafts["check"]=check
                    record.drafts=drafts
    elif payload.capability=="embedding":
        texts=data.get("texts")
        if not isinstance(texts,list) or not 1<=len(texts)<=32 or any(not isinstance(t,str) or not t.strip() or len(t)>12000 for t in texts): raise HTTPException(422,"请输入1至32段有效文本。")
    elif payload.capability=="rerank":
        items=data.get("candidates")
        if not isinstance(data.get("query"),str) or not data["query"].strip() or not isinstance(items,list) or not 1<=len(items)<=32 or any(not isinstance(i,dict) or not isinstance(i.get("text"),str) or not i["text"].strip() or not isinstance(i.get("id"),str) or not i["id"].strip() for i in items) or len({i["id"] for i in items})!=len(items): raise HTTPException(422,"请填写查询和带唯一编号的候选材料。")
    elif payload.capability=="tts" and (not isinstance(data.get("text"),str) or not 0<len(data["text"].strip())<=5000): raise HTTPException(422,"合成文本需为1至5000字。")
    if payload.capability=='ocr' and record:
        task=db.get(LearningTask,record.task_id);question=data.get('question');block=data.get('blockId')
        if question is not None and (isinstance(question,bool) or not isinstance(question,int) or not 0<=question<len(task.questions)):raise HTTPException(422,'当前题目不存在。')
        if block and not any(b.get('id')==block for b in task.snapshot.get('blocks',[])):raise HTTPException(422,'当前内容块不存在。')
    if payload.capability=='text' and record and user.role=='student' and not wrong_item:
        from .tutoring import prepare
        data=prepare(db,user,record,payload.data)
        from .tutoring import request_fingerprint
        data["_requestFingerprint"]=request_fingerprint(payload)
        file_id=data.pop('fileId')
    if wrong_item:
        from .remediation import prepare
        data=prepare(db,user,wrong_item,payload.data)
    digest=hashlib.sha256(json.dumps({"cap":payload.capability,"data":data,"record":payload.recordId,"file":file_id},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    existing=db.scalar(select(ModelJob).where(ModelJob.owner_id==user.id,ModelJob.request_key==payload.requestKey))
    if existing:
        if existing.input_hash!=digest: raise HTTPException(409,"重复请求标识对应不同内容，请重新提交。")
        return serialize(existing)
    existing=db.scalar(select(ModelJob).where(ModelJob.owner_id==user.id,ModelJob.input_hash==digest,ModelJob.status.in_(["queued","running"])))
    if existing: return serialize(existing)
    job=ModelJob(id="job-"+uuid.uuid4().hex,owner_id=user.id,record_id=payload.recordId,file_id=file_id,capability=payload.capability,request_key=payload.requestKey,input_hash=digest,active_hash=digest,input=data)
    db.add(job)
    try:
        db.flush()
        if data.get('guidance') and data.get('strategy')!='try' and record:
            from .tutoring import STRATEGIES
            db.add(HelpRecord(id=help_record_id(job.id),record_id=record.id,question=data.get('question'),kind='指导请求',message=STRATEGIES[data['strategy']]+'：'+data['prompt'],file_id=file_id,attempt_number=len(db.scalars(select(Attempt.id).where(Attempt.record_id==record.id)).all())+1))
        event(db,job,"排队中")
        db.commit()
    except IntegrityError:
        db.rollback()
        existing=db.scalar(select(ModelJob).where(ModelJob.owner_id==user.id, (ModelJob.request_key==payload.requestKey) | (ModelJob.active_hash==digest)))
        if existing and existing.input_hash==digest: return serialize(existing)
        raise HTTPException(409,"请求正在提交，请重新读取运行列表。") from None
    return serialize(job)


@router.get("/jobs/{job_id}")
def detail(job_id: str, request: Request, db=Depends(get_db)):
    job=job_for(db,user_for(request,db),job_id)
    result=serialize(job)
    if job.capability=='retrieval' and job.status=='succeeded' and job.result:
        current={(d['id'],d.get('versionId')) for d in published_documents(db)}
        result['liveItems']=[item for item in job.result.get('items',[]) if (item['id'],item.get('versionId')) in current]
        result['hasStaleItems']=len(result['liveItems'])!=len(job.result.get('items',[]))
    result["runs"]=[{"id":run.id,"number":run.number,"status":run.status,"model":run.model,"provider":run.provider,"error":run.error,"result":({**run.result,"variant":{k:v for k,v in run.result["variant"].items() if k!="expected"}} if run.result and run.result.get("variant") else run.result),"startedAt":run.started_at.isoformat()+"Z","endedAt":run.ended_at.isoformat()+"Z" if run.ended_at else None} for run in db.scalars(select(ModelRun).where(ModelRun.job_id==job.id).order_by(ModelRun.number)).all()]
    return result


@router.put("/jobs/{job_id}/correction")
def correct_transcript(job_id: str, body: dict, request: Request, db=Depends(get_db)):
    user=user_for(request,db)
    job=job_for(db,user,job_id)
    if job.owner_id!=user.id or job.capability!="asr" or job.status!="succeeded": raise HTTPException(409,"只能修订自己已完成的转写结果。")
    text=str(body.get("text","")).strip()
    if not 0<len(text)<=20000: raise HTTPException(422,"请输入有效转写文字。")
    job.result={**job.result,"correctedText":text}
    db.commit()
    return serialize(job)


@router.post("/jobs/{job_id}/retry")
def retry(job_id: str, request: Request, db=Depends(get_db)):
    user=user_for(request,db)
    job=db.scalar(select(ModelJob).where(ModelJob.id==job_id).with_for_update())
    if not job or job.owner_id!=user.id: raise HTTPException(404,"没有找到可重试的任务。")
    if user.role=='student' and job.record_id:
        from .teaching import ensure_write
        record=db.get(StudentRecord,job.record_id);ensure_write(db,user,record.task_id)
    from .job_access import validate_retry
    validate_retry(db,job)
    if job.status!="failed": raise HTTPException(409,"只有失败任务可以重试。")
    if db.scalar(select(ModelJob.id).where(ModelJob.owner_id==user.id,ModelJob.active_hash==job.input_hash,ModelJob.id!=job.id).limit(1)):
        raise HTTPException(409,"相同内容已有运行任务，请先查看该任务。")
    job.status,job.error,job.retry_count="queued","",0
    if job.capability=='lesson_agent' and job.result:
        from .prepare_agent import now
        job.result={**job.result,'budgetStartedAt':now()}
    job.active_hash=job.input_hash
    event(db,job,"等待手动重试")
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"相同内容已有运行任务，请先查看该任务。") from None
    return serialize(job)


@router.post('/jobs/{job_id}/stop')
def stop_guidance(job_id:str,request:Request,db=Depends(get_db)):
    user=user_for(request,db);job=db.scalar(select(ModelJob).where(ModelJob.id==job_id).with_for_update())
    if not job or job.owner_id!=user.id or not job.input.get('guidance'):raise HTTPException(404,'没有找到自己的指导。')
    if job.status in ('queued','running'):
        job.status='cancelled';job.error='已结束本轮，历史保留。';job.active_hash=None;event(db,job,'用户结束本轮指导');db.commit()
        from .model_jobs import cancel_execution
        cancel_execution(job.id)
    return serialize(job)


@router.get("/jobs/{job_id}/events")
def events(job_id: str, request: Request, after: int=0, db=Depends(get_db)):
    user=user_for(request,db)
    job_for(db,user,job_id)
    try: cursor=max(after,int(request.headers.get("last-event-id","0")))
    except ValueError: raise HTTPException(422,"事件游标无效。")
    db.close()
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            with SessionLocal() as session:
                job=job_for(session,user,job_id)
                rows=session.scalars(select(ModelEvent).where(ModelEvent.job_id==job_id,ModelEvent.id>cursor).order_by(ModelEvent.id)).all()
                chunks=[]
                for row in rows:
                    cursor=row.id
                    chunks.append(f"id: {row.id}\nevent: progress\ndata: "+json.dumps({"id":row.id,"status":row.status,"step":row.step,"attemptNumber":row.attempt_number},ensure_ascii=False)+"\n\n")
                terminal=job.status in ("succeeded","failed","cancelled")
            for chunk in chunks: yield chunk
            if terminal:
                yield 'event: done\ndata: {}\n\n'
                return
            yield ": heartbeat\n\n"
            await asyncio.sleep(.5)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})


def owned_agent(db,user,job_id):
    job=db.scalar(select(ModelJob).where(ModelJob.id==job_id).with_for_update())
    if user.role!='teacher' or not job or job.owner_id!=user.id or job.capability!='lesson_agent':raise HTTPException(404,'没有找到自己的备课任务。')
    return job

@router.get('/agent/draft-state')
def agent_draft_state(lessonId:str,request:Request,db=Depends(get_db)):
    from .prepare_agent import current_draft,fingerprint
    user=user_for(request,db)
    if user.role!='teacher':raise HTTPException(403,'请使用教师账号。')
    row=current_draft(db,user.id,lessonId)
    return {'draftHash':fingerprint(row),'goal':row.goal if row else '', 'blocks':row.blocks if row else [],'lessonVersionId':(row.lesson_snapshot or {}).get('versionId') if row else None,'sourceVersion':__import__('sczx_business.curriculum',fromlist=['published_lesson']).published_lesson(db,lessonId)}

@router.put('/agent/{job_id}/draft')
def agent_edit(job_id:str,body:dict,request:Request,db=Depends(get_db)):
    from .prepare_agent import validate_plan,now
    from .model_jobs import math_check
    job=owned_agent(db,user_for(request,db),job_id)
    if job.status not in ('succeeded','failed') or not (job.result or {}).get('plan'):raise HTTPException(409,'请等待建议生成完成。')
    if (job.result or {}).get('accepted'):raise HTTPException(409,'已确认的建议请在备课页继续编辑。')
    try:plan=validate_plan(body,job.input['lesson'],job.result.get('evidence',[]))
    except ValueError as error:raise HTTPException(422,'建议结构或引用无效：'+str(error).split('\n')[0]) from None
    from .math_conditions import require_conditions
    require_conditions(plan)
    verification=math_check(plan['mathClaims'])
    if verification['status']=='inconsistent':raise HTTPException(422,'列出的数学表达式不一致，请修订后保存。')
    from .teaching_quality import review_plan
    result=copy.deepcopy(job.result);result['textQuality']=review_plan(plan,job.input.get('regenerateBlockId'));result.update(editable=plan,editedAt=now(),decision='pending',verification={**verification,'structure':'passed','references':'passed','humanReviewRequired':True})
    job.result=result;job.status='succeeded';job.error='';job.active_hash=None
    event(db,job,'建议草稿已保存，等待确认');db.commit();return serialize(job)

@router.post('/agent/{job_id}/confirm')
def agent_confirm(job_id:str,body:dict,request:Request,db=Depends(get_db)):
    from .planning_schemas import AgentConfirmation
    from .prepare_agent import current_draft,fingerprint,validate_plan,now
    from .models import LessonDraft
    from .library import uid
    from .model_jobs import math_check
    try:confirmation=AgentConfirmation.model_validate(body)
    except ValueError:raise HTTPException(422,'请明确确认替换备课目标和活动。') from None
    user=user_for(request,db);job=owned_agent(db,user,job_id);result=copy.deepcopy(job.result or {})
    if result.get('accepted'):return {'accepted':result['accepted'],'created':False}
    if job.status!='succeeded' or not result.get('editable'):raise HTTPException(409,'请先完成并保存建议。')
    try:plan=validate_plan(result['editable'],job.input['lesson'],result.get('evidence',[]))
    except ValueError:raise HTTPException(422,'建议未通过校验。') from None
    from .math_conditions import require_conditions
    require_conditions(plan)
    if math_check(plan['mathClaims'])['status']=='inconsistent':raise HTTPException(422,'请先修订数学核对问题。')
    row=db.scalar(select(LessonDraft).where(LessonDraft.teacher_id==user.id,LessonDraft.lesson_id==job.input['lessonId']).with_for_update())
    if fingerprint(row)!=confirmation.expectedDraftHash:raise HTTPException(409,'备课草稿已变更，请重新查看当前草稿后再确认；本次建议已保留。')
    lesson=job.input['lesson']
    from .curriculum import published_lesson
    latest=published_lesson(db,job.input['lessonId'])
    if not latest or latest['versionId']!=lesson['versionId']:raise HTTPException(409,'来源课时已重新发布或停用。本次历史结果保留，请使用最新课时重新生成，不能覆盖当前教案。')
    from .drafts import preserve_original,checkpoint
    if row:preserve_original(db,row)
    if row and {q['id'] for q in row.questions}!={q['id'] for q in lesson['questions']}:raise HTTPException(409,'当前题目与课时版本不同，请先在备课页确认使用发布课时。')
    if not row:
        row=LessonDraft(id=uid('draft'),teacher_id=user.id,lesson_id=job.input['lessonId'],case_id=lesson.get('caseId'),case_snapshot=lesson.get('caseSnapshot'),lesson_snapshot=lesson,questions=copy.deepcopy(lesson['questions']),student_base='',due_date='');db.add(row)
    row.lesson_snapshot=copy.deepcopy(lesson)
    base_blocks=copy.deepcopy(row.blocks or lesson['blocks'])
    target=job.input.get('regenerateBlockId')
    by_id={b['id']:b for b in plan['blocks']};row.blocks=[{**copy.deepcopy(b),'title':by_id[b['id']]['title'],'content':by_id[b['id']]['content'],'agentEvidence':by_id[b['id']]['evidenceIds'],'agentJobId':job.id,**{key:by_id[b['id']][key] for key in ('studentTask','teacherQuestion','studentResponse','adjustment') if by_id[b['id']].get(key)}} if (not target or b['id']==target) else b for b in base_blocks];row.goal=row.goal if target else plan['goal']
    checkpoint(db,row,'采用Agent建议')
    receipt={'draftId':row.id,'lessonId':row.lesson_id,'confirmedAt':now(),'jobId':job.id}
    result.update(accepted=receipt,decision='accepted');job.result=result;event(db,job,'已确认保存到备课草稿');db.commit();return {'accepted':receipt,'created':True}

@router.post('/agent/{job_id}/cancel')
def agent_cancel(job_id:str,request:Request,db=Depends(get_db)):
    from .model_jobs import cancel_execution
    job=owned_agent(db,user_for(request,db),job_id)
    if (job.result or {}).get('accepted'):raise HTTPException(409,'已确认内容请在备课页继续编辑。')
    if job.status=='cancelled':return serialize(job)
    job.status='cancelled';job.error='教师取消，已完成步骤保留。';job.active_hash=None
    if job.result:job.result={**job.result,'decision':'rejected'}
    event(db,job,'已取消');db.commit();cancel_execution(job.id);return serialize(job)

@router.get('/failures')
def failures(request:Request,db=Depends(get_db)):
    user=user_for(request,db)
    from .job_access import validate_retry
    rows=db.scalars(select(ModelJob).where(ModelJob.status=='failed').order_by(ModelJob.updated_at.desc())).all();result=[]
    for job in rows:
        own=job.owner_id==user.id
        if not own and user.role!='admin' and not can_read(db,user,job):continue
        reason='仅原提交账号可重试。'
        if own:
            try:validate_retry(db,job);reason=''
            except HTTPException as e:reason=str(e.detail)
        result.append({'id':job.id,'capability':job.capability,'createdAt':job.created_at.isoformat()+'Z','attemptNumber':job.attempt_number,'retryCount':job.retry_count,'status':job.status,'error':job.error if own else '业务任务失败，请由原提交者核对来源后处理。','canRetry':own and not reason,'retryBlockedReason':reason})
    return result
