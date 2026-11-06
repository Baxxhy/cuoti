"""Durable recognition jobs; stale results never replace edited questions."""
import base64
import hashlib
import json
import logging

from .algorithm import compute, image_bytes
from .database import Database
from .question_edit import _INVALIDATIONS
from .security import new_id
from .storage import read_media, write_media, remove_media

logger = logging.getLogger(__name__)


def fingerprint(row):
    return hashlib.sha256(json.dumps([row[k] for k in ['question_text', 'student_answer', 'subject', 'grade', 'formulas', 'options', 'question_type', 'knowledge_points', 'confirmed']], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def short_title(value, limit=60):
    if not value: return '待确认错题'
    prefix = value[:limit]
    if len(value) > limit:
        markers = [prefix.index(c) for c in ['$', '\\'] if c in prefix]
        if markers:
            before = prefix[:min(markers)]
            return before + '…' if before.strip() else '题目详情'
    return prefix


def fail_job(job_id, question_id, expected='', recovered=False):
    try:
        with Database.from_environment() as db, db.transaction():
            questions = db.query('SELECT * FROM questions WHERE id=? FOR UPDATE', [question_id]).rows
            jobs = db.query('SELECT status FROM processing_jobs WHERE id=? AND question_id=? FOR UPDATE', [job_id, question_id]).rows
            if not questions or not jobs or jobs[0]['status'] not in ['pending', 'running']: return
            cancelled = questions[0]['status'] == 'archived' or bool(expected and fingerprint(questions[0]) != expected)
            message = '题目已修改或归档，识别结果未应用' if cancelled else '识别任务因服务重启中断，请重试' if recovered else '识别暂时未完成，请检查图片后重试'
            db.query('UPDATE processing_jobs SET status=?,error=?,updated_at=UTC_TIMESTAMP() WHERE id=?', ['cancelled' if cancelled else 'failed', message, job_id])
            if not cancelled and (not recovered or questions[0]['status'] in ['processing', 'pending', 'awaiting_crop']):
                db.query("UPDATE questions SET status='partial',updated_at=UTC_TIMESTAMP() WHERE id=?", [question_id])
    except Exception:
        logger.warning('Recognition failure state could not be persisted')


def recover_jobs():
    try:
        with Database.from_environment() as db:
            jobs = db.query("SELECT id,question_id FROM processing_jobs WHERE status IN ('pending','running') AND kind IN ('ingest','crop','ocr','reprocess') ORDER BY question_id,id").rows
        for job in jobs: fail_job(job['id'], job['question_id'], recovered=True)
    except Exception:
        logger.warning('Recognition recovery deferred: database unavailable')


def run_recognition(job_id, question_id, image_path, require_crop=False):
    files, committed, expected = [], False, ''
    try:
        with Database.from_environment() as db:
            with db.transaction():
                questions = db.query('SELECT * FROM questions WHERE id=? FOR UPDATE', [question_id]).rows
                jobs = db.query('SELECT status FROM processing_jobs WHERE id=? AND question_id=? FOR UPDATE', [job_id, question_id]).rows
                if not questions or not jobs or jobs[0]['status'] != 'pending': return
                if questions[0]['status'] == 'archived':
                    db.query("UPDATE processing_jobs SET status='cancelled',error='题目已归档',updated_at=UTC_TIMESTAMP() WHERE id=?", [job_id]); return
                sources = db.query('SELECT id FROM question_assets WHERE question_id=? AND path=? AND kind=?', [question_id, image_path, 'crop' if require_crop else 'original']).rows
                if not sources: raise ValueError('missing source asset')
                db.query("UPDATE processing_jobs SET status='running',progress=15,error=NULL,updated_at=UTC_TIMESTAMP() WHERE id=?", [job_id])
                expected = fingerprint(questions[0])
            payload = {'operation': 'preprocess', 'image_base64': base64.b64encode(read_media(image_path)).decode()}
            prepared = compute(payload)
            db.query("UPDATE processing_jobs SET progress=45,updated_at=UTC_TIMESTAMP() WHERE id=? AND status='running'", [job_id])
            computed = compute({**payload, 'operation': 'recognize'})
            recognition = computed['recognition']
            assets = []
            for raw in prepared['assets'] + computed['assets']:
                asset = dict(raw)
                kind = asset['kind']
                if kind not in ['clean', 'red_mask', 'overlay', 'question_figure', 'student_working_figure', 'teacher_annotation_region']:
                    raise ValueError('invalid asset kind')
                path = f'uploads/{question_id}/derived/{new_id()}.' + ('png' if kind == 'red_mask' else 'jpg')
                write_media(path, image_bytes(asset)); files.append(path)
                asset['path'] = path; assets.append(asset)
            with db.transaction():
                questions = db.query('SELECT * FROM questions WHERE id=? FOR UPDATE', [question_id]).rows
                jobs = db.query('SELECT status FROM processing_jobs WHERE id=? AND question_id=? FOR UPDATE', [job_id, question_id]).rows
                if not questions or not jobs or jobs[0]['status'] != 'running': return
                if questions[0]['status'] == 'archived' or fingerprint(questions[0]) != expected:
                    db.query("UPDATE processing_jobs SET status='cancelled',error='题目已修改或归档，识别结果未应用',updated_at=UTC_TIMESTAMP() WHERE id=?", [job_id]); return
                for sql in _INVALIDATIONS: db.query(sql, [question_id])
                db.query('DELETE FROM teacher_marks WHERE question_id=?', [question_id])
                db.query("DELETE FROM question_assets WHERE question_id=? AND kind IN ('question_figure','student_working_figure','teacher_annotation_region')", [question_id])
                for asset in assets:
                    db.query('INSERT INTO question_assets (id,question_id,kind,path,sha256,role,bbox,description,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())', [new_id(), question_id, asset['kind'], asset['path'], asset['sha256'], asset.get('role'), json.dumps(asset.get('bbox', [])), asset.get('description')])
                confidence = recognition['recognition_confidence']
                db.query("INSERT INTO ocr_runs (id,question_id,provider,raw_result,confidence,stream,status,model_name,duration_ms,error,created_at,updated_at) VALUES (?,?,'qwen-pool',?,?,'qwen_crop','completed','Qwen',?,NULL,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [new_id(), question_id, json.dumps(recognition, ensure_ascii=False), confidence, computed['duration_ms']])
                text = recognition['question_text']
                db.query("UPDATE questions SET confirmed=0,question_text=?,student_answer=?,subject=?,grade=?,question_type=?,formulas=JSON_ARRAY(),options=?,title=?,status='needs_confirmation',updated_at=UTC_TIMESTAMP() WHERE id=?", [text, recognition.get('student_answer'), recognition['subject'], recognition.get('grade'), recognition['question_type'], json.dumps(recognition['options'], ensure_ascii=False), short_title(text), question_id])
                work = new_id()
                db.query("INSERT INTO student_works (id,question_id,user_id,answer,explanation,created_at,updated_at) VALUES (?,?,?,?,'',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))", [work, question_id, questions[0]['user_id'], recognition.get('student_answer') or ''])
                for step in recognition['student_steps']:
                    text = step['text']
                    db.query("INSERT INTO student_steps (id,work_id,step_index,text,bbox,raw_text,normalized_text,formula,confidence,source,user_confirmed,created_at,updated_at) VALUES (?,?,?,?,JSON_ARRAY(),?,?,?,?,'qwen_crop',0,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [new_id(), work, step['index'] - 1, text, text, ' '.join(text.split()), text if '=' in text else '', confidence])
                for mark in recognition['teacher_annotations']:
                    db.query("INSERT INTO teacher_marks (id,question_id,mark_type,comment,bbox,confidence,source,created_at,updated_at) VALUES (?,?,?,?,JSON_ARRAY(),?,'qwen_crop',UTC_TIMESTAMP(),UTC_TIMESTAMP())", [new_id(), question_id, mark['type'], mark['text'], confidence])
                db.query("UPDATE processing_jobs SET status='completed',progress=100,error=NULL,updated_at=UTC_TIMESTAMP() WHERE id=?", [job_id])
            committed = True
    except Exception:
        fail_job(job_id, question_id, expected)
    finally:
        if not committed:
            for path in files:
                try: remove_media(path)
                except OSError: pass
