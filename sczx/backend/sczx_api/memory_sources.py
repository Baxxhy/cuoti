"""Source validation for educational memory; generated summaries are never authority."""
import hashlib
import json
from .diagnosis import diagnosis_fingerprint
from .learning_evidence import question_version,digest
from .practice_context import source_version
from .question_detail import query_array
from .rows import row_json
from .tutor_variants import data_snapshot


def task_snapshot(db,question_id,owner):
    value=data_snapshot(db,question_id,owner)
    def rows(table,sql):return query_array(db,table,sql,question_id)
    works=rows('student_works','SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1')
    value['work']=works[0] if works else None
    value['steps']=rows('student_steps','SELECT * FROM student_steps WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id')
    value['assets']=rows('question_assets',"SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id")
    diagnoses=rows('diagnoses','SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1')
    value['diagnosis']=diagnoses[0] if diagnoses else None
    return value


def task_fingerprint(db,question_id,owner):
    return digest(diagnosis_fingerprint(task_snapshot(db,question_id,owner)))


def dataset_version(db,dataset_id):
    rows=db.query('SELECT * FROM dataset_questions WHERE id=? AND usable_for_auto_grade=1',[dataset_id]).rows
    return digest(row_json('dataset_questions',rows[0])) if rows else ''


def question(db,question_id,subject):
    rows=db.query("SELECT * FROM questions WHERE id=? AND subject=? AND status<>'archived' AND confirmed=1",[question_id,subject]).rows
    return row_json('questions',rows[0]) if rows else {}


def sorted_digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def practice_proof_valid(db,source,preparation,candidate,trace):
    proof=trace.get('alignment_proof') or {}
    cards=db.query('SELECT * FROM knowledge_points WHERE id=? AND subject=?',[preparation.get('target_knowledge_id'),source['subject']]).rows
    context={'policy':1,'source':source_version(db,source),'candidate':sorted_digest(candidate),'target':sorted_digest(row_json('knowledge_points',cards[0])) if cards else ''}
    return proof.get('method') in ['symbolic_linear','qwen_grounded_concept'] and proof.get('context')==context


def update_valid(db,update,owner,subject):
    if update.get('user_id')!=owner:return False
    evidence=update.get('evidence') or {};source=evidence.get('memory_source') or {}
    if source.get('rule_version')!='learning-memory-v1':return False
    current=question(db,update.get('question_id',''),subject)
    if not current or source.get('question_version')!=question_version(db,current) or current['user_id']!=owner:return False
    strategy=evidence.get('strategy','')
    if strategy=='aemt_assistance_aware':
        rows=db.query("SELECT a.result,t.input_fingerprint FROM learning_task_actions a JOIN learning_tasks t ON t.id=a.task_id WHERE t.id=? AND t.user_id=? AND t.question_id=? AND a.request_id=? AND a.status='applied'",[evidence.get('learning_task_id',''),owner,current['id'],evidence.get('action_request_id','')]).rows
        if not rows or rows[0]['input_fingerprint']!=task_fingerprint(db,current['id'],owner):return False
        attempt=json.loads(rows[0]['result']).get('attempt') or {};event=evidence.get('aemt_event') or {};verdict=attempt.get('verdict','')
        return verdict in ['confirmed_correct','confirmed_incorrect'] and event.get('verdict')==verdict and (attempt.get('grading') or {}).get('can_update_learning') is True and event.get('solution_seen') is not True and event.get('scope') in ['original_question','contrast_question']
    if strategy=='verified_condition_contrast':
        rows=db.query("SELECT * FROM learning_tasks WHERE id=? AND user_id=? AND question_id=? AND status='completed' AND learning_applied=1",[evidence.get('learning_task_id',''),owner,current['id']]).rows
        return bool(rows) and rows[0]['input_fingerprint']==task_fingerprint(db,current['id'],owner)
    if strategy=='independent_dataset_practice':
        dataset=evidence.get('dataset_question_id','');version=dataset_version(db,dataset)
        if not version or version!=source.get('dataset_version'):return False
        rows=db.query('SELECT * FROM dataset_practice_attempts WHERE id=? AND user_id=? AND mistake_id=? AND dataset_question_id=?',[evidence.get('practice_attempt_id',''),owner,current['id'],dataset]).rows
        if not rows:return False
        attempt=row_json('dataset_practice_attempts',rows[0]);details=attempt.get('grading_details') or {}
        candidates=db.query('SELECT * FROM dataset_questions WHERE id=?',[dataset]).rows
        return bool(candidates) and details.get('can_update_learning') is True and practice_proof_valid(db,current,{'target_knowledge_id':attempt['knowledge_id']},row_json('dataset_questions',candidates[0]),{'alignment_proof':details.get('alignment_proof') or {}})
    if strategy in ['micro_activity','assisted_progression']:
        return bool(db.query("SELECT id FROM tutor_sessions WHERE id=? AND user_id=? AND question_id=? AND status='completed'",[evidence.get('tutor_session_id',''),owner,current['id']]).rows)
    return False
