"""Project the original learning journey from persisted facts."""
from datetime import datetime
from fastapi import HTTPException
from .accounts import current_user
from .database import Database
from .memory_sources import task_snapshot
from .question_detail import query_array
from .rows import row_json
from .task_core import task_row,validate_version
from .task_policy import object_value
from .task_records import self_check_public
from .task_sources import fingerprint

_ACTIONS={
    'crop':('继续框选题目','/pages/crop/crop?id={q}','框选要学习的题目，再开始识别。'),
    'processing':('查看识别进度','/pages/ocr/ocr?id={q}&job={t}','识别仍在处理中，完成后核对题干和答案。'),
    'diagnose':('开始错因诊断','/pages/diagnosis/diagnosis?id={q}','根据确认后的题目与步骤寻找错误原因。'),
    'resume':('继续上次辅导','/pages/tutor/tutor?id={t}','从已保存的学习阶段继续。'),
    'review':('完成到期复习','/pages/review/review?plan={t}','先独立回忆，再根据判题结果安排下次复习。'),
    'learn':('查看诊断并学习','/pages/diagnosis/diagnosis?id={q}','理解首错原因，再练习验证。'),
    'practice':('练一道相似题','/pages/practice/practice?id={q}','用独立作答检验理解。')}


def action(kind,qid,target=''):
    if kind=='confirm':return {'label':'核对题目信息','url':'/pages/ocr/ocr?id='+qid+('&job='+target if target else ''),'reason':'确认题干和自己的作答，避免识别偏差影响诊断。'}
    label,path,reason=_ACTIONS[kind];return {'label':label,'url':path.format(q=qid,t=target),'reason':reason}


def time_key(value):
    utc=value.replace('+00:00','').replace('Z','').replace(' ','T')
    return utc+'.000000' if '.' not in utc else utc.ljust(26,'0')


def journey_time(value):
    key=time_key(value)
    return (key[:19] if key.endswith('.000000') else key)+'+00:00'


def trusted(item):
    details=object_value(item,'grading_details')
    return details.get('can_update_learning') is True and details.get('question_changed') is not True


def event(events,event_id,time,title,detail):
    events.append({'id':event_id,'time':journey_time(time),'title':title,'detail':detail})


def recent(events):return sorted(events,key=lambda e:time_key(e['time']),reverse=True)[:30]


def build(data,now):
    question=data['question'];qid=question['id'];diagnosis=object_value(data,'diagnosis');analysis=object_value(data,'analysis');job=object_value(data,'job');ocr=object_value(data,'ocr')
    latest='';active='';active_time='';understanding=False;independent=False;events=[]
    event(events,'question:'+qid,question['created_at'],'记录错题',question['subject']+' · '+question['question_type'])
    if ocr:event(events,'ocr:'+ocr['id'],ocr['created_at'],'图片识别','识别完成，请以人工核对后的内容为准。')
    if diagnosis:event(events,'diagnosis:'+diagnosis['id'],diagnosis['created_at'],'错因诊断',diagnosis.get('root_misconception') or '可在诊断页查看具体证据。')
    for session in data.get('sessions') or []:
        flags=object_value(session,'state');time=time_key(session['created_at'])
        if flags.get('question_changed') is not True:
            if not latest or time>latest:latest=time
            if session['status']=='active' and (not active_time or time>active_time):active=session['id'];active_time=time
            understanding=understanding or flags.get('understanding_passed') is True and flags.get('teach_back_passed') is True
            independent=independent or flags.get('near_transfer') is True and flags.get('far_transfer') is True and flags.get('assisted') is not True and flags.get('transfer_insufficient') is not True
        detail='本轮已结束，后续仍需独立练习和复习。' if session['status']=='completed' else '学习进度已保存，可继续。'
        if flags.get('question_changed') is True:detail='题目信息已修改，本次记录保留为历史，不计入当前进度。'
        elif flags.get('assisted') is True or flags.get('transfer_insufficient') is True:detail='本轮使用了辅助或迁移尚不稳定，仍需巩固。'
        event(events,'session:'+session['id'],session['updated_at'],'辅导记录',detail)
    attempts=verified=correct=waiting=0
    for item in data.get('practices') or []:
        attempts+=1;valid=trusted(item);details=object_value(item,'grading_details');changed=details.get('question_changed') is True
        if valid:
            verified+=1
            if item.get('correct') is True:correct+=1
        if details.get('can_update_learning') is not True and not changed:waiting+=1
        detail=('独立练习作答正确' if item.get('correct') is True else '本次作答仍需巩固') if valid else '本次结果待核对，未作为掌握证据'
        if changed:detail='题目信息已修改，此次练习作为历史记录保留。'
        event(events,'practice:'+item['id'],item['created_at'],'题库练习',detail)
    completed=0;review_correct=False
    for item in data.get('reviews') or []:
        valid=trusted(item) and item['grade']!='pending'
        if valid:completed+=1;review_correct=review_correct or item.get('correct') is True
        detail=('复习作答正确' if item.get('correct') is True else '复习仍需巩固') if valid else '等待完成判定和难度反馈'
        if object_value(item,'grading_details').get('question_changed') is True:detail='题目信息已修改，此次复习作为历史记录保留。'
        event(events,'review:'+item['id'],item['created_at'],'复习作答',detail)
    seconds=int(datetime.fromisoformat(now.replace('Z','+00:00')).timestamp());end_day=((seconds+8*3600)//86400+1)*86400-8*3600
    due=0;next_time='';next_id=''
    for plan in data.get('plans') or []:
        if plan['status']!='pending':continue
        time=plan['due_at'];key=time_key(time)
        if not next_time or key<time_key(next_time):next_time=time;next_id=plan['id']
        if int(datetime.fromisoformat(time.replace('Z','+00:00')).timestamp())<end_day:due+=1
    kind='practice';target=''
    if question['status']=='awaiting_crop':kind='crop'
    elif job.get('status') in ['pending','running']:kind='processing';target=job['id']
    elif question.get('confirmed') is not True:kind='confirm';target=job['id'] if job.get('status')=='failed' else ''
    elif not diagnosis:kind='diagnose'
    elif active:kind='resume';target=active
    elif due>0:kind='review';target=next_id
    elif not latest:kind='learn'
    def stage(key,label,done,detail):return {'key':key,'label':label,'completed':done,'detail':detail}
    stages=[stage('confirmed','核对题目',question.get('confirmed') is True,'题干与作答已确认' if question.get('confirmed') is True else '等待核对识别内容'),stage('diagnosed','找到错因',bool(diagnosis),'已有诊断证据，可查看和纠正' if diagnosis else '等待完成诊断'),stage('understanding','理解并讲清',understanding,'理解检查与教回均通过' if understanding else '以实际检查与教回结果为准'),stage('transfer','独立迁移',independent,'相似题和综合应用均独立通过' if independent else '尚无完整的独立迁移证据'),stage('review','间隔复习',review_correct,f'完成 {completed} 次有效复习' if completed>0 else '等待复习验证长期保持')]
    return {**{k:question[k] for k in ['title','question_text','subject']},'question_id':qid,'generated_at':journey_time(now),'stages':stages,'next_action':action(kind,qid,target),'summary':'曾有独立迁移证据，继续用复习检验保持。' if independent else '按记录逐步巩固，完成辅导不等于已经掌握。','verification':{'label':'已完成规则校验' if analysis.get('verified') is True else '尚未通过规则校验','verified':analysis.get('verified') is True,'diagnosis_confirmed':diagnosis.get('user_confirmed') is True},'practice':{'attempts':attempts,'verified_attempts':verified,'correct':correct,'pending':waiting},'review':{'completed':completed,'due':due,'next_due_at':journey_time(next_time) if next_time else None},'events':recent(events),'history_limit':50}


def add_tasks(db,result,user_id,qid):
    rows=db.query('SELECT * FROM learning_tasks WHERE user_id=? AND question_id=? ORDER BY updated_at DESC,id DESC LIMIT 50',[user_id,qid]).rows
    if not rows:return result
    snapshot=task_snapshot(db,qid,user_id,lock=True);items=[];events=list(result.get('events') or []);active='';repair=original=near=finished=False
    for row in rows:
        task=row_json('learning_tasks',row);current=validate_version(db,task,snapshot);status=task['status'];flags=object_value(task,'checkpoint');assistance=object_value(flags,'assistance')
        if current:
            repair=repair or flags.get('repair_passed') is True;original=original or flags.get('independent_passed') is True and assistance.get('independent') is not True
            near=near or task['learning_applied'] is True;finished=finished or status=='completed'
            if not active and status in ['queued','running','waiting_student','needs_review','failed']:active=task['id']
        items.append({**{k:task[k] for k in ['id','status','updated_at','learning_applied']},'source_current':current})
        detail='原题已更新，本次过程保留为历史。' if not current else ('本次对照已独立完成，仍需间隔复习检验保持。' if task['learning_applied'] is True else '本轮学习已结束，未新增独立迁移证据。') if status=='completed' else '本次已结束，回答与订正记录保留。' if status=='cancelled' else '已保存当前步骤，可回任务继续查看。'
        event(events,'task:'+task['id'],task['updated_at'],'订正学习',detail)
    result['learning_tasks']={'items':items,'repair_verified':repair,'original_independent':original,'near_transfer':near}
    current_url=object_value(result,'next_action').get('url','');question=snapshot['question']
    if active and question['confirmed'] is True and question['status']!='awaiting_crop' and not current_url.startswith('/pages/ocr/'):
        result['next_action']={'label':'继续订正学习','url':'/pages/task/task?id='+active,'reason':'从已保存的当前步骤继续，不必重新开始。'}
    elif finished and current_url.startswith('/pages/diagnosis/'):result['next_action']=action('practice',qid)
    if near:result['summary']='已有本次单条件对照的独立证据，继续用间隔复习检验保持。'
    notes=[]
    for row in db.query('SELECT n.* FROM learning_self_checks n WHERE n.user_id=? AND n.question_id=? AND n.deleted=0 ORDER BY n.updated_at DESC,n.id DESC LIMIT 50',[user_id,qid]).rows:
        note=row_json('learning_self_checks',row);task=task_row(db,note['task_id'],user_id)
        current=note['input_fingerprint']==fingerprint(snapshot) and task['status']!='stale' and question['status']!='archived'
        view=self_check_public(note,current,False)['note'];view['source_current']=current;notes.append(view)
        event(events,'selfcheck:'+note['id'],note['updated_at'],'保存自检要点','学生确认的提醒，不作为掌握证明。' if current else '原题已更新，这条要点保留为历史提醒。')
    result.update(self_checks=notes,events=recent(events));return result


def journey(request,qid):
    with Database.from_environment() as db:
        user=current_user(request,db)
        with db.transaction():
            rows=db.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived'",[qid,user['id']]).rows
            if not rows:raise HTTPException(404,'题目不存在')
            data={'question':row_json('questions',rows[0])}
            for key,table in [('analysis','problem_analyses'),('diagnosis','diagnoses'),('job','processing_jobs'),('ocr','ocr_runs')]:
                values=query_array(db,table,f'SELECT * FROM {table} WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',qid);data[key]=values[0] if values else None
            for key,table,column in [('sessions','tutor_sessions','question_id'),('practices','dataset_practice_attempts','mistake_id'),('plans','review_plans','question_id')]:
                suffix=" AND status='pending' ORDER BY due_at,id" if key=='plans' else ' ORDER BY created_at DESC,id DESC'
                data[key]=[row_json(table,r) for r in db.query(f'SELECT * FROM {table} WHERE {column}=? AND user_id=?'+suffix+' LIMIT 50',[qid,user['id']]).rows]
            data['reviews']=[row_json('review_records',r) for r in db.query('SELECT r.* FROM review_records r JOIN review_plans p ON p.id=r.plan_id WHERE p.question_id=? AND p.user_id=? ORDER BY r.created_at DESC,r.id DESC LIMIT 50',[qid,user['id']]).rows]
            now=db.query('SELECT UTC_TIMESTAMP(6) AS now').rows[0]['now'].replace(' ','T')+'+00:00'
            return add_tasks(db,build(data,now),user['id'],qid)
