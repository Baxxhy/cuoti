import base64
import json

from fastapi import HTTPException

from .accounts import current_user, read_json, secret
from .algorithm import compute, image_bytes
from .database import Database
from .question_detail import asset_crop, read_question
from .recognition import run_recognition
from .rows import row_json
from .security import media_url, new_id
from .storage import read_media, write_media, remove_media


def crop_box(body):
    try:
        raw = body['box']
        if not isinstance(raw, list) or len(raw) != 4 or any(isinstance(x, bool) for x in raw): raise ValueError
        x, y, w, h = map(float, raw)
        if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 and 0 < h <= 1 and x+w <= 1.000001 and y+h <= 1.000001): raise ValueError
        return [x, y, w, h]
    except (KeyError, ValueError, TypeError, OverflowError):
        raise HTTPException(422, '裁剪范围无效，请重新框选题目') from None


async def crop_question(request, background):
    question_id, files = request.path_params['question_id'], []
    try:
        with Database.from_environment() as db:
            user = current_user(request, db)
            box = crop_box(await read_json(request))
            with db.transaction():
                rows = db.query('SELECT status FROM questions WHERE id=? AND user_id=? FOR UPDATE', [question_id, user['id']]).rows
                if not rows or rows[0]['status'] == 'archived': raise HTTPException(404, '题目不存在或已归档')
                active = db.query("SELECT id,status FROM processing_jobs WHERE question_id=? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running') ORDER BY created_at DESC,id DESC LIMIT 1", [question_id]).rows
                old = db.query("SELECT * FROM question_assets WHERE question_id=? AND kind='crop' ORDER BY created_at DESC,id DESC LIMIT 1", [question_id]).rows
                if active:
                    if not old: raise HTTPException(409, '已有识别任务正在处理，请先查看结果再调整范围')
                    asset = row_json('question_assets', old[0]); stored = asset_crop([asset])
                    if stored is None: raise HTTPException(409, '已有识别任务正在处理')
                    if any(abs(a-b) > .000001 for a, b in zip(stored, box)): raise HTTPException(409, '已有识别任务正在处理，请先查看结果再调整范围')
                    return {**asset, 'url': media_url('/' + asset['path'], secret()), 'job_id': active[0]['id'], 'status': active[0]['status'], 'resumed': True, 'crop_box': stored}
                originals = db.query("SELECT path FROM question_assets WHERE question_id=? AND kind='original' ORDER BY created_at,id LIMIT 1", [question_id]).rows
                if not originals: raise HTTPException(404, '原图不存在')
                computed = compute({'operation': 'crop', 'box': box, 'image_base64': base64.b64encode(read_media(originals[0]['path'])).decode()})
                if computed.get('kind') != 'crop': raise HTTPException(503, '裁剪结果无效')
                path = f'uploads/{question_id}/crops/{new_id()}.jpg'
                write_media(path, image_bytes(computed)); files.append(path)
                x, y, w, h = box
                bbox = json.dumps([x, y, min(1, x+w), min(1, y+h)])
                asset_id = old[0]['id'] if old else new_id()
                if old:
                    db.query('UPDATE question_assets SET path=?,sha256=?,bbox=?,updated_at=UTC_TIMESTAMP() WHERE id=?', [path, computed['sha256'], bbox, asset_id])
                else:
                    db.query("INSERT INTO question_assets (id,question_id,kind,path,sha256,bbox,created_at,updated_at) VALUES (?,?,'crop',?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [asset_id, question_id, path, computed['sha256'], bbox])
                job_id = new_id()
                db.query("INSERT INTO processing_jobs (id,question_id,kind,status,progress,created_at,updated_at) VALUES (?,?,'crop','pending',0,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [job_id, question_id])
                db.query("UPDATE questions SET status='processing',updated_at=UTC_TIMESTAMP() WHERE id=?", [question_id])
                asset = row_json('question_assets', db.query('SELECT * FROM question_assets WHERE id=?', [asset_id]).rows[0])
                result = {**asset, 'url': media_url('/' + path, secret()), 'geometry': computed['geometry'], 'original_preserved': True, 'job_id': job_id, 'status': 'pending'}
            files.clear()
            background.add_task(run_recognition, job_id, question_id, path, True)
            return result
    finally:
        for path in files:
            try: remove_media(path)
            except OSError: pass


async def start_recognition(request, background, synchronous=False):
    question_id = request.path_params['question_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        path = None
        with db.transaction():
            questions = db.query('SELECT status FROM questions WHERE id=? AND user_id=? FOR UPDATE', [question_id, user['id']]).rows
            if not questions or questions[0]['status'] == 'archived': raise HTTPException(404, '题目不存在或已归档')
            active = db.query("SELECT * FROM processing_jobs WHERE question_id=? AND status IN ('pending','running') AND kind IN ('ingest','crop','ocr','reprocess') ORDER BY created_at DESC,id DESC LIMIT 1", [question_id]).rows
            if active:
                job_id = active[0]['id']
            else:
                assets = db.query("SELECT path FROM question_assets WHERE question_id=? AND kind='crop' ORDER BY created_at DESC,id DESC LIMIT 1", [question_id]).rows
                if not assets: raise HTTPException(422, '请先框选题目，生成裁剪图片后再识别')
                job_id, path = new_id(), assets[0]['path']
                db.query("INSERT INTO processing_jobs (id,question_id,kind,status,progress,created_at,updated_at) VALUES (?,?,?,'pending',0,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [job_id, question_id, 'ocr' if synchronous else 'reprocess'])
                db.query("UPDATE questions SET status='processing',updated_at=UTC_TIMESTAMP() WHERE id=?", [question_id])
        if path:
            if synchronous: run_recognition(job_id, question_id, path, True)
            else: background.add_task(run_recognition, job_id, question_id, path, True)
        if synchronous:
            result = {'job': row_json('processing_jobs', db.query('SELECT * FROM processing_jobs WHERE id=?', [job_id]).rows[0]), 'question': await read_question(request)}
        else: result = {'job_id': job_id}
        if path is None: result['resumed'] = True
        return result
