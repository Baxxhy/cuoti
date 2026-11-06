"""Manual recording with server-owned study snapshots and atomic work records."""
import hashlib
import json
import os
from pathlib import Path

from fastapi import HTTPException

from .accounts import current_user, read_json, text_field
from .database import Database
from .security import new_id


def optional_text(body, key):
    value = body.get(key, '')
    if not isinstance(value, str):
        raise HTTPException(422, f'{key} 必须是文字')
    if len(value) > 36:
        raise HTTPException(422, f'{key} 长度不正确')
    return value


def answer_text(value):
    if value is None: return ''
    if isinstance(value, str): return value
    if isinstance(value, list): return '、'.join(map(answer_text, value))
    if isinstance(value, dict): return '；'.join(k + '：' + answer_text(v) for k, v in value.items())
    return json.dumps(value, ensure_ascii=False)


def display_options(source):
    result = []
    for raw in source.get('options', []):
        option = dict(raw) if isinstance(raw, dict) else {'text': answer_text(raw)}
        if 'text' not in option:
            option['text'] = option.get('content', option.get('value', ''))
        result.append(option)
    return result


def image_layout(source):
    count = len(source.get('image_paths', []))
    stem = source.get('question_text', '').count('<ImageHere>')
    options = [str(o.get('text', '')).count('<ImageHere>') for o in display_options(source)]
    total = stem + sum(options) + answer_text(source.get('answer')).count('<ImageHere>') + source.get('solution', '').count('<ImageHere>')
    visual = source.get('source_metadata', {}).get('has_visual') is True
    review = total != count and (total > 0 or visual)
    public = count if total == 0 and not visual else stem + sum(options)
    return review, list(range(min(public, count)))


def owned_study(db, session_id, owner, lock=False):
    rows = db.query('SELECT * FROM study_sessions WHERE id=? AND user_id=?' + (' FOR UPDATE' if lock else ''), [session_id, owner]).rows
    if not rows:
        raise HTTPException(404, '没有找到这次练习或考试')
    return rows[0]


def study_source(db, owner, body):
    session_id, item_id = optional_text(body, 'study_session_id'), optional_text(body, 'study_item_id')
    if not session_id and not item_id:
        return {}
    session = owned_study(db, session_id, owner)
    if session['status'] != 'submitted':
        raise HTTPException(409, '请先交卷再加入错题本')
    rows = db.query('SELECT * FROM study_session_items WHERE session_id=? ORDER BY position', [session_id]).rows
    for row in rows:
        if row['id'] != item_id: continue
        grading = json.loads(row['grading'] or '{}')
        if grading.get('correct') is not False:
            raise HTTPException(422, '此题尚未判错')
        source = json.loads(row['snapshot'])
        review, _ = image_layout(source)
        unavailable = review or source.get('quality_status') == 'format_review'
        current = db.query('SELECT quality_status,source_metadata FROM dataset_questions WHERE id=?', [source['id']]).rows
        if current:
            metadata = json.loads(current[0]['source_metadata'])
            unavailable = unavailable or current[0]['quality_status'] == 'format_review' or any(e.get('content_hash') == source.get('content_hash', '') for e in metadata.get('format_review_history', []))
        if unavailable: raise HTTPException(409, '此题已暂停使用')
        for key in ['question_text', 'subject', 'grade']: body[key] = source.get(key)
        options = display_options(source)
        if len(options) > 8: raise HTTPException(422, '选项数量超过支持范围')
        for index, option in enumerate(options):
            label = option.get('label') or option.get('key') or 'ABCDEFGH'[index]
            option['label'] = label
            if not option.get('text'): option['text'] = f'见选项{label}配图'
        kind = source.get('question_type', '')
        multiple = '多' in kind or kind in ['multiple_choice', 'multiple-response', 'multiple_response', 'multi_choice', 'multi-select']
        body.update(options=options, question_type='综合题' if not options else '多选题' if multiple else '单选题',
                    student_answer=answer_text(json.loads(row['student_answer']) if row['student_answer'] else None), student_steps=[])
        return source
    raise HTTPException(404, '没有找到这道练习题')


def image_suffix(data):
    for magic, suffix in [(b'\x89PNG\r\n\x1a\n', 'png'), (b'\xff\xd8\xff', 'jpg'), (b'GIF87a', 'gif'), (b'GIF89a', 'gif'), (b'BM', 'bmp'), (b'II*\0', 'tif'), (b'MM\0*', 'tif')]:
        if data.startswith(magic): return suffix
    return 'webp' if data.startswith(b'RIFF') and data[8:12] == b'WEBP' else 'bin'


def copy_figures(db, question_id, source, copied):
    _, indices = image_layout(source)
    bank = Path(os.environ.get('SCZX_QUESTION_BANK_ROOT', 'data/question_bank_assets')).absolute()
    media = Path(os.environ.get('SCZX_MEDIA_ROOT', 'media')).absolute()
    for index in indices:
        original = Path(source['image_paths'][index]).absolute()
        try:
            relative = original.relative_to(bank)
        except ValueError:
            raise HTTPException(422, '题库配图路径无效') from None
        # Open each component without following symlinks, as the original media API does.
        fd = os.open(bank, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in relative.parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd); fd = child
            file_fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            with os.fdopen(file_fd, 'rb') as file:
                size = os.fstat(file.fileno()).st_size
                if not 0 < size <= 64 * 1024 * 1024: raise HTTPException(422, '题库配图大小无效')
                data = file.read()
        except OSError:
            raise HTTPException(404, '资源不存在') from None
        finally:
            os.close(fd)
        stored = f'uploads/{question_id}/bank-{index}.{image_suffix(data)}'
        target = media / stored
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as file: file.write(data)
        copied.append(target)
        db.query("INSERT INTO question_assets (id,question_id,kind,path,sha256,bbox,description,created_at,updated_at) VALUES (?,?,'question_figure',?,?,JSON_ARRAY(),'题库配图',UTC_TIMESTAMP(),UTC_TIMESTAMP())", [new_id(), question_id, stored, hashlib.sha256(data).hexdigest()])


def array(body, key, limit):
    value = body.get(key, [])
    if not isinstance(value, list) or len(value) > limit:
        raise HTTPException(422, f'{key} 格式或数量不正确')
    return value


async def create_manual_question(request):
    with Database.from_environment() as db:
        user = current_user(request, db)
        if user['role'] != 'student': raise HTTPException(403, '请使用学生账号记录错题')
        body = await read_json(request, 8 * 1024 * 1024)
        source = study_source(db, user['id'], body)
        text = text_field(body, 'question_text', 12000)
        subject = text_field(body, 'subject', 30, fallback='数学')
        kind = text_field(body, 'question_type', 50, fallback='综合题')
        if kind not in ['综合题', '单选题', '多选题']: raise HTTPException(422, '题目类型不正确')
        grade = body.get('grade')
        if grade is not None:
            if not isinstance(grade, str): raise HTTPException(422, '年级格式不正确')
            if len(grade) > 30: raise HTTPException(422, '年级过长')
        answer = body.get('student_answer', '')
        if not isinstance(answer, str) or len(answer) > 6000: raise HTTPException(422, '作答必须为不超过 6000 字的文字')
        answer = answer.strip()
        options, labels, validated = array(body, 'options', 8), set(), []
        if (kind == '综合题' and options) or (kind != '综合题' and len(options) < 2): raise HTTPException(422, '题目类型和选项数量不匹配')
        for option in options:
            if not isinstance(option, dict): raise HTTPException(422, '选项格式不正确')
            label = text_field(option, 'label', 1, trim=False)
            if label not in 'ABCDEFGH' or label in labels: raise HTTPException(422, '选项标记无效或重复')
            labels.add(label)
            validated.append({'label': label, 'text': text_field(option, 'text', 12000)})
        steps = []
        for step in array(body, 'student_steps', 30):
            if not isinstance(step, str): raise HTTPException(422, '步骤必须为文字')
            step = step.strip()
            if not step or len(step) > 12000: raise HTTPException(422, '步骤文字长度不正确')
            steps.append(step)
        question_id, work_id, copied = new_id(), new_id(), []
        try:
            with db.transaction():
                item_id = optional_text(body, 'study_item_id')
                if source:
                    owned_study(db, optional_text(body, 'study_session_id'), user['id'], lock=True)
                    previous = db.query("SELECT id FROM questions WHERE user_id=? AND status<>'archived' AND JSON_CONTAINS(tags,JSON_QUOTE(?)) LIMIT 1", [user['id'], 'study-item:' + item_id]).rows
                    if previous: return {'id': previous[0]['id'], 'status': 'confirmed'}
                db.query("INSERT INTO questions (id,user_id,subject,grade,title,question_text,student_answer,status,confirmed,favorite,tags,formulas,options,question_type,knowledge_points,created_at,updated_at) VALUES (?,?,?,?,?,?,?,'confirmed',1,0,JSON_ARRAY(),JSON_ARRAY(),?,?,JSON_ARRAY(),UTC_TIMESTAMP(),UTC_TIMESTAMP())", [question_id, user['id'], subject, grade, text[:80], text, answer or None, json.dumps(validated, ensure_ascii=False), kind])
                db.query("INSERT INTO student_works (id,question_id,user_id,answer,explanation,created_at,updated_at) VALUES (?,?,?,?,'',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))", [work_id, question_id, user['id'], answer])
                for index, step in enumerate(steps):
                    db.query("INSERT INTO student_steps (id,work_id,step_index,text,bbox,raw_text,normalized_text,formula,confidence,source,user_confirmed,created_at,updated_at) VALUES (?,?,?,?,JSON_ARRAY(),?,?,?,1,'user',1,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [new_id(), work_id, index, step, step, step, step if '=' in step else ''])
                if source:
                    db.query('UPDATE questions SET tags=?,knowledge_points=? WHERE id=?', [json.dumps(['study-item:' + item_id]), json.dumps(source.get('knowledge_points', [])), question_id])
                    copy_figures(db, question_id, source, copied)
        except BaseException:
            for path in copied: path.unlink(missing_ok=True)
            raise
        return {'id': question_id, 'status': 'confirmed'}
