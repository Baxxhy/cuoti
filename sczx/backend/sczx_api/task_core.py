import copy
import json
from fastapi import HTTPException
from .accounts import current_user,secret
from .memory_sources import task_snapshot
from .rows import row_json
from .security import media_url
from .task_policy import at_limit,limit_view,stopped_view,object_value,integer_value
from .task_sources import fingerprint


def owner(request,db):
    user=current_user(request,db)
    if user['role']!='student':raise HTTPException(403,'请使用学生账号学习')
    return user['id']


def task_row(db,task_id,user_id,lock=False):
    rows=db.query('SELECT * FROM learning_tasks WHERE id=? AND user_id=?'+(' FOR UPDATE' if lock else ''),[task_id,user_id]).rows
    if not rows:raise HTTPException(404,'学习任务不存在或无权访问')
    return row_json('learning_tasks',rows[0])


def public(task):
    result={k:copy.deepcopy(task[k]) for k in ['id','question_id','session_id','status','version','step_id','input_fingerprint','student_view','created_at','updated_at','learning_applied']}
    view=copy.deepcopy(object_value(task,'student_view'))
    for block in view.get('prompt_blocks') or []:
        images=[media_url(path if path.startswith('/') else '/'+path,secret()) for path in block.get('images') or []]
        if images:block['images']=images
    draft=object_value(view,'handwriting')
    if draft.get('image_url'):draft['image_url']=media_url(draft['image_url'],secret());view['handwriting']=draft
    limited=at_limit(task) and task['status'] in ['waiting_student','needs_review','failed']
    result.update(restart_required=limited,student_view=limit_view() if limited else view,last_request_id=task['active_request'],current_action=object_value(task,'pending_action').get('kind',''),exit_reason=task.get('exit_reason') or '')
    return result


def validate_version(db,task,snapshot):
    question=object_value(snapshot,'question')
    if task['input_fingerprint']==fingerprint(snapshot) and question['status']!='archived' and question['confirmed'] is True:
        view=object_value(task,'student_view')
        for block in view.get('prompt_blocks') or []:
            if block.get('kind')=='question' and block.get('text')==question['question_text'] and object_value(task,'checkpoint').get('phase','')!='contrast':
                block.update(options=copy.deepcopy(question['options']),question_type=question['question_type'],images=[a['path'] for a in snapshot.get('assets') or [] if a.get('kind')=='question_figure'])
        task['student_view']=view
        return True
    if task['status'] not in ['cancelled','stale']:
        view=stopped_view('题目或学习依据已更新，请回原题重新开始')
        db.query("UPDATE learning_tasks SET status='stale',version=version+1,lease_token=NULL,lease_until=NULL,student_view=?,exit_reason='input_changed',updated_at=UTC_TIMESTAMP(6) WHERE id=?",[json.dumps(view,ensure_ascii=False),task['id']])
        db.query("UPDATE learning_task_actions SET status='stale',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",[task['id']])
        task.update(status='stale',student_view=view,version=integer_value(task,'version')+1)
    return False
