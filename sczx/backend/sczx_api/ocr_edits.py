import json

from fastapi import HTTPException

from .accounts import current_user, read_json
from .database import Database
from .manual_questions import array
from .question_detail import read_question
from .question_edit import validate_edit, number, _INVALIDATIONS
from .rows import row_json
from .security import new_id


def step_object(item, teacher=False):
    return item if isinstance(item, dict) else {'comment' if teacher else 'text': item}


def step_text(item):
    item = step_object(item)
    return item.get('text', item.get('raw_text', ''))


def choice_answer(steps, options):
    texts = [step_text(s).strip().upper() for s in steps if step_text(s).strip()]
    if len(texts) != 1: return None
    known = {o.get('label', o.get('key', '')).upper() for o in options if isinstance(o, dict)}
    labels, expect_label = [], True
    for char in texts[0]:
        if char.isspace(): continue
        if expect_label:
            if char not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' or (known and char not in known): return None
            if char not in labels: labels.append(char)
        elif char not in '、,，': return None
        expect_label = not expect_label
    return '、'.join(labels) if labels and not expect_label else None


async def save_ocr_edits(request, confirm):
    question_id = request.path_params['question_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        body = await read_json(request, 8 * 1024 * 1024, default_empty=True)
        validated = validate_edit(body)
        with db.transaction():
            rows = db.query('SELECT * FROM questions WHERE id=? AND user_id=? FOR UPDATE', [question_id, user['id']]).rows
            if not rows: raise HTTPException(404, '题目不存在或无权访问')
            if rows[0]['status'] == 'archived': raise HTTPException(409, '题目已归档，不能修改')
            existing = row_json('questions', rows[0])
            edits = {k: validated[k] for k in ['question_text', 'subject', 'formulas', 'options', 'question_type', 'knowledge_points'] if k in validated}
            steps = array(body, 'student_steps', 100)
            answer = (validated.get('student_answer') or '').strip()
            kind = edits.get('question_type', existing['question_type'])
            normalized_steps = steps
            if not answer and ('选择' in kind or 'choice' in kind.lower() or 'multiple' in kind.lower()):
                inferred = choice_answer(steps, edits.get('options', existing['options']))
                if inferred:
                    answer, normalized_steps = inferred, []
            if 'student_answer' in validated: edits['student_answer'] = answer or None
            if 'grade' in validated:
                grade = validated['grade']
                edits['grade'] = None if grade is None or grade == '' else grade.strip()
            changed = any(existing[k] != v for k, v in edits.items())
            if 'student_steps' in body:
                previous = db.query('SELECT s.text FROM student_steps s WHERE s.work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY s.step_index', [question_id]).rows
                changed = changed or [s['text'] for s in previous] != [step_text(s) for s in normalized_steps]
                work = new_id()
                db.query("INSERT INTO student_works (id,question_id,user_id,answer,explanation,created_at,updated_at) VALUES (?,?,?,?,'',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))", [work, question_id, user['id'], edits.get('student_answer', existing['student_answer']) or ''])
                for index, raw in enumerate(normalized_steps):
                    item = step_object(raw); text = step_text(item)
                    db.query('INSERT INTO student_steps (id,work_id,step_index,text,bbox,raw_text,normalized_text,formula,confidence,source,user_confirmed,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,1,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))', [new_id(), work, index, text, json.dumps([number(n) for n in item.get('bbox', [])]), item.get('raw_text', text), ' '.join(text.split()), text if '=' in text else '', number(item.get('confidence', 1)), item.get('source', 'user')])
            if 'teacher_marks' in body:
                db.query('DELETE FROM teacher_marks WHERE question_id=?', [question_id])
                for raw in array(body, 'teacher_marks', 100):
                    item = step_object(raw, True)
                    db.query("INSERT INTO teacher_marks (id,question_id,mark_type,comment,bbox,confidence,source,created_at,updated_at) VALUES (?,?,?,?,?,?,'user',UTC_TIMESTAMP(),UTC_TIMESTAMP())", [new_id(), question_id, item.get('mark_type', 'comment'), item.get('comment', ''), json.dumps([number(n) for n in item.get('bbox', [])]), number(item.get('confidence', 1))])
            text = edits.get('question_text', existing['question_text'])
            if confirm and not text.strip(): raise HTTPException(422, '请先补充题目文字再确认')
            db.query("UPDATE processing_jobs SET status='cancelled',error='题目已人工核对，旧识别结果未应用',updated_at=UTC_TIMESTAMP() WHERE question_id=? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running')", [question_id])
            if changed:
                for sql in _INVALIDATIONS: db.query(sql, [question_id])
            sql = 'UPDATE questions SET updated_at=UTC_TIMESTAMP(),status=?'
            params = ['confirmed' if confirm else 'ocr_draft']
            if confirm: sql += ',confirmed=1'
            for key, value in edits.items():
                sql += f', `{key}`=?'
                params.append(json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value)
            db.query(sql + ' WHERE id=?', params + [question_id])
    return await read_question(request)
