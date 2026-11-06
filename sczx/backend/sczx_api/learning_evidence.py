"""Persist learning evidence and its source stamp in the business database."""
import hashlib
import json
from .algorithm import compute
from .manual_questions import answer_text
from .question_detail import query_array
from .rows import row_json
from .security import new_id


def first_label(values):
    if not isinstance(values,list):return ''
    for value in values:
        raw=next((value[k] for k in ['name','label','code'] if isinstance(value.get(k),str) and value[k]),'') if isinstance(value,dict) else answer_text(value)
        if raw.strip():return raw.strip()
    return ''


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def question_version(db,question):
    question_id=question['id'];value=[question[k] for k in ['id','user_id','subject','grade','question_type','question_text','student_answer','options','knowledge_points']]
    def query(table,sql):return query_array(db,table,sql,question_id)
    works=query('student_works','SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1')
    value.append(works[0] if works else None)
    value.append(query('student_steps','SELECT * FROM student_steps WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id'))
    value.append(query('question_assets',"SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id"))
    analyses=query('problem_analyses','SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1')
    value.append(analyses[0] if analyses else None)
    value.append(query('reference_steps','SELECT r.* FROM reference_steps r JOIN problem_analyses a ON a.id=r.analysis_id WHERE a.question_id=? ORDER BY r.step_index,r.id'))
    value.append([])
    return digest(value)


def knowledge_point(db,question,preferred='',include_analysis=True):
    point=preferred.strip() or first_label(question['knowledge_points'])
    if not point and include_analysis:
        analyses=db.query('SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1',[question['id']]).rows
        if analyses:point=first_label(row_json('problem_analyses',analyses[0])['knowledge_points'])
    return point or question['title'].strip() or question['subject'].strip()+'·'+question['question_type']


def apply_evidence(db,owner,question,evidence,preferred='',include_analysis=True,timeout=200):
    point=knowledge_point(db,question,preferred,include_analysis)
    subject=question['subject'].strip();question_id=question['id']
    diagnoses=db.query('SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',[question_id]).rows
    diagnosis=row_json('diagnoses',diagnoses[0]) if diagnoses else {}
    code=diagnosis.get('error_type','').strip();code='unclassified' if not code or code in ['exact','equivalent','branch_solution'] else code
    label=diagnosis.get('root_misconception','').strip() or code
    old_mastery=db.query('SELECT * FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? ORDER BY updated_at DESC,id DESC LIMIT 1',[owner,subject,point]).rows
    old_mistake=db.query('SELECT * FROM misconception_states WHERE user_id=? AND subject=? AND code=? ORDER BY updated_at DESC,id DESC LIMIT 1',[owner,subject,code]).rows
    before_mastery=row_json('mastery_states',old_mastery[0]) if old_mastery else None
    before_mistake=row_json('misconception_states',old_mistake[0]) if old_mistake else None
    defaults={'mastery_score':0.,'evidence_count':0,'confidence':0.,'near_transfer_rate':0.,'far_transfer_rate':0.,'forgetting_risk':.5}
    mastery={k:before_mastery[k] if before_mastery else v for k,v in defaults.items()};mastery['update_reason']=''
    defaults={'probability':.5,'evidence_count':1,'related_question_count':1,'label':label,'status':'active','successful_strategy':'','failed_strategy':''}
    mistake={k:before_mistake[k] if before_mistake else v for k,v in defaults.items()}
    computed=compute({'operation':'cognition_update','mastery_values':mastery,'misconception_values':mistake,'learning_evidence':evidence,'misconception_label':label},timeout=timeout)
    next_mastery,next_mistake=computed['mastery'],computed['misconception']
    mastery_id=old_mastery[0]['id'] if old_mastery else new_id();mistake_id=old_mistake[0]['id'] if old_mistake else new_id()
    if not old_mastery:db.query("INSERT INTO mastery_states (id,user_id,subject,knowledge_point,mastery_score,confidence,evidence_count,near_transfer_rate,far_transfer_rate,forgetting_risk,update_reason,created_at,updated_at) VALUES (?,?,?,?,0,0,0,0,0,0.5,'',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[mastery_id,owner,subject,point])
    if not old_mistake:db.query("INSERT INTO misconception_states (id,user_id,subject,code,label,probability,evidence_count,status,related_question_count,successful_strategy,failed_strategy,first_seen_at,created_at,updated_at) VALUES (?,?,?,?,?,0.5,1,'active',1,'','',UTC_TIMESTAMP(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[mistake_id,owner,subject,code,label])
    keys=['mastery_score','confidence','evidence_count','near_transfer_rate','far_transfer_rate','forgetting_risk','update_reason']
    db.query('UPDATE mastery_states SET mastery_score=?,confidence=?,evidence_count=?,near_transfer_rate=?,far_transfer_rate=?,forgetting_risk=?,update_reason=?,last_evidence_at=UTC_TIMESTAMP(),updated_at=UTC_TIMESTAMP() WHERE id=?',[next_mastery[k] for k in keys]+[mastery_id])
    keys=['probability','evidence_count','related_question_count','label','status','successful_strategy','failed_strategy']
    db.query('UPDATE misconception_states SET probability=?,evidence_count=?,related_question_count=?,label=?,status=?,successful_strategy=?,failed_strategy=?,last_seen_at=UTC_TIMESTAMP(),updated_at=UTC_TIMESTAMP() WHERE id=?',[next_mistake[k] for k in keys]+[mistake_id])
    dataset=evidence.get('dataset_question_id','');version=''
    if dataset:
        rows=db.query('SELECT * FROM dataset_questions WHERE id=? AND usable_for_auto_grade=1',[dataset]).rows
        if rows:version=digest(row_json('dataset_questions',rows[0]))
    evidence['memory_source']={'rule_version':'learning-memory-v1','question_version':question_version(db,question),'mastery_id':mastery_id,'misconception_id':mistake_id,'dataset_version':version}
    for kind,key,old,new in [('mastery',point,mastery['mastery_score'],next_mastery['mastery_score']),('misconception',code,mistake['probability'],next_mistake['probability'])]:
        db.query('INSERT INTO cognitive_updates (id,user_id,question_id,entity_type,entity_key,old_value,new_value,evidence,reason,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[new_id(),owner,question_id,kind,key,old,new,json.dumps(evidence,ensure_ascii=False),next_mastery['update_reason']])
    return {'mastery_before':before_mastery,'misconception_before':before_mistake,'mastery_after':row_json('mastery_states',db.query('SELECT * FROM mastery_states WHERE id=?',[mastery_id]).rows[0]),'misconception_after':row_json('misconception_states',db.query('SELECT * FROM misconception_states WHERE id=?',[mistake_id]).rows[0])}
