import json
from fastapi import HTTPException
from .algorithm import compute
from .rows import row_json
from .study_bank import scoped_where,bank_filter


def selection(db,owner,subject,band,source,search,count,grade):
    fields=['id','subject','grade_band','question_type','knowledge_points','options'];candidates=[];allowed=set()
    for row in db.query('SELECT q.*'+scoped_where(grade)+' ORDER BY RAND() LIMIT 200',bank_filter(subject,band,source,search,grade)).rows:
        question=row_json('dataset_questions',row);candidates.append({k:question[k] for k in fields});allowed.add(question['id'])
    if len(candidates)<count:raise HTTPException(422,'当前范围可用题目不足，请减少题数或更换学科')
    observations=[]
    history=db.query("SELECT i.snapshot,i.grading FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id JOIN dataset_questions q ON q.id=JSON_UNQUOTE(JSON_EXTRACT(i.snapshot,'$.id')) WHERE s.user_id=? AND s.status='submitted' AND q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND (?='' OR q.subject=?) ORDER BY s.created_at DESC,i.position DESC LIMIT 400",[owner,subject,subject]).rows
    for row in reversed(history):
        grading=json.loads(row['grading']);correct=grading.get('correct')
        if grading.get('can_update_learning') is not True or not isinstance(correct,bool):continue
        question=json.loads(row['snapshot']);observations.append({**{k:question[k] for k in fields},'correct':correct,'confirmed':True,'independent':True})
    result=compute({'operation':'adaptive_practice','adaptive_practice':{'candidates':candidates,'observations':observations,'count':count}})
    ids=result.get('question_ids') or []
    if len(ids)!=count:raise HTTPException(503,'选题未完成，请重试')
    seen=set()
    for item_id in ids:
        if not isinstance(item_id,str) or item_id not in allowed or item_id in seen:raise HTTPException(503,'选题结果无效，请重试')
        seen.add(item_id)
    return result
