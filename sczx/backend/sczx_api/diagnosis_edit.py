import json

from fastapi import HTTPException

from .accounts import current_user, read_json
from .database import Database
from .diagnosis import sql_value, diagnosis_snapshot, diagnosis_fingerprint, diagnosis_input, save_evidence
from .algorithm import compute
from .knowledge_links import sync_links
from .manual_questions import array
from .question_detail import safe_counterfactual
from .question_edit import text, number
from .questions import _TAXONOMY
from .rows import row_json

_CODES = {code for code, _ in _TAXONOMY} | {'exact','equivalent','branch_solution','necessary_condition','extra_step','formula_selection','unknown','variable_error'}


def validate_correction(body):
    edits = {}
    for key, value in body.items():
        if key == 'first_error_step':
            if value is None: edits[key] = None
            elif type(value) is int:
                if not 0 <= value <= 2147483647: raise HTTPException(422, '错误步骤序号无效')
                edits[key] = value
            else: raise HTTPException(422, '错误步骤序号必须为非负整数或空值')
        elif key in ['first_error_text','root_misconception','error_location','recommended_strategy']:
            edits[key] = text(value, 12000)
        elif key == 'error_type':
            code = text(value, 60)
            if code not in _CODES: raise HTTPException(422, '请选择支持的错误类型')
            edits[key] = code
        elif key == 'confidence':
            confidence = number(value)
            if not 0 <= confidence <= 1: raise HTTPException(422, '置信度超出范围')
            edits[key] = confidence
        elif key == 'missing_prerequisites':
            values = array(body, key, 100)
            for item in values: text(item, 12000)
            edits[key] = values
    return edits


async def correct_diagnosis(request):
    question_id = request.path_params['question_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        body = await read_json(request, 2 * 1024 * 1024); edits = validate_correction(body)
        with db.transaction():
            questions = db.query('SELECT status FROM questions WHERE id=? AND user_id=? FOR UPDATE', [question_id, user['id']]).rows
            if not questions: raise HTTPException(404, '题目不存在或无权访问')
            if questions[0]['status'] == 'archived': raise HTTPException(409, '题目已归档，不能修正诊断')
            rows = db.query('SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1 FOR UPDATE', [question_id]).rows
            if not rows: raise HTTPException(404, '诊断不存在')
            if not edits: raise HTTPException(422, '请提供需要修正的诊断内容')
            if 'first_error_step' in edits:
                index = edits['first_error_step']
                if index is not None:
                    steps = db.query('SELECT s.text FROM student_steps s WHERE s.work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY s.step_index', [question_id]).rows
                    if index >= len(steps): raise HTTPException(422, '错误步骤不在当前作答中，请重新核对')
                    edits['first_error_text'] = steps[index]['text']
                else: edits['first_error_text'] = ''
            current = row_json('diagnoses', rows[0])
            if edits.get('error_type', current['error_type']) in ['exact', 'equivalent']:
                if edits.get('first_error_step') is not None: raise HTTPException(422, '未发现错误时不能同时指定出错步骤')
                edits.update(first_error_step=None, first_error_text='')
            sql = 'UPDATE diagnoses SET user_confirmed=1,correction=?,updated_at=UTC_TIMESTAMP(6)'
            values = [json.dumps(body, ensure_ascii=False)]
            for key, value in edits.items(): sql += f', `{key}`=?'; values.append(sql_value(value))
            db.query(sql + ' WHERE id=?', values + [current['id']])
            return row_json('diagnoses', db.query('SELECT * FROM diagnoses WHERE id=?', [current['id']]).rows[0])


def cached_counterfactual(db, diagnosis_id):
    rows = db.query("SELECT * FROM diagnosis_evidence WHERE diagnosis_id=? AND kind='counterfactual_validation' ORDER BY created_at,id LIMIT 1", [diagnosis_id]).rows
    if not rows: return False, None
    diagnoses = db.query('SELECT * FROM diagnoses WHERE id=?', [diagnosis_id]).rows
    diagnosis = row_json('diagnoses', diagnoses[0]) if diagnoses else {}
    return True, safe_counterfactual(row_json('diagnosis_evidence', rows[0])['metadata_json'], diagnosis)


async def counterfactual_question(request):
    question_id = request.path_params['question_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        with db.transaction():
            value = diagnosis_snapshot(db, question_id, user['id'])
            if value['analysis'] is None or value['diagnosis'] is None: raise HTTPException(404, '题目诊断不存在')
            found, cached = cached_counterfactual(db, value['diagnosis']['id'])
        if found: return cached
        payload = diagnosis_input(value, include_images=False); payload['operation'] = 'counterfactual'
        computed = compute(payload)
        with db.transaction():
            current = diagnosis_snapshot(db, question_id, user['id'])
            if diagnosis_fingerprint(current) != diagnosis_fingerprint(value): raise HTTPException(409, '题目或诊断已变化，请重新验证')
            diagnosis = current['diagnosis']
            found, cached = cached_counterfactual(db, diagnosis['id'])
            if found: return cached
            save_evidence(db, diagnosis['id'], current, computed, include_alignment=False)
            sync_links(db, current['question'], current['analysis'], diagnosis)
            return safe_counterfactual(computed['counterfactual'], diagnosis)
