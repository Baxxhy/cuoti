"""Question edit validation and dependent-learning invalidation."""
import json
import math

from fastapi import HTTPException

from .accounts import current_user, read_json
from .database import Database
from .rows import row_json


def text(value, limit, minimum=0, trim=False, nullable=False):
    if value is None and nullable:
        return None
    if isinstance(value, str):
        clean = value.strip() if trim else value
        if minimum <= len(clean) <= limit:
            return clean
    raise HTTPException(422, '输入文字格式或长度不正确')


def number(value):
    try:
        if not isinstance(value, (str, int, float)):
            raise ValueError
        result = float(value)
        if not math.isfinite(result):
            raise HTTPException(422, '数字必须有限')
        return result
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(422, '数字格式不正确') from None


def flag(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        if value.lower() in ['1', 'true', 't', 'yes', 'y', 'on']:
            return True
        if value.lower() in ['0', 'false', 'f', 'no', 'n', 'off']:
            return False
    raise HTTPException(422, '收藏状态格式不正确')


def validate_steps(items, teacher):
    for item in items:
        if isinstance(item, str):
            text(item, 12000)
            continue
        if not isinstance(item, dict):
            raise HTTPException(422, '步骤格式不正确')
        for key in ['comment'] if teacher else ['text', 'raw_text', 'normalized_text', 'formula']:
            if key in item:
                text(item[key], 12000)
        key = 'mark_type' if teacher else 'source'
        if key in item:
            text(item[key], 50)
        if 'confidence' in item and not 0 <= number(item['confidence']) <= 1:
            raise HTTPException(422, '置信度超出范围')
        if 'bbox' in item:
            if not isinstance(item['bbox'], list):
                raise HTTPException(422, '坐标格式不正确')
            if len(item['bbox']) > 4:
                raise HTTPException(422, '坐标数量不正确')
            for coordinate in item['bbox']:
                number(coordinate)


def validate_edit(body):
    edits = {}
    fields = {'question_text': (12000, 1, True, False), 'student_answer': (12000, 0, False, True),
              'grade': (30, 0, False, True), 'subject': (30, 1, True, False),
              'question_type': (50, 1, False, False), 'title': (255, 0, False, False)}
    arrays = ['tags', 'formulas', 'knowledge_points', 'options', 'student_steps', 'teacher_marks']
    for key, value in body.items():
        if key in fields:
            edits[key] = text(value, *fields[key])
        elif key == 'favorite':
            edits[key] = flag(value)
        elif key in arrays:
            limit = 26 if key == 'options' else 50 if key in ['tags', 'knowledge_points'] else 100
            if not isinstance(value, list) or len(value) > limit:
                raise HTTPException(422, f'{key} 格式或数量不正确')
            if key in ['student_steps', 'teacher_marks']:
                validate_steps(value, key == 'teacher_marks')
                continue
            clean, labels = [], set()
            for item in value:
                if key == 'options':
                    if not isinstance(item, dict):
                        raise HTTPException(422, '选项格式不正确')
                    label = text(item.get('label'), 8, 1, True)
                    if label in labels:
                        raise HTTPException(422, '选项标记不能重复')
                    labels.add(label)
                    clean.append({'label': label, 'text': text(item.get('text'), 12000)})
                elif key == 'formulas':
                    clean.append(text(item, 12000))
                else:
                    clean.append(text(item, 30, 1, True))
            edits[key] = clean
    return edits


_INVALIDATIONS = [
    'DELETE e FROM diagnosis_evidence e JOIN diagnoses d ON e.diagnosis_id = d.id WHERE d.question_id = ?',
    'DELETE FROM diagnoses WHERE question_id = ?',
    'DELETE s FROM reference_steps s JOIN problem_analyses a ON s.analysis_id = a.id WHERE a.question_id = ?',
    'DELETE FROM problem_analyses WHERE question_id = ?',
    'DELETE FROM user_question_knowledge_links WHERE question_id = ?',
    'DELETE FROM practice_recommendations WHERE mistake_id = ?',
    "UPDATE tutor_sessions SET state = JSON_SET(IF(JSON_TYPE(state) = 'OBJECT', state, JSON_OBJECT()), '$.question_changed', CAST('true' AS JSON)), updated_at = UTC_TIMESTAMP() WHERE question_id = ?",
    "UPDATE review_plans SET status = 'cancelled', updated_at = UTC_TIMESTAMP() WHERE question_id = ? AND status = 'pending'",
    "UPDATE dataset_practice_attempts SET grading_details = JSON_SET(IF(JSON_TYPE(grading_details) = 'OBJECT', grading_details, JSON_OBJECT()), '$.question_changed', CAST('true' AS JSON)), updated_at = UTC_TIMESTAMP() WHERE mistake_id = ?",
    "UPDATE review_records r JOIN review_plans p ON r.plan_id = p.id SET r.grading_details = JSON_SET(IF(JSON_TYPE(r.grading_details) = 'OBJECT', r.grading_details, JSON_OBJECT()), '$.question_changed', CAST('true' AS JSON)), r.updated_at = UTC_TIMESTAMP() WHERE p.question_id = ?",
]


async def edit_question(request):
    question_id = request.path_params['question_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        body = await read_json(request, 8 * 1024 * 1024)
        with db.transaction():
            rows = db.query('SELECT * FROM questions WHERE id = ? AND user_id = ? FOR UPDATE', [question_id, user['id']]).rows
            if not rows:
                raise HTTPException(404, '内容不存在或无权访问')
            if rows[0]['status'] == 'archived':
                raise HTTPException(409, '题目已归档，不能修改')
            edits = validate_edit(body)
            existing = row_json('questions', rows[0])
            if 'options' in edits or 'question_type' in edits:
                kind = edits.get('question_type', existing['question_type'])
                options = edits.get('options', existing['options'])
                if kind in ['单选题', '多选题'] and len(options) < 2:
                    raise HTTPException(422, '选择题至少需要两个不同选项')
            changed = any(key in edits and existing[key] != edits[key] for key in ['question_text', 'student_answer', 'subject', 'grade', 'formulas', 'options', 'question_type', 'knowledge_points'])
            if changed:
                for sql in _INVALIDATIONS:
                    db.query(sql, [question_id])
            if any(existing[key] != value for key, value in edits.items()):
                sql = 'UPDATE questions SET updated_at = UTC_TIMESTAMP()'
                params = []
                for key, value in edits.items():
                    sql += f', `{key}` = ?'
                    params.append(json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else int(value) if isinstance(value, bool) else value)
                if changed:
                    sql += ", status = IF(confirmed, 'confirmed', 'needs_confirmation')"
                db.query(sql + ' WHERE id = ?', params + [question_id])
            return row_json('questions', db.query('SELECT * FROM questions WHERE id = ?', [question_id]).rows[0])
