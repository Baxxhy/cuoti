"""Only server-owned due notebook entries and eligible bank questions are candidates."""
from fastapi import HTTPException
from .retrieval import usable_candidate
from .rows import row_json
from .task_policy import object_value


def bank_row(row):
    return row_json('dataset_questions',{k:v for k,v in row.items() if k not in ['recent_n','recent_pass']})


def plan_candidates(db,owner,question,points):
    result=[]
    for row in db.query("SELECT q.* FROM questions q WHERE q.user_id=? AND q.subject=? AND q.id<>? AND EXISTS(SELECT 1 FROM review_plans r WHERE r.question_id=q.id AND r.user_id=? AND r.status='pending' AND r.due_at<=UTC_TIMESTAMP()) ORDER BY q.id LIMIT 30",[owner,question['subject'],question['id'],owner]).rows:
        source=row_json('questions',row)
        result.append({'id':source['id'],'subject':source['subject'],'source':'notebook','due':True,'estimated_minutes':3,'question_type':source['question_type']})
    rows=db.query("SELECT q.*,(SELECT COUNT(*) FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id WHERE s.user_id=? AND s.created_at>=UTC_TIMESTAMP()-INTERVAL 7 DAY AND JSON_UNQUOTE(JSON_EXTRACT(i.snapshot,'$.id'))=q.id) AS recent_n,EXISTS(SELECT 1 FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id WHERE s.user_id=? AND s.status='submitted' AND s.created_at>=UTC_TIMESTAMP()-INTERVAL 1 DAY AND JSON_UNQUOTE(JSON_EXTRACT(i.snapshot,'$.id'))=q.id AND JSON_EXTRACT(i.grading,'$.correct')=true AND JSON_EXTRACT(i.grading,'$.can_update_learning')=true) AS recent_pass FROM dataset_questions q WHERE q.subject=? AND q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND q.has_answer=1 ORDER BY q.id LIMIT 200",[owner,owner,question['subject']]).rows
    for row in rows:
        if len(result)>=200:break
        source=bank_row(row)
        if not usable_candidate(question,source,'practice'):continue
        labels=[p if isinstance(p,str) else p.get('name','') for p in source['knowledge_points']]
        related=any(label and label in points for label in labels)
        if not related and source['question_type']!=question['question_type']:continue
        item={k:source[k] for k in ['id','subject','question_type','grade_band','knowledge_points','options']}
        difficulty=source.get('difficulty','')
        item.update(source='dataset',error_relevance=1. if related else .2,estimated_minutes=3,difficulty=.25 if difficulty in ['easy','简单','容易'] else .8 if difficulty in ['hard','困难','较难'] else .5,recent_exposures=int(row['recent_n']),just_mastered=row['recent_pass']=='1')
        result.append(item)
    return result


def validate_recommendation(result,domain):
    plan=object_value(object_value(result,'student_view'),'recommendation');qid=plan.get('question_id','')
    if not qid:return
    candidates=domain.get('practice_candidates') or []
    if not any(c.get('id','')==qid and c.get('source','')==plan.get('question_source','') and c.get('just_mastered') is not True for c in candidates):raise HTTPException(503,'推荐题目不在本次可用范围内')
    for alternate in plan.get('alternatives') or []:
        if alternate==qid or not any(c.get('id','')==alternate and c.get('just_mastered') is not True for c in candidates):raise HTTPException(503,'备选题目不在本次可用范围内')
