import re
from fastapi import HTTPException
from .accounts import current_user
from .database import Database
from .manual_questions import answer_text
from .question_detail import query_array
from .questions import display_key
from .rows import row_json


def days_parameter(request,fallback,maximum):
    if 'days' not in request.query_params:return fallback
    raw=request.query_params.get('days','').strip()
    if not re.fullmatch(r'[+-]?[0-9]+',raw):raise HTTPException(422,'days 必须是整数')
    value=int(raw)
    if not -(2**63)<=value<2**63:raise HTTPException(422,'days 必须是整数')
    if not 1<=value<=maximum:raise HTTPException(422,'days 超出允许范围')
    return value


def canonical_mistake(value):
    return '移项符号' if '移项' in value and ('符号' in value or '变号' in value) else value


def method_label(value):
    return {'socratic':'逐步提问','micro_activity':'小步练习','assisted_progression':'分步辅助练习','independent_dataset_practice':'独立完成题库练习','incremental_hint':'分层提示','understanding_check_prompt':'理解检查','preserve_correct_part':'保留正确部分再提示','visual_counterexample':'图形演示和反例','prerequisite_example':'补充基础例子','temporary_rediagnosis':'重新分析题目','answer_with_explanation':'结合答案讲解','targeted_remediation':'针对错误讲解','guided':'逐步引导','':'尚未确定'}.get(value,value)


def learner_text(value):
    return (value or '根据最近的学习情况更新').replace('教回','讲解思路').replace('近迁移','相似题').replace('远迁移','综合题').replace('提示等级','使用提示')


def graph_topic(question):
    raw=question.get('question_type') or '错题学习'
    if question.get('knowledge_points'):raw=answer_text(question['knowledge_points'][0]).strip()
    return {'fill_blank':'填空题','choice':'单选题','multiple_choice':'多选题','calculation':'计算题','proof':'证明题','subjective':'主观题','other':'其他题型','':'错题学习'}.get(raw,raw)


def percent(value):
    scaled=value*100;lower=int(scaled);fraction=scaled-lower
    return lower+1 if fraction>.5 or fraction==.5 and lower%2!=0 else lower


def current_states(db,owner,mastery_limit='',mistake_limit='',translate=False):
    mastery=[];mistakes=[];seen_points=set();seen_mistakes=set()
    for row in db.query('SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at DESC,id DESC'+mastery_limit,[owner]).rows:
        key=(row['subject'],row['knowledge_point'])
        if key in seen_points:continue
        seen_points.add(key);mastery.append(row_json('mastery_states',row))
    for row in db.query('SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id'+mistake_limit,[owner]).rows:
        label=canonical_mistake(row['label']);key=(row['subject'],label)
        if key in seen_mistakes:continue
        seen_mistakes.add(key);item=row_json('misconception_states',row);item['label']=label
        if translate:
            for field in ['successful_strategy','failed_strategy']:item[field]=method_label(item[field]) if item.get(field) else ''
        mistakes.append(item)
    return mastery,mistakes


async def analytics(request):
    days=days_parameter(request,14,365)
    with Database.from_environment() as db:
        user=current_user(request,db)
        with db.transaction():
            mastery,mistakes=current_states(db,user['id'],translate=True);trend=[];evidence_count=0
            rows=db.query("SELECT DATE(created_at) AS day,AVG(new_value) AS average,COUNT(*) AS count FROM cognitive_updates WHERE user_id=? AND entity_type='mastery' AND created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) GROUP BY DATE(created_at) ORDER BY day",[user['id'],1-days]).rows
            for row in rows:
                count=int(row['count']);evidence_count+=count
                trend.append({'date':row['day'],'score':int(float(row['average'])*1000+.5)/10,'evidence_count':count})
            return {'mastery':mastery,'misconceptions':mistakes,'trend':trend,'summary':{'knowledge_count':len(mastery),'misconception_count':len(mistakes),'evidence_count':evidence_count}}


async def error_sources(request):
    days=days_parameter(request,90,365);subject=request.query_params.get('subject','')
    with Database.from_environment() as db:
        user=current_user(request,db)
        with db.transaction():
            rows=db.query("SELECT q.* FROM questions q JOIN diagnoses d ON d.id=(SELECT d2.id FROM diagnoses d2 WHERE d2.question_id=q.id ORDER BY d2.created_at DESC,d2.id DESC LIMIT 1) WHERE q.user_id=? AND q.status<>'archived' AND q.confirmed=1 AND (?='' OR q.subject=?) AND d.created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) ORDER BY q.updated_at DESC,q.id DESC LIMIT 201",[user['id'],subject,subject,-days]).rows
            sources=[];seen=set()
            for row in rows[:200]:
                key=display_key(row['question_text'],row['id'])
                if key in seen:continue
                seen.add(key);question=row_json('questions',row)
                diagnoses=query_array(db,'diagnoses','SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',row['id'])
                item={k:question[k] for k in ['id','subject','grade','question_text','knowledge_points','updated_at']};item['diagnosis']=diagnoses[0] if diagnoses else None
                plans=db.query("SELECT id FROM review_plans WHERE user_id=? AND question_id=? AND status='pending' AND due_at<TIMESTAMP(DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR))+INTERVAL 16 HOUR ORDER BY due_at,id LIMIT 1",[user['id'],row['id']]).rows
                item['due_review_id']=plans[0]['id'] if plans else None;sources.append(item)
            return {'sources':sources,'days':days,'limit':200,'truncated':len(rows)>200}
