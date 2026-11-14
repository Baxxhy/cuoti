import asyncio
import contextlib
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from .database import SessionLocal
from .models import FileAsset, HelpRecord, ModelEvent, ModelJob, ModelRun
from .model_provider import ModelProvider, ModelError
from .math_tools import compare_equivalence

log = logging.getLogger(__name__)
provider = ModelProvider()
worker_task = None
active_execution = None
active_job_id = None
worker_loop = None

def cancel_execution(job_id):
    if worker_loop and active_job_id == job_id and active_execution:
        worker_loop.call_soon_threadsafe(active_execution.cancel)



def help_record_id(job_id):
    return "help-" + job_id[4:]


def storage_dir():
    return Path(os.getenv("SCZX_STORAGE_DIR", "./var/uploads")).resolve()


def event(db, job, step):
    job.step = step
    db.add(ModelEvent(job_id=job.id, attempt_number=job.attempt_number, status=job.status, step=step))


def phase(job_id, step):
    with SessionLocal.begin() as db:
        job = db.get(ModelJob, job_id)
        event(db, job, step)


def math_check(claims):
    results = []
    for claim in claims:
        from .math_tools import compare_claim
        equal, verified, reason = compare_claim(claim["left"], claim["right"])
        results.append({**claim, "method":reason, "status": "verified" if verified and equal else "inconsistent" if verified else "unverified"})
    status = "inconsistent" if any(x["status"] == "inconsistent" for x in results) else "verified" if results and all(x["status"] == "verified" for x in results) else "unverified"
    return {"status": status, "claims": results, "scope": "仅核对列出的表达式或单变量方程，条件关系需人工核对，不代表整份讲解已核对"}


def require_job_write(db,job):
    from .models import Account,StudentRecord
    from .teaching import ensure_write
    from fastapi import HTTPException
    owner=db.get(Account,job.owner_id)
    if owner and owner.role=='student' and job.record_id:
        rec=db.get(StudentRecord,job.record_id)
        try:ensure_write(db,owner,rec.task_id)
        except HTTPException:raise ModelError('已移出班级，本轮指导停止；历史保留，重新加入后可手动重试。') from None


async def execute(job_id, run_id):
    with SessionLocal() as db:
        job = db.get(ModelJob, job_id)
        require_job_write(db,job)
        capability, data, file = job.capability, dict(job.input), None
        if capability=='text' and not data.get('guidance') and not data.get('remediation') and job.record_id:
            from .models import Account,StudentRecord
            owner=db.get(Account,job.owner_id)
            if owner.role=='student':
                from .tutoring import prepare
                data=prepare(db,owner,db.get(StudentRecord,job.record_id),data);data.pop('fileId',None)
        if job.retry_count and "结构" in job.error:
            data["repairStructure"] = True
        if job.file_id:
            asset = db.get(FileAsset, job.file_id)
            path = storage_dir() / asset.storage_key if asset else None
            if not path or not path.is_file(): raise ModelError("原始文件缺失，请重新上传。")
            file = (asset.original_name, path.read_bytes(), asset.content_type)
    if capability == 'lesson_agent':
        from .prepare_agent import run_agent
        result=await run_agent(job_id,run_id,provider)
        with SessionLocal.begin() as db:
            job=db.scalar(select(ModelJob).where(ModelJob.id==job_id).with_for_update());run=db.get(ModelRun,run_id)
            if job.status=='cancelled':raise asyncio.CancelledError()
            job.result,job.status,job.error,job.active_hash=result,'succeeded','',None
            run.result,run.status,run.model,run.provider,run.ended_at=result,'succeeded',result.get('model',''),'Codex CLI / LangGraph',datetime.utcnow()
            event(db,job,'等待教师确认')
        return
    phase(job_id, {"document_parse": "正在解析原文", "document_ocr": "正在识别原文页面", "case_extract": "正在整理教学经验", "retrieval": "正在检索教学案例", "ocr": "正在识别题图", "text": "正在生成指导", "embedding": "正在生成向量", "rerank": "正在重排材料", "asr": "正在转写音频", "tts": "正在合成音频"}[capability])
    if data.get('remediation'):
        from .remediation import run
        result,model,source=await run(data,provider,run_id)
    elif data.get('guidance'):
        from .tutoring import run
        result,model,source=await run(data,provider,run_id)
    else:result, model, source = await provider.call(capability, data, file=file, request_id=run_id)
    if capability in ("text", "case_extract") and not data.get("guidance") and not data.get("remediation"):
        from .math_conditions import require_conditions
        from .education import context_subject,is_mathematical
        subject,_=context_subject(data)
        result["conditionCheck"]=require_conditions(result) if not subject or is_mathematical(subject) else {"issues":[],"scope":"依照当前学科材料和评价要点核对"}
        phase(job_id, "正在核对数学表达")
        result["verification"] = await asyncio.to_thread(math_check, result.get("mathClaims", []))
        context = data.get('context') if isinstance(data.get('context'),dict) else {}
        provided = [{**x,'role':'retrieval'} for x in context.get('teachingCases',[]) if isinstance(x,dict)]
        lesson = context.get('lesson') if isinstance(context.get('lesson'),dict) else {}
        primary = lesson.get('caseSnapshot')
        if isinstance(primary,dict) and primary.get('versionId'):
            matched = next((x for x in provided if x.get('versionId') == primary['versionId']), {})
            provided = [{**matched,**primary,'role':'lesson','roles':['lesson','retrieval'] if matched else ['lesson']},
                        *[x for x in provided if x.get('versionId') != primary['versionId']]]
        result['sources'] = [{k:x.get(k) for k in ('id','title','source','versionId','version','references','role','roles','knowledgeIds','knowledgeMatches','matchReasons','matchedFields')} for x in provided]
    if capability=='text' and not data.get('guidance') and not data.get('remediation') and context.get('retrieval'):
        result['retrieval']=context['retrieval']
    if capability == "case_extract":
        original = {x['id']: x['text'] for x in data['units']}
        required = {'content'} | {key for key in ('goal','studentBase','difficulty','diagnosis','strategy','effectCheck','introduction','adjustment','boundary') if result.get(key)}
        for key in ('knowledgePoints','steps','questions','responses'):
            required.update(f'{key}.{index}' for index in range(len(result.get(key, []))))
        if not required.issubset({r['field'] for r in result['references']}):
            raise ModelError('教学片段缺少原文引用，不符合结果结构。', retryable=True)
        for item in result['references']:
            if item['unitId'] not in original or ''.join(item['quote'].split()) not in ''.join(original[item['unitId']].split()):
                raise ModelError("原文引用不符合结果结构，请重新提取。", retryable=True)
    phase(job_id, "正在保存结果")
    with SessionLocal.begin() as db:
        job, run = db.get(ModelJob, job_id), db.get(ModelRun, run_id)
        try:require_job_write(db,job)
        except ModelError as error:
            if data.get('guidance'):error.metrics=result.get('workflow',{});error.model=model;error.provider=source
            raise
        if job.status=="cancelled":raise asyncio.CancelledError()
        if capability == "document_ocr":
            from .models import MaterialUnit
            unit = db.get(MaterialUnit, data['unitId'])
            unit.original_text = result['text']
            if not unit.text: unit.text = result['text']
            unit.details = {**unit.details, 'uncertainties': result.get('uncertainties', [])}
        if capability == "case_extract":
            from .models import MaterialUnit
            from .library import create_draft, reference
            refs = [{**reference(db, db.get(MaterialUnit, r['unitId']), r['quote']), 'field':r['field']} for r in result['references']]
            experience = {k: v for k, v in result.items() if k not in ('references','content','title','grade','subject','verification','sources')}
            draft = create_draft(db, {'title': result['title'], 'content': result['content'], 'grade': result['grade'], 'subject': result['subject'], 'source': refs[0]['source'] or refs[0]['materialTitle'], 'author': refs[0]['author'], 'experience': experience, 'references': refs, 'verification': result.get('verification'), 'extractionJobId': job.id})
            result['caseId'] = draft.case_id
        if capability == "tts":
            contents = result.pop("audio")
            file_id, key = "file-" + uuid.uuid4().hex, uuid.uuid4().hex
            folder = storage_dir()
            folder.mkdir(parents=True, exist_ok=True)
            (folder / key).write_bytes(contents)
            db.add(FileAsset(id=file_id, owner_id=job.owner_id, original_name="讲解音频.mp3", content_type=result["contentType"], size=len(contents), storage_key=key))
            db.flush()
            result.update(fileId=file_id, url="/api/files/" + file_id)
        if data.get('remediation') and data.get('mode')=='analysis':
            from .models import WrongQuestion
            row=db.get(WrongQuestion,data['wrongId']);row.details={**(row.details or {}),'planJobId':job.id}
        if capability == "text" and job.record_id and data.get("strategy")!="try" and (not data.get('remediation') or data.get('mode')=='guidance'):
            # Stable ID prevents duplicate helper records if a caller repeats a task.
            help_id = help_record_id(job.id)
            entry=db.get(HelpRecord,help_id)
            message=result['hint']+'\n\n'+'\n'.join(result['steps'])
            if not entry:db.add(HelpRecord(id=help_id,record_id=job.record_id,question=data.get('question'),kind='模型指导',message=message,file_id=job.file_id,attempt_number=data.get('attemptNumber',1)))
            else:entry.kind='模型指导';entry.message=message

        job.result, job.status, job.error = result, "succeeded", ""
        job.active_hash = None
        run.result, run.model, run.provider, run.status, run.ended_at = result, model, source, "succeeded", datetime.utcnow()
        event(db, job, "已完成")


def recover_interrupted():
    with SessionLocal.begin() as db:
        for job in db.scalars(select(ModelJob).where(ModelJob.status == "running")).all():
            job.status, job.error = "failed", "服务中断，输入与已有结果已保留，可手动重试。"
            job.active_hash = None
            event(db, job, "服务中断")
            for run in db.scalars(select(ModelRun).where(ModelRun.job_id == job.id, ModelRun.status == "running")).all():
                run.status, run.error, run.ended_at = "failed", job.error, datetime.utcnow()


async def worker():
    global active_execution,active_job_id
    needs_recovery = False
    while True:
        try:
            if needs_recovery:
                recover_interrupted()
                needs_recovery = False
            with SessionLocal.begin() as db:
                job_id = db.scalar(select(ModelJob.id).where(ModelJob.status == "queued").order_by(ModelJob.created_at).with_for_update(skip_locked=True).limit(1))
                job = db.get(ModelJob,job_id) if job_id else None
                if job:
                    job.status, job.attempt_number = "running", job.attempt_number + 1
                    run_id, job_id = "run-" + uuid.uuid4().hex, job.id
                    db.add(ModelRun(id=run_id, job_id=job.id, number=job.attempt_number))
                    event(db, job, "开始执行")
                else:
                    job_id = None
            if not job_id:
                await asyncio.sleep(.5)
                continue
            try:
                with SessionLocal() as session: agent=session.get(ModelJob,job_id).capability=='lesson_agent'
                active_job_id=job_id
                active_execution=asyncio.create_task(execute(job_id,run_id))
                await asyncio.wait_for(active_execution, timeout=300 if agent else 150)
            except asyncio.CancelledError:
                with SessionLocal.begin() as db:
                    job,run=db.get(ModelJob,job_id),db.get(ModelRun,run_id)
                    if job.status!='cancelled':raise
                    run.status,run.error,run.ended_at='cancelled',job.error or '用户取消',datetime.utcnow()
            except Exception as error:
                if isinstance(error, TimeoutError): error = ModelError("任务执行超时，可重试。", retryable=True)
                known = isinstance(error, ModelError)
                message = str(error) if known else "任务执行失败，输入已保留，请重试。"
                if not known: log.exception("model job failed: %s", job_id)
                with SessionLocal.begin() as db:
                    job=db.scalar(select(ModelJob).where(ModelJob.id==job_id).with_for_update());run=db.get(ModelRun,run_id)
                    if job.status=='cancelled':
                        run.status,run.error,run.ended_at='cancelled',job.error or '用户取消',datetime.utcnow()
                        continue
                    run.status, run.error, run.ended_at = "failed", message, datetime.utcnow()
                    run.model, run.provider = getattr(error, "model", ""), getattr(error, "provider", "")
                    if getattr(error,"metrics",None):run.result={"workflow":error.metrics}
                    again = known and error.retryable and not job.input.get('guidance') and not job.input.get('remediation') and not (job.capability=='text' and job.record_id) and job.retry_count < (1 if job.capability=='lesson_agent' else 2)
                    job.status, job.error = ("queued" if again else "failed"), message
                    if not again: job.active_hash = None
                    if again: job.retry_count += 1
                    event(db, job, "稍后自动重试" if again else "执行失败")
                if again: await asyncio.sleep(min(60, max(2, error.retry_after)))
            finally:
                active_execution=None;active_job_id=None
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("model worker iteration failed")
            needs_recovery = True
            await asyncio.sleep(2)


async def start():
    global worker_task,worker_loop
    worker_loop=asyncio.get_running_loop()
    recover_interrupted()
    worker_task = asyncio.create_task(worker())


async def stop():
    if worker_task:
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError): await worker_task
    recover_interrupted()
    await provider.close()
