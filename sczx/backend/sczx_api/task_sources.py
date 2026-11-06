"""Immutable task sources, with transport numeric normalization only."""
import json
from .diagnosis import diagnosis_fingerprint
from .learning_evidence import digest
from .rows import row_json
from .task_policy import integer_value,object_value


class TaskSourceError(Exception):
    def __init__(self,reason):
        super().__init__('任务来源校验未通过');self.reason=reason


def source_equal(left,right):
    if type(left) in [int,float] and type(right) in [int,float]:
        return left==right if type(left) is type(right) is int else float(left)==float(right)
    if type(left) is not type(right):return False
    if isinstance(left,dict):return left.keys()==right.keys() and all(source_equal(v,right[k]) for k,v in left.items())
    if isinstance(left,list):return len(left)==len(right) and all(source_equal(a,b) for a,b in zip(left,right))
    return left==right


def fingerprint(snapshot):return digest(diagnosis_fingerprint(snapshot))


def source(db,task,current,origin='legacy_revalidated'):
    rows=db.query('SELECT * FROM learning_task_sources WHERE task_id=?',[task['id']]).rows
    if rows:
        try:record=row_json('learning_task_sources',rows[0])
        except Exception:raise TaskSourceError('source_parse') from None
        captured=object_value(record,'source')
        if record['input_fingerprint']!=task['input_fingerprint']:raise TaskSourceError('source_fingerprint')
        old=diagnosis_fingerprint(captured);fresh=diagnosis_fingerprint(current)
        for index,a in enumerate(old):
            if not source_equal(a,fresh[index]):raise TaskSourceError('source_field_'+str(index))
        return captured
    if task['input_fingerprint']!=fingerprint(current):raise TaskSourceError('source_legacy_stale')
    db.query("INSERT INTO learning_task_sources (task_id,schema_version,input_fingerprint,origin,source,created_at) VALUES (?,'1.0',?,?,?,UTC_TIMESTAMP(6))",[task['id'],task['input_fingerprint'],origin,json.dumps(current,ensure_ascii=False)])
    return current


def step_ids(snapshot,key):return [item['id'] for item in snapshot.get(key) or []]


def attempt_source(db,task,phase):
    result={'snapshot_id':task['id'],'student_step_id':None,'step_index':None,'student_step_text':''}
    rows=db.query('SELECT source FROM learning_task_sources WHERE task_id=?',[task['id']]).rows
    if not rows:return {}
    captured=json.loads(rows[0]['source']);result['student_work_id']=object_value(captured,'work').get('id','')
    if phase=='repair':
        steps=captured.get('steps') or []
        if steps:
            assessment=object_value(object_value(task,'checkpoint'),'evidence_diagnosis')
            first=integer_value(assessment,'first_error_step') if assessment.get('verified') is True and assessment.get('first_error_step') is not None else integer_value(object_value(captured,'diagnosis'),'first_error_step')
            index=0 if first<0 or first>99 else min(first,len(steps)-1)
            result.update(student_step_id=steps[index]['id'],step_index=index,student_step_text=steps[index]['text'])
    return result


def public_source(db,task_id):
    rows=db.query('SELECT * FROM learning_task_sources WHERE task_id=?',[task_id]).rows
    if not rows:return None
    record=row_json('learning_task_sources',rows[0]);question=object_value(object_value(record,'source'),'question')
    return {'snapshot_id':task_id,'origin':record['origin'],'captured_at':record['created_at'],**{k:question[k] for k in ['subject','grade','question_text','options']}}
