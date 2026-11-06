import base64
import json

from fastapi import HTTPException

from .accounts import current_user, read_json
from .algorithm import compute
from .database import Database
from .knowledge_links import sync_links
from .manual_questions import array
from .question_detail import query_array
from .question_edit import _INVALIDATIONS, text as edit_text
from .rows import row_json
from .security import new_id
from .storage import read_media


def snapshot(db, question_id, owner):
    rows = db.query('SELECT * FROM questions WHERE id=? AND user_id=? FOR UPDATE', [question_id, owner]).rows
    if not rows or rows[0]['status'] == 'archived': raise HTTPException(404, '题目不存在或已归档')
    question = row_json('questions', rows[0])
    if not question['confirmed'] or not question['question_text'].strip(): raise HTTPException(409, '请先核对并确认题目文字，再开始分析')
    def query(table, sql): return query_array(db, table, sql, question_id)
    works = query('student_works', 'SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1')
    analyses = query('problem_analyses', 'SELECT * FROM problem_analyses WHERE question_id=?')
    return {'question': question, 'work': works[0] if works else None,
            'steps': query('student_steps', 'SELECT s.* FROM student_steps s WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id'),
            'assets': query('question_assets', "SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id"),
            'analysis': analyses[0] if analyses else None}


def fingerprint(value):
    question = value['question']
    return [question[k] for k in ['question_text', 'subject', 'grade', 'question_type', 'student_answer', 'options', 'knowledge_points', 'confirmed', 'status']] + [value[k] for k in ['work', 'steps', 'assets', 'analysis']]


def images(value):
    seen, result = set(), []
    for asset in value['assets']:
        path = asset['path']
        if path not in seen:
            result.append(base64.b64encode(read_media(path)).decode()); seen.add(path)
    return result


async def analyze_question(request):
    question_id = request.path_params['question_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        with db.transaction(): initial = snapshot(db, question_id, user['id'])
        question = initial['question']
        payload = {'operation': 'analyze', 'text': question['question_text'], 'grade': question['grade'] or '', 'student_steps': [s['text'] for s in initial['steps']], 'images_base64': images(initial)}
        payload.update({k: question[k] for k in ['subject', 'question_type', 'student_answer', 'options']})
        computed = compute(payload); analysis = computed['analysis']
        references, valid = analysis['reference_steps'], computed['reference_math_valid']
        if len(references) != len(valid) or not analysis['final_answer'].strip(): raise HTTPException(503, '分析结果不完整')
        with db.transaction():
            current = snapshot(db, question_id, user['id'])
            if fingerprint(current) != fingerprint(initial): raise HTTPException(409, '题目或作答已变化，请重新分析')
            for sql in _INVALIDATIONS: db.query(sql, [question_id])
            analysis_id = new_id()
            db.query('INSERT INTO problem_analyses (id,question_id,subject,problem_type,known_conditions,goal,knowledge_points,prerequisites,final_answer,verified,raw_result,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())', [analysis_id, question_id, analysis['subject'], analysis['problem_type'], json.dumps(analysis['known_conditions'], ensure_ascii=False), analysis['goal'], json.dumps(analysis['knowledge_points'], ensure_ascii=False), json.dumps(analysis['prerequisites'], ensure_ascii=False), analysis['final_answer'], int(analysis['answer_verified']), json.dumps(analysis, ensure_ascii=False)])
            for index, text in enumerate(references):
                equation = '=' in text
                db.query('INSERT INTO reference_steps (id,analysis_id,step_index,text,expression,explanation,math_valid,uses_condition,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())', [new_id(), analysis_id, index, text, text if equation else None, '由题目条件进行等价变形' if equation else '推理步骤', int(valid[index]), int(index == 0)])
            sync_links(db, question, analysis)
            db.query("UPDATE questions SET status='analyzed',updated_at=UTC_TIMESTAMP() WHERE id=?", [question_id])
            result = row_json('problem_analyses', db.query('SELECT * FROM problem_analyses WHERE id=?', [analysis_id]).rows[0])
            result['reference_steps'] = references
            return result


async def submit_work(request):
    question_id = request.path_params['question_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        body = await read_json(request, 8 * 1024 * 1024)
        answer = edit_text(body.get('answer', ''), 12000)
        explanation = edit_text(body.get('explanation', ''), 12000)
        steps = array(body, 'steps', 100)
        for step in steps: edit_text(step, 12000)
        with db.transaction():
            rows = db.query('SELECT status FROM questions WHERE id=? AND user_id=? FOR UPDATE', [question_id, user['id']]).rows
            if not rows: raise HTTPException(404, '题目不存在或无权访问')
            if rows[0]['status'] == 'archived': raise HTTPException(409, '题目已归档，不能提交作答')
            for sql in _INVALIDATIONS: db.query(sql, [question_id])
            db.query("UPDATE processing_jobs SET status='cancelled',error='已提交新作答，旧识别结果未应用',updated_at=UTC_TIMESTAMP() WHERE question_id=? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running')", [question_id])
            db.query("UPDATE questions SET student_answer=?,status=IF(confirmed,'confirmed','needs_confirmation'),updated_at=UTC_TIMESTAMP() WHERE id=?", [answer or None, question_id])
            work_id = new_id()
            db.query('INSERT INTO student_works (id,question_id,user_id,answer,explanation,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))', [work_id, question_id, user['id'], answer, explanation])
            for index, text in enumerate(steps):
                db.query("INSERT INTO student_steps (id,work_id,step_index,text,bbox,raw_text,normalized_text,formula,confidence,source,user_confirmed,created_at,updated_at) VALUES (?,?,?,?,JSON_ARRAY(),?,?,?,1,'user',1,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [new_id(), work_id, index, text, text, ' '.join(text.split()), text if '=' in text else ''])
            return row_json('student_works', db.query('SELECT * FROM student_works WHERE id=?', [work_id]).rows[0])
