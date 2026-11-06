import json
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from .accounts import current_user
from .algorithm import compute
from .database import Database
from .rows import row_json

_SENSITIVE=['credential','password','secret','api_key','apikey','access_token','refresh_token','authorization','chain_of_thought','reasoning_content','raw_prompt','system_prompt']
_LABELS={'agent':{'mindtrace_tutor':'教学决策智能体','diagnosis':'错因诊断智能体','cognition':'认知建模智能体'},'branch':{'guided_question':'引导式提问','direct_explanation':'直接讲解','worked_example':'例题示范','visualization':'可视化讲解','teach_back':'学生复述','near_transfer':'近迁移检验','far_transfer':'远迁移检验','review_schedule':'安排复习'},'tool':{'knowledge_search':'知识检索','step_alignment':'步骤对齐','visualization':'生成教学图示','rediagnose':'动态再诊断','answer_reveal':'答案与步骤核对','answer_check':'数学结论验证','variant_generator':'生成迁移题','cognition_update':'更新认知状态','review_scheduler':'生成复习计划'}}


def sanitize(value):
    if isinstance(value,dict):return {k:sanitize(v) for k,v in value.items() if not any(part in k.lower() for part in _SENSITIVE)}
    if isinstance(value,list):return [sanitize(v) for v in value]
    return value


def timestamp(value):
    if isinstance(value,str):
        if value.endswith('+00:00'):value=value[:-6]
        if value.endswith('.000000'):value=value[:-7]
    return value


def fields(source,keys):return {k:timestamp(source.get(k)) if k in ['created_at','updated_at','due_at'] else source.get(k) for k in keys}


def label(kind,key):return _LABELS.get(kind,{}).get(key,key)


def metrics(db,owner):
    return {key:int(db.query(f'SELECT COUNT(*) AS count FROM {table} WHERE user_id=?'+extra,[owner]).rows[0]['count']) for key,table,extra in [('questions','questions'," AND status<>'archived'"),('sessions','tutor_sessions',''),('pending_reviews','review_plans'," AND status='pending'")]}


def student_data(db,student_id):
    rows=db.query("SELECT * FROM users WHERE id=? AND role='student'",[student_id]).rows
    if not rows:raise HTTPException(404,'未找到学生')
    user=row_json('users',rows[0]);profiles=db.query('SELECT * FROM student_profiles WHERE user_id=?',[student_id]).rows;profile=row_json('student_profiles',profiles[0]) if profiles else {}
    student=fields(user,['id','name','created_at']);student.update(grade=profile.get('grade') or '' if profiles else '未设置',learning_goal=profile.get('learning_goal') or '')
    result={'student':student,'metrics':metrics(db,student_id),'mastery':[],'misconceptions':[],'reviews':[]}
    for row in db.query('SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at DESC,id DESC LIMIT 20',[student_id]).rows:
        value=row_json('mastery_states',row);result['mastery'].append({**fields(value,['subject','knowledge_point','confidence','forgetting_risk','evidence_count']),'score':value['mastery_score']})
    for row in db.query('SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id DESC LIMIT 20',[student_id]).rows:result['misconceptions'].append(fields(row_json('misconception_states',row),['code','label','probability','status','evidence_count']))
    for row in db.query('SELECT * FROM review_plans WHERE user_id=? ORDER BY due_at,id LIMIT 20',[student_id]).rows:result['reviews'].append(fields(row_json('review_plans',row),['id','question_id','due_at','status','reason']))
    return result


def trace(db,session_id):
    result=[]
    for row in db.query('SELECT * FROM agent_runs WHERE session_id=? ORDER BY created_at,id',[session_id]).rows:
        run=row_json('agent_runs',row);value=run['result'] if isinstance(run['result'],dict) else {};branch=value.get('branch') or ''
        item={'id':run['id'],'time':timestamp(run['created_at']),'agent':label('agent',run['agent_name']),'status':run['status'],'decision':label('branch',branch) if branch else '完成一次决策','goal':value.get('next_goal') or value.get('goal') or ''}
        for key in ['observation','plan','verification']:item[key]=sanitize(value.get(key,{}))
        actions=[]
        for raw in db.query('SELECT * FROM agent_tool_calls WHERE agent_run_id=? ORDER BY created_at,id',[row['id']]).rows:
            call=row_json('agent_tool_calls',raw);actions.append({'id':call['id'],'tool':label('tool',call['tool_name']),'input':sanitize(call.get('input_json',{})),'output':sanitize(call.get('output_json',{}))})
        item['actions']=actions;result.append(item)
    return result


def session_data(db,session_id):
    rows=db.query('SELECT * FROM tutor_sessions WHERE id=?',[session_id]).rows
    if not rows:raise HTTPException(404,'未找到教学会话')
    session=row_json('tutor_sessions',rows[0]);owner=session['user_id'];question_id=session['question_id']
    result={'session':fields(session,['id','stage','status','turn_count','hint_level','mastery_score','created_at','updated_at'])}
    for key,table,sql,params,keys in [
        ('student','users','SELECT * FROM users WHERE id=?',[owner],['id','name']),
        ('question','questions','SELECT * FROM questions WHERE id=?',[question_id],['id','title','subject','question_text','student_answer','knowledge_points']),
        ('diagnosis','diagnoses','SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',[question_id],['first_error_step','first_error_text','error_type','root_misconception','confidence','recommended_strategy'])]:
        values=db.query(sql,params).rows;result[key]=fields(row_json(table,values[0]),keys) if values else None
    turns=[]
    for row in db.query('SELECT * FROM tutor_turns WHERE session_id=? ORDER BY created_at,id',[session_id]).rows:
        value=row_json('tutor_turns',row);turns.append({**fields(value,['id','role','content','stage']),'time':timestamp(value['created_at']),'decision':sanitize(value.get('metadata_json',{}))})
    updates=[]
    for row in db.query('SELECT * FROM cognitive_updates WHERE user_id=? AND question_id=? ORDER BY created_at,id',[owner,question_id]).rows:
        value=row_json('cognitive_updates',row);updates.append({**fields(value,['id','entity_type','entity_key','old_value','new_value','reason']),'time':timestamp(value['created_at'])})
    result.update(turns=turns,trace=trace(db,session_id),cognitive_updates=updates);return result


async def workbench(db):
    result={'generated_at':db.query("SELECT DATE_FORMAT(UTC_TIMESTAMP(6),'%Y-%m-%dT%H:%i:%s.%f+00:00') AS generated_at").rows[0]['generated_at']}
    result['metrics']={key:int(db.query(f'SELECT COUNT(*) AS count FROM {table} WHERE {condition}').rows[0]['count']) for key,table,condition in [('students','users',"role='student'"),('questions','questions',"status<>'archived'"),('diagnoses','diagnoses','1=1'),('sessions','tutor_sessions','1=1'),('active_sessions','tutor_sessions',"status='active'"),('agent_runs','agent_runs','1=1'),('cognitive_updates','cognitive_updates','1=1'),('pending_reviews','review_plans',"status='pending'")]}
    students=[]
    for row in db.query("SELECT * FROM users WHERE role='student' ORDER BY updated_at DESC,id DESC LIMIT 50").rows:
        user=row_json('users',row);item=fields(user,['id','name','updated_at']);profiles=db.query('SELECT grade FROM student_profiles WHERE user_id=?',[user['id']]).rows;counts=metrics(db,user['id'])
        item.update(grade=profiles[0]['grade'] or '' if profiles else '未设置',question_count=counts['questions'],session_count=counts['sessions']);students.append(item)
    sessions=[]
    for row in db.query('SELECT s.*,u.name AS student_name,q.title AS question_title,q.subject AS question_subject FROM tutor_sessions s JOIN users u ON u.id=s.user_id JOIN questions q ON q.id=s.question_id ORDER BY s.updated_at DESC,s.id DESC LIMIT 50').rows:
        item={k:row[k].replace(' ','T') if k=='updated_at' else row[k] for k in ['id','stage','status','updated_at']}
        item.update({key:row[source] or '' for key,source in [('student_id','user_id'),('student_name','student_name'),('question_id','question_id'),('question_title','question_title'),('subject','question_subject')]});item.update(turn_count=json.loads(row['turn_count']),mastery_score=json.loads(row['mastery_score']));sessions.append(item)
    state=await run_in_threadpool(compute,{'operation':'system_state','probe_provider':False});provider=state.get('provider') or {};voice=state.get('voice') or {}
    result.update(students=students,sessions=sessions,system={'database':'mysql','provider':{**fields(provider,['logical_model','total_entries','text_entries','vision_entries']),'status':provider['last_status']},'voice':fields(voice,['status','loaded','stt_model','tts_model'])})
    return result


async def admin_api(request,kind):
    with Database.from_environment() as db:
        user=current_user(request,db)
        if user['role']!='admin':raise HTTPException(403,'请使用管理员账号')
        with db.transaction():
            if kind=='student':return student_data(db,request.path_params['student_id'])
            if kind=='session':return session_data(db,request.path_params['session_id'])
            return await workbench(db)
