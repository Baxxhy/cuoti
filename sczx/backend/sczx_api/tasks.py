"""Learning task request lifecycle; execution is handled by the task worker."""
import hashlib
import json
from fastapi import HTTPException
from .accounts import text_field
from .database import Database
from .learning_evidence import digest
from .memory_sources import task_snapshot
from .practice import request_text
from .rows import row_json
from .security import new_id
from .task_core import owner,task_row,public,validate_version
from .task_policy import object_value,visual_values,validate_visual_action,at_limit,stopped_view
from .task_sources import fingerprint,source
from .tutor_answer import summary


def strict(body,allowed):
    if any(key not in allowed for key in body):raise HTTPException(422,'请求包含不支持的字段')


def authorize(request,task_id=None):
    with Database.from_environment() as db:
        user_id=owner(request,db)
        if task_id is not None:task_row(db,task_id,user_id)


def list_tasks(request):
    with Database.from_environment() as db:
        user_id=owner(request,db);qid=request.query_params.get('question_id','');result=[]
        for row in db.query("SELECT * FROM learning_tasks WHERE user_id=? AND (?='' OR question_id=?) ORDER BY updated_at DESC,id DESC LIMIT 50",[user_id,qid,qid]).rows:
            item=public(row_json('learning_tasks',row));titles=db.query('SELECT question_text FROM questions WHERE id=?',[row['question_id']]).rows
            item['question_title']=summary(titles[0]['question_text'],60) if titles else '本题学习';result.append(item)
        return result


def create_task(request,body):
    with Database.from_environment() as db:
        user_id=owner(request,db);strict(body,['question_id','session_id','request_id'])
        qid=text_field(body,'question_id',36);request_id=text_field(body,'request_id',80);sid=request_text(body,'session_id',36)
        body_hash=hashlib.sha256((qid+'|'+sid).encode()).hexdigest()
        with db.transaction():
            snapshot=task_snapshot(db,qid,user_id,lock=True);question=snapshot['question']
            previous=db.query('SELECT task_id,body_hash FROM learning_task_requests WHERE user_id=? AND request_id=?',[user_id,request_id]).rows
            if previous:
                if previous[0]['body_hash']!=body_hash:raise HTTPException(409,'同一请求编号不能用于不同任务')
                task=task_row(db,previous[0]['task_id'],user_id,True);validate_version(db,task,snapshot);return public(task)
            if question['status']=='archived' or question['confirmed'] is not True or not isinstance(snapshot['analysis'],dict) or not (snapshot['analysis'].get('final_answer') or '').strip():raise HTTPException(409,'请先核对题目并完成分析，再开始订正学习')
            if sid and not db.query('SELECT id FROM tutor_sessions WHERE id=? AND user_id=? AND question_id=?',[sid,user_id,qid]).rows:raise HTTPException(404,'关联学习会话不存在')
            task_id='';origin='legacy_revalidated'
            active=db.query("SELECT * FROM learning_tasks WHERE user_id=? AND question_id=? AND status IN ('queued','running','waiting_student','needs_review','failed') ORDER BY created_at DESC,id DESC LIMIT 1 FOR UPDATE",[user_id,qid]).rows
            if active:
                task=row_json('learning_tasks',active[0])
                if validate_version(db,task,snapshot):task_id=task['id']
            if not task_id:
                task_id=new_id();origin='created';event={'kind':'start','text':''}
                db.query("INSERT INTO learning_tasks (id,user_id,question_id,session_id,input_fingerprint,status,step_id,checkpoint,student_view,pending_action,active_request,created_at,updated_at) VALUES (?,?,?,?,?,'queued',?,JSON_OBJECT(),?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[task_id,user_id,qid,sid or None,fingerprint(snapshot),new_id(),json.dumps(stopped_view('正在准备这一步'),ensure_ascii=False),json.dumps(event,ensure_ascii=False),'__initial__'])
            source(db,task_row(db,task_id,user_id),snapshot,origin=origin)
            db.query('INSERT INTO learning_task_requests (user_id,request_id,task_id,body_hash,created_at) VALUES (?,?,?,?,UTC_TIMESTAMP(6))',[user_id,request_id,task_id,body_hash])
            return public(task_row(db,task_id,user_id))


def read_task(request,task_id):
    with Database.from_environment() as db:
        user_id=owner(request,db);initial=task_row(db,task_id,user_id)
        with db.transaction():
            snapshot=task_snapshot(db,initial['question_id'],user_id,lock=True);task=task_row(db,task_id,user_id,True)
            validate_version(db,task,snapshot);return public(task)


def task_action(request,task_id,body,cancel=False):
    from .task_images import attach_image
    with Database.from_environment() as db:
        user_id=owner(request,db);initial=task_row(db,task_id,user_id)
        if not cancel:strict(body,['kind','text','version','step_id','input_fingerprint','request_id','handwriting_id','handwriting_confirmed','visual_values'])
        with db.transaction():
            snapshot=task_snapshot(db,initial['question_id'],user_id,lock=True);task=task_row(db,task_id,user_id,True)
            if cancel:
                if task['status'] not in ['completed','cancelled','stale']:
                    db.query("UPDATE learning_tasks SET status='cancelled',cancel_requested=1,version=version+1,lease_token=NULL,lease_until=NULL,student_view=?,exit_reason='student_cancelled',updated_at=UTC_TIMESTAMP(6) WHERE id=?",[json.dumps(stopped_view('已结束这次学习，之前的记录仍在'),ensure_ascii=False),task_id])
                    db.query("UPDATE learning_task_actions SET status='cancelled',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",[task_id])
                return public(task_row(db,task_id,user_id))
            request_id=text_field(body,'request_id',80);values=visual_values(body)
            hash_values=[body.get(k,'' if k=='text' else None) for k in ['kind','text','version','step_id','input_fingerprint','handwriting_id','handwriting_confirmed']]
            if 'visual_values' in body:hash_values.append([values.get(k) for k in ['delta','k','b','a','h']])
            body_hash=digest(hash_values)
            if request_id=='__initial__':raise HTTPException(422,'请求编号不可用')
            prior=db.query('SELECT body_hash FROM learning_task_actions WHERE task_id=? AND request_id=?',[task_id,request_id]).rows
            if prior:
                if prior[0]['body_hash']!=body_hash:raise HTTPException(409,'同一请求编号不能修改提交内容')
                validate_version(db,task,snapshot);return public(task)
            if not validate_version(db,task,snapshot):return public(task)
            status=task['status']
            if status not in ['waiting_student','needs_review','failed']:raise HTTPException(409,'任务仍在处理或已结束，请先刷新状态')
            version=body.get('version')
            if type(version) is not int or version!=task['version'] or text_field(body,'step_id',36)!=task['step_id'] or text_field(body,'input_fingerprint',64)!=task['input_fingerprint']:raise HTTPException(409,'这一步已更新，请保留内容并刷新后再提交')
            kind=text_field(body,'kind',30)
            if kind not in ['answer','hint','reveal','resume','use_text','visualize','observe_visualization','close_visualization']:raise HTTPException(422,'不支持的学习动作')
            validate_visual_action(task,body,kind,values)
            text=text_field(body,'text',1200) if kind=='observe_visualization' else request_text(body,'text',12000)
            if kind in ['answer','observe_visualization'] and not text.strip():raise HTTPException(422,'请先写下你的回答')
            if at_limit(task):raise HTTPException(409,'这次学习已到上限，请结束后回原题重开')
            event={'kind':kind,'text':text}
            if kind=='observe_visualization':event['visual_values']=values
            attach_image(db,task,body,event)
            if kind=='resume' and status=='failed' and object_value(task,'pending_action').get('kind')=='recognize_handwriting':event.update(kind='recognize_handwriting',handwriting_id=task['pending_action']['handwriting_id'])
            db.query("INSERT INTO learning_task_actions (id,task_id,request_id,body_hash,kind,input_version,input_step_id,body,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,'pending',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[new_id(),task_id,request_id,body_hash,kind,version,task['step_id'],json.dumps(event,ensure_ascii=False)])
            db.query("UPDATE learning_tasks SET status='queued',version=version+1,pending_action=?,active_request=?,lease_token=NULL,lease_until=NULL,exit_reason='',updated_at=UTC_TIMESTAMP(6) WHERE id=?",[json.dumps(event,ensure_ascii=False),request_id,task_id])
            return public(task_row(db,task_id,user_id))
