import hashlib
import json
from fastapi import HTTPException
from .question_detail import query_array
from .rows import row_json


def equivalent(left,right):
    # Original jsonEquivalent compares scalar JSON text, so true != 1 != 1.0.
    return json.dumps(left,sort_keys=True,ensure_ascii=False)==json.dumps(right,sort_keys=True,ensure_ascii=False)


def source_fingerprint(db,question):
    source={k:question[k] for k in ['question_text','student_answer','subject','grade','title','formulas','options','question_type','knowledge_points']}
    source['student_work_revisions']=[r['id'] for r in db.query('SELECT id FROM student_works WHERE question_id=? ORDER BY id',[question['id']]).rows]
    return hashlib.sha256(json.dumps(source,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def source_version(db,question):
    value={'question':source_fingerprint(db,question)}
    for key,table in [('analysis','problem_analyses'),('diagnosis','diagnoses')]:
        rows=query_array(db,table,f'SELECT * FROM {table} WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',question['id'])
        value[key]=rows[0] if rows else None
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def served(db,owner,mistake,question_id,mode):
    rows=db.query('SELECT * FROM practice_recommendations WHERE user_id=? AND mistake_id=? AND dataset_question_id=? AND mode=? ORDER BY created_at DESC LIMIT 1',[owner,mistake['id'],question_id,mode]).rows
    if not rows:raise HTTPException(409,'请先获取推荐题再作答')
    record=row_json('practice_recommendations',rows[0])
    trace=record['retrieval_trace'] if isinstance(record['retrieval_trace'],dict) else {}
    if trace.get('source_question_fingerprint','')!=source_fingerprint(db,mistake):raise HTTPException(409,'题目或推荐已更新，请重新获取推荐题再提交')
    return record


def handwriting_context(db,owner,mistake_id,question_id,mode):
    mistakes=db.query('SELECT * FROM questions WHERE id=? AND user_id=?',[mistake_id,owner]).rows
    generated=db.query("SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND v.question_id=? AND s.user_id=? AND s.stage='standalone_practice'",[question_id,mistake_id,owner]).rows
    if mistakes and generated:
        variant=row_json('variant_questions',generated[0]);meta=variant['generation_metadata'] if isinstance(variant['generation_metadata'],dict) else {};mistake=row_json('questions',mistakes[0])
        if meta.get('mode','')!=mode or meta.get('source_version','')!=source_version(db,mistake):raise HTTPException(409,'原题已更新，请重新获取练习')
        if meta.get('options'):raise HTTPException(422,'选择题请直接选择选项')
        return {'subject':mistake['subject'],'text':variant['question_text']}
    questions=db.query('SELECT * FROM dataset_questions WHERE id=?',[question_id]).rows
    if not mistakes or not questions:raise HTTPException(404,'没有找到这道练习题')
    question=row_json('dataset_questions',questions[0]);served(db,owner,row_json('questions',mistakes[0]),question_id,mode)
    if question['options']:raise HTTPException(422,'选择题请直接选择选项')
    return {'subject':question['subject'],'text':question['question_text']}
