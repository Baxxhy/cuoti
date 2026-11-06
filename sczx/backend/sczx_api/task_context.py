import json
from .learning_evidence import knowledge_point
from .learning_memory import apply_task_memory,learning_memory
from .rows import row_json
from .task_planning import plan_candidates
from .task_policy import object_value,integer_value
from .task_sources import step_ids
from .tutor_core import knowledge


def context(db,snapshot,owner):
    question=snapshot['question'];analysis=object_value(snapshot,'analysis');diagnosis=object_value(snapshot,'diagnosis')
    result={'question_id':question['id'],**{k:question.get(k,'') for k in ['subject','grade','question_type','question_text','options']}}
    if result['grade'] is None:result['grade']=''
    result.update(student_work_id=object_value(snapshot,'work').get('id',''),student_step_ids=step_ids(snapshot,'steps'),reference_step_ids=step_ids(snapshot,'references'),expected=analysis.get('final_answer') or '',reference_steps=[r['text'] for r in snapshot['references']],student_steps=[r['text'] for r in snapshot['steps']])
    first=integer_value(diagnosis,'first_error_step') if diagnosis.get('first_error_step') is not None else 0
    result.update(first_error_step=first if 0<=first<=99 else 0,diagnosed_correct=diagnosis.get('first_error_step') is None and diagnosis.get('error_type') in ['exact','equivalent'],diagnosis_confirmed=diagnosis.get('user_confirmed') is True,diagnosis_hypothesis=diagnosis.get('root_misconception') or '')
    points=knowledge(snapshot);cards=[];seen=set()
    for point in points:
        if len(cards)>=3:break
        for row in db.query('SELECT * FROM knowledge_points WHERE subject=? AND (name=? OR code=?) ORDER BY code LIMIT 3',[question['subject'],point,point]).rows:
            card=row_json('knowledge_points',row)
            if card['code'] not in seen and len(cards)<3:cards.append(card);seen.add(card['code'])
    result.update(knowledge_points=points,cards=cards);prerequisites=[]
    for label in diagnosis.get('missing_prerequisites') or []:
        if len(prerequisites)>=6:break
        rows=db.query('SELECT k.id FROM knowledge_points k JOIN mastery_states m ON m.subject=k.subject AND (m.knowledge_point=k.name OR m.knowledge_point=k.code) WHERE m.user_id=? AND k.subject=? AND (k.name=? OR k.code=?) AND m.evidence_count>0 AND m.mastery_score<0.3 ORDER BY k.id LIMIT 1',[owner,question['subject'],label,label]).rows
        prerequisites.extend(row['id'] for row in rows)
    result.update(prerequisite_card_ids=prerequisites,practice_candidates=plan_candidates(db,owner,question,points))
    rows=db.query("SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast.question')) AS prompt FROM learning_tasks t JOIN questions q ON q.id=t.question_id WHERE t.user_id=? AND q.subject=? AND (JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast_passed'))='true' OR JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.assistance.contrast'))='true') AND JSON_EXTRACT(t.checkpoint,'$.contrast.question') IS NOT NULL ORDER BY prompt LIMIT 50",[owner,question['subject']]).rows
    result['seen_contrasts']=[r['prompt'] for r in rows];point=knowledge_point(db,question)
    rows=db.query('SELECT mastery_score,evidence_count,last_evidence_at FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? ORDER BY updated_at DESC,id DESC LIMIT 1',[owner,question['subject'],point]).rows
    if rows:
        row=rows[0];count=int(row['evidence_count']);state={'mastery':float(row['mastery_score']) if count>0 else .35,'evidence_count':count,'last_effective_at':row['last_evidence_at'] or ''}
        counts=db.query("SELECT COUNT(CASE WHEN JSON_EXTRACT(u.evidence,'$.aemt_event.hint_used')=false THEN 1 END) AS independent_count,COUNT(CASE WHEN JSON_EXTRACT(u.evidence,'$.aemt_event.hint_used')=false AND JSON_UNQUOTE(JSON_EXTRACT(u.evidence,'$.aemt_event.verdict'))='confirmed_correct' THEN 1 END) AS independent_correct,COUNT(CASE WHEN JSON_EXTRACT(u.evidence,'$.aemt_event.hint_used')=true THEN 1 END) AS hinted_count FROM cognitive_updates u JOIN questions q ON q.id=u.question_id WHERE u.user_id=? AND q.subject=? AND u.entity_type='mastery' AND u.entity_key=? AND JSON_EXTRACT(u.evidence,'$.aemt_event.solution_seen')=false",[owner,question['subject'],point]).rows[0]
        state.update({k:int(counts[k]) for k in ['independent_count','independent_correct','hinted_count']});result['mastery_state']=state
    profiles=db.query('SELECT preferences FROM student_profiles WHERE user_id=?',[owner]).rows
    if profiles:
        preferences=json.loads(profiles[0]['preferences']);minutes=integer_value(preferences,'daily_minutes')
        if 0<minutes<=120:
            goal=3 if minutes<=5 else 5 if minutes<=10 else 10
            completed=db.query("SELECT (SELECT COUNT(DISTINCT question_id) FROM learning_tasks WHERE user_id=? AND status='completed' AND updated_at>=UTC_DATE()) AS tasks,(SELECT COUNT(*) FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id WHERE s.user_id=? AND s.status='submitted' AND s.submitted_at>=UTC_DATE() AND JSON_EXTRACT(i.grading,'$.can_update_learning')=true) AS practice",[owner,owner]).rows[0]
            tasks=int(completed['tasks']);practice=int(completed['practice'])
            result.update(available_minutes=max(0,minutes-tasks*3-practice),goal_remaining=max(0,goal-tasks-practice))
    apply_task_memory(result,learning_memory(db,owner,question));return result
