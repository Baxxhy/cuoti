from fastapi import HTTPException
from .accounts import current_user
from .database import Database
from .rows import row_json
from .recognition import run_recognition


async def get_job(request):
    with Database.from_environment() as db:
        user = current_user(request, db)
        rows = db.query('SELECT j.* FROM processing_jobs j JOIN questions q ON q.id=j.question_id WHERE j.id=? AND q.user_id=?', [request.path_params['job_id'], user['id']]).rows
        if not rows: raise HTTPException(404, '任务不存在或无权访问')
        return row_json('processing_jobs', rows[0])


async def retry_job(request, background):
    job_id = request.path_params['job_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        owned = db.query('SELECT j.question_id FROM processing_jobs j JOIN questions q ON q.id=j.question_id WHERE j.id=? AND q.user_id=?', [job_id, user['id']]).rows
        if not owned: raise HTTPException(404, '任务不存在或无权访问')
        question_id = owned[0]['question_id']
        with db.transaction():
            questions = db.query('SELECT status FROM questions WHERE id=? AND user_id=? FOR UPDATE', [question_id, user['id']]).rows
            if not questions or questions[0]['status'] == 'archived': raise HTTPException(404, '题目不存在或已归档')
            jobs = db.query('SELECT * FROM processing_jobs WHERE id=? AND question_id=? FOR UPDATE', [job_id, question_id]).rows
            if not jobs: raise HTTPException(404, '任务不存在')
            job = jobs[0]
            if job['status'] != 'failed': raise HTTPException(409, '任务仍在处理或已完成，请刷新后查看结果')
            if job['kind'] not in ['ingest', 'crop', 'ocr', 'reprocess']: raise HTTPException(409, '该任务不支持识别重试')
            active = db.query("SELECT * FROM processing_jobs WHERE question_id=? AND status IN ('pending','running') AND kind IN ('ingest','crop','ocr','reprocess') ORDER BY created_at DESC,id DESC LIMIT 1", [question_id]).rows
            if active: return {**row_json('processing_jobs', active[0]), 'resumed': True}
            assets = db.query("SELECT path,kind FROM question_assets WHERE question_id=? AND (kind='crop' OR (kind='original' AND ?='ingest')) ORDER BY (kind='crop') DESC,created_at DESC,id DESC LIMIT 1", [question_id, job['kind']]).rows
            if not assets: raise HTTPException(422, '缺少识别图片，请重新框选题目')
            db.query("UPDATE processing_jobs SET status='pending',progress=0,error=NULL,updated_at=UTC_TIMESTAMP() WHERE id=?", [job_id])
            db.query("UPDATE questions SET status='processing',updated_at=UTC_TIMESTAMP() WHERE id=?", [question_id])
            result = row_json('processing_jobs', db.query('SELECT * FROM processing_jobs WHERE id=?', [job_id]).rows[0])
        background.add_task(run_recognition, job_id, question_id, assets[0]['path'], assets[0]['kind'] == 'crop')
        return result
