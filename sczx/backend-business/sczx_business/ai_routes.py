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
from .models import Attempt, FileAsset, LearningTask, ModelJob, ModelRun, ModelEvent, StudentRecord
from .model_jobs import event, provider, help_record_id
from .retrieval import search, published_documents

router = APIRouter(prefix="/api/ai")


def user_for(request, db):
    from .main import current_user
    return current_user(request, db)


def can_read(db, user, job):
    if user.role == "admin" or job.owner_id == user.id: return True
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
    if 'context' in exposed:exposed['context']=public_context(exposed['context'])
    result = job.result
    if result and not detail and "vectors" in result: result = {k:v for k,v in result.items() if k != "vectors"}
    return {"id":job.id,"capability":job.capability,"summary":job.input.get("label", ""),"recordId":job.record_id,"fileId":job.file_id,"helpRecordId":help_record_id(job.id) if job.capability=="text" and job.record_id and job.status=="succeeded" else None,"question":job.input.get("question"),"recognizedText":job.input.get("recognizedText"),"status":job.status,"step":job.step,"error":job.error,"result":result,"attemptNumber":job.attempt_number,"createdAt":job.created_at.isoformat()+"Z","updatedAt":job.updated_at.isoformat()+"Z", **({"input":exposed} if detail else {})}


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


@router.get("/search")
def search_cases(request: Request, q: str = "", db=Depends(get_db)):
    user_for(request, db)
    if len(q) > 2000: raise HTTPException(422, "检索内容过长，请缩短问题。")
    documents = published_documents(db)
    items = search(q, documents) if q.strip() else documents
    return {"query": q, "method": "bm25", "items": items, "totalDocuments": len(documents)}


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
    elif user.role == "teacher":
        query=query.outerjoin(StudentRecord,ModelJob.record_id==StudentRecord.id).outerjoin(LearningTask,StudentRecord.task_id==LearningTask.id).where((LearningTask.teacher_id==user.id) | (ModelJob.owner_id==user.id))
    return [serialize(item,False) for item in db.scalars(query.order_by(ModelJob.created_at.desc()).limit(60)).all()]


@router.post("/jobs",status_code=201)
def create_job(payload: JobInput, request: Request, db=Depends(get_db)):
    user = user_for(request, db)
    data = payload.data.copy()
    record = db.get(StudentRecord,payload.recordId) if payload.recordId else None
    if payload.capability == "retrieval":
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
        query = data.get("query")
        if not isinstance(query, str) or not 0 < len(query.strip()) <= 2000: raise HTTPException(422, "请输入1至2000字的教学问题。")
        data = {"query": query.strip(), "rerank": data.get("rerank") is True, "documents": published_documents(db)}
    if payload.capability=="text":
        prompt=data.get("prompt","")
        prompt=prompt.strip() if isinstance(prompt,str) else ""
        if not prompt: raise HTTPException(422,"请填写问题。")
        data["prompt"]=prompt[:12000]
        if record:
            task=db.get(LearningTask,record.task_id)
            question=data.get("question")
            if question is not None and (isinstance(question,bool) or not isinstance(question,int) or not 0<=question<len(task.questions)):
                raise HTTPException(422,"当前题目不存在。")
            data["context"]={"lesson":task.snapshot,"question":task.questions[question] if question is not None else None,"observation":record.observation}
            recognized = data.get("recognizedText", "")
            teaching_query = (recognized if isinstance(recognized, str) else "") + " " + prompt
            data["context"]["teachingCases"] = search(teaching_query, published_documents(db), 3)
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
    result["runs"]=[{"id":run.id,"number":run.number,"status":run.status,"model":run.model,"provider":run.provider,"error":run.error,"result":run.result,"startedAt":run.started_at.isoformat()+"Z","endedAt":run.ended_at.isoformat()+"Z" if run.ended_at else None} for run in db.scalars(select(ModelRun).where(ModelRun.job_id==job.id).order_by(ModelRun.number)).all()]
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
    if job.status!="failed": raise HTTPException(409,"只有失败任务可以重试。")
    if db.scalar(select(ModelJob.id).where(ModelJob.owner_id==user.id,ModelJob.active_hash==job.input_hash,ModelJob.id!=job.id).limit(1)):
        raise HTTPException(409,"相同内容已有运行任务，请先查看该任务。")
    job.status,job.error,job.retry_count="queued","",0
    job.active_hash=job.input_hash
    event(db,job,"等待手动重试")
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"相同内容已有运行任务，请先查看该任务。") from None
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
                terminal=job.status in ("succeeded","failed")
            for chunk in chunks: yield chunk
            if terminal:
                yield 'event: done\ndata: {}\n\n'
                return
            yield ": heartbeat\n\n"
            await asyncio.sleep(.5)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
