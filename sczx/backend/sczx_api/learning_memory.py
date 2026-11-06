from datetime import datetime
from .learning_evidence import digest,question_version
from .memory_sources import update_valid,question as memory_question,task_fingerprint
from .recognition import short_title
from .rows import row_json


def entry(kind,row,question_id,classification,summary,days,source_version,sources,independence='not_applicable',outcome='unknown'):
    observed=int(datetime.fromisoformat(row['updated_at']).timestamp())
    return {'ref':kind+':'+row['id'],'kind':kind,'classification':classification,'question_id':question_id,'source_refs':sources,'observed_at':observed,'expires_at':observed+days*86400,'summary':short_title(summary,400),'version':digest([row,source_version]),'independence':independence,'outcome':outcome}


def estimate_current(db,row,kind,owner,subject):
    key='knowledge_point' if kind=='mastery' else 'code';source_key='mastery_id' if kind=='mastery' else 'misconception_id'
    rows=db.query(f"SELECT u.* FROM cognitive_updates u WHERE u.user_id=? AND u.entity_type=? AND u.entity_key=? AND (JSON_UNQUOTE(JSON_EXTRACT(u.evidence,'$.memory_source.{source_key}'))=? OR JSON_EXTRACT(u.evidence,'$.memory_source') IS NULL) ORDER BY u.created_at DESC,u.id DESC LIMIT 1",[owner,kind,row[key],row['id']]).rows
    if not rows:return True
    update=row_json('cognitive_updates',rows[0])
    if not (update.get('evidence') or {}).get('memory_source'):return True
    return update_valid(db,update,owner,subject)


def learning_memory(db,owner,question):
    subject=question['subject'];question_id=question['id'];entries=[];legacy={k:[] for k in ['mastery','misconceptions','updates','reviews']}
    rows=db.query('SELECT * FROM mastery_states WHERE user_id=? AND subject=? AND updated_at<=UTC_TIMESTAMP(6) AND updated_at>UTC_TIMESTAMP(6)-INTERVAL 30 DAY ORDER BY updated_at DESC,id DESC LIMIT 12',[owner,subject]).rows
    for row in rows:
        if len(legacy['mastery'])>=3:break
        record=row_json('mastery_states',row)
        if not estimate_current(db,record,'mastery',owner,subject):continue
        legacy['mastery'].append(record)
        entries.append(entry('mastery',record,'','estimate',record['knowledge_point']+'：历史掌握估计 '+str(record['mastery_score'])+'，不是掌握证明',30,'',['mastery:'+record['id']]))
    rows=db.query("SELECT * FROM misconception_states WHERE user_id=? AND subject=? AND status='active' AND updated_at<=UTC_TIMESTAMP(6) AND updated_at>UTC_TIMESTAMP(6)-INTERVAL 30 DAY ORDER BY updated_at DESC,id DESC LIMIT 12",[owner,subject]).rows
    for row in rows:
        if len(legacy['misconceptions'])>=3:break
        record=row_json('misconception_states',row)
        if not estimate_current(db,record,'misconception',owner,subject):continue
        legacy['misconceptions'].append(record)
        entries.append(entry('misconception',record,'','candidate',record['label']+'：待核对误区候选，不能对学生定性',30,'',['misconception:'+record['id']]))
    rows=db.query("SELECT u.* FROM cognitive_updates u JOIN questions q ON q.id=u.question_id WHERE u.user_id=? AND q.subject=? AND u.entity_type='mastery' AND u.updated_at<=UTC_TIMESTAMP(6) AND u.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY u.updated_at DESC,u.id DESC LIMIT 30",[owner,subject]).rows
    for row in rows:
        if len(legacy['updates'])>=4:break
        record=row_json('cognitive_updates',row)
        if not update_valid(db,record,owner,subject):continue
        evidence=record.get('evidence') or {};strategy=evidence.get('strategy','');aemt=evidence.get('aemt_event') or {};verdict=aemt.get('verdict','')
        correct=evidence.get('near_transfer') is True or evidence.get('far_transfer') is True or strategy=='aemt_assistance_aware' and verdict=='confirmed_correct'
        outcome='correct' if correct else 'incorrect' if strategy=='independent_dataset_practice' or strategy=='aemt_assistance_aware' and verdict=='confirmed_incorrect' else 'unknown'
        independence='assisted' if strategy=='assisted_progression' or evidence.get('hint_level',0)>0 else 'independent'
        sources=['cognitive:'+record['id'],'question:'+record['question_id']]
        for key,prefix in [('learning_task_id','task:'),('practice_attempt_id','practice:'),('tutor_session_id','tutor:')]:
            if evidence.get(key):sources.append(prefix+evidence[key])
        scope='本次原题作答' if strategy=='aemt_assistance_aware' and aemt.get('scope')=='original_question' else '本次迁移作答'
        conclusion=(scope+'正确' if strategy=='aemt_assistance_aware' else '本次迁移判定正确') if outcome=='correct' else (scope+'有误' if strategy=='aemt_assistance_aware' else '本次迁移作答有误') if outcome=='incorrect' else '结果尚不充分'
        summary=record['entity_key']+'：历史学习事件，'+conclusion+'；不代表整个知识点掌握'
        entries.append(entry('cognitive',record,record['question_id'],'verified_event',summary,90,(evidence.get('memory_source') or {}).get('question_version',''),sources,independence,outcome));legacy['updates'].append(record)
    reviewed=0
    rows=db.query("SELECT r.* FROM review_records r JOIN review_plans p ON p.id=r.plan_id JOIN questions q ON q.id=p.question_id WHERE p.user_id=? AND q.user_id=? AND q.subject=? AND q.status<>'archived' AND q.confirmed=1 AND r.grade<>'pending' AND r.updated_at<=UTC_TIMESTAMP(6) AND r.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY r.updated_at DESC,r.id DESC LIMIT 20",[owner,owner,subject]).rows
    for row in rows:
        if reviewed>=3:break
        record=row_json('review_records',row);details=record.get('grading_details') or {}
        if details.get('can_update_learning') is not True or details.get('verdict') not in ['confirmed_correct','confirmed_incorrect']:continue
        plans=db.query('SELECT question_id FROM review_plans WHERE id=? AND user_id=?',[record['plan_id'],owner]).rows
        if not plans:continue
        item_id=plans[0]['question_id'];source=memory_question(db,item_id,subject);version=question_version(db,source)
        if details.get('memory_question_version','')!=version:continue
        outcome='correct' if record['correct'] is True else 'incorrect';summary='本次复习系统判定'+('正确；难度自评不等于掌握' if outcome=='correct' else '有误；不以学生的难度自评改为正确')
        entries.append(entry('review_record',record,item_id,'verified_event',summary,90,version,['review_record:'+record['id'],'review:'+record['plan_id']],'unknown',outcome));reviewed+=1
    notes=0
    rows=db.query("SELECT n.* FROM learning_self_checks n JOIN learning_tasks t ON t.id=n.task_id JOIN questions q ON q.id=n.question_id WHERE n.user_id=? AND q.user_id=? AND q.subject=? AND q.status<>'archived' AND q.confirmed=1 AND n.deleted=0 AND t.status='completed' AND n.updated_at<=UTC_TIMESTAMP(6) AND n.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY n.updated_at DESC,n.id DESC LIMIT 20",[owner,owner,subject]).rows
    for row in rows:
        if notes>=3:break
        record=row_json('learning_self_checks',row);item_id=record['question_id'];version=task_fingerprint(db,item_id,owner)
        if version!=record['input_fingerprint']:continue
        entries.append(entry('self_check',record,item_id,'student_self_report','学生确认的自述（未证明掌握）：'+record['text'],90,version,['self_check:'+record['id'],'task:'+record['task_id']]));notes+=1
    rows=db.query("SELECT p.* FROM review_plans p JOIN questions q ON q.id=p.question_id WHERE p.user_id=? AND q.user_id=? AND q.id=? AND q.subject=? AND q.status<>'archived' AND q.confirmed=1 AND p.status='pending' AND p.updated_at<=UTC_TIMESTAMP(6) AND p.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY p.due_at,p.id LIMIT 2",[owner,owner,question_id,subject]).rows
    for row in rows:
        record=row_json('review_plans',row);legacy['reviews'].append(record);version=question_version(db,question)
        entries.append(entry('review',record,question_id,'reminder','当前题有待复习安排，到期时间：'+record['due_at']+'；安排不证明学会',90,version,['review:'+record['id'],'question:'+question_id]))
    return {'snapshot':{'rule_version':'learning-memory-v1','entries':entries},'legacy_rows':legacy}


def audit_manifest(snapshot):
    return [{k:e[k] for k in ['ref','version','classification','observed_at','expires_at','question_id','source_refs']} for e in snapshot.get('entries',[])]


def apply_task_memory(context,memory):
    snapshot=memory.get('snapshot') or {};refs=[];versions={};summary=''
    for value in snapshot.get('entries',[]):
        refs.append(value['ref']);versions[value['ref']]=value['version'];text=value['summary']+'；'
        if len(summary)+len(text)<=1800:summary+=text
    context.update(memory_snapshot=snapshot,memory_refs=refs,memory_versions=versions,memory_summary=short_title(summary,1800))
