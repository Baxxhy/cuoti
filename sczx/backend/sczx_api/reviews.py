import json
from fastapi import HTTPException
from .accounts import current_user,read_json,text_field,secret
from .algorithm import compute
from .database import Database
from .handwriting import validate_handwriting
from .learning_evidence import question_version,digest
from .question_detail import query_array
from .question_edit import text
from .questions import display_key
from .rows import row_json
from .security import media_url,new_id


def review_question(db,plan,owner):
    rows=db.query('SELECT * FROM questions WHERE id=? AND user_id=?',[plan['question_id'],owner]).rows
    if not rows:raise HTTPException(404,'题目不存在')
    return row_json('questions',rows[0])


def receipt(record):
    details=record.get('grading_details') or {};raw=details.get('handwriting_image_url') or '';path=raw.split('?',1)[0] if raw else ''
    result={'attempt_id':record['id'],'request_id':details.get('review_request_id',''),'correct':record['correct'] if details.get('can_update_learning') is True else None}
    result.update({key:details[key] for key in ['score','feedback','matched_points','can_update_learning']})
    result.update(grading={key:details[key] for key in ['verdict','correct','score','feedback','matched_points','can_update_learning']},expected_answer=record['expected_answer'],student_answer=record['student_answer'],handwriting_image_url=media_url(path,secret()),handwriting_recognition=details['handwriting_recognition'])
    return result


def renew_handwriting(record):
    details=record.get('grading_details') or {};raw=details.get('handwriting_image_url') or ''
    if raw:details['handwriting_image_url']=media_url(raw.split('?',1)[0],secret())


async def list_reviews(request,history=False):
    with Database.from_environment() as db:
        user=current_user(request,db);result=[]
        if history:
            for row in db.query("SELECT r.* FROM review_records r JOIN review_plans p ON p.id=r.plan_id WHERE p.user_id=? AND r.grade<>'pending' ORDER BY r.created_at DESC,r.id DESC",[user['id']]).rows:
                record=row_json('review_records',row);plan=row_json('review_plans',db.query('SELECT * FROM review_plans WHERE id=?',[row['plan_id']]).rows[0])
                questions=db.query('SELECT * FROM questions WHERE id=? AND user_id=?',[plan['question_id'],user['id']]).rows
                renew_handwriting(record);record.update(plan=plan,question=row_json('questions',questions[0]) if questions else None);result.append(record)
        else:
            seen=set()
            for row in db.query("SELECT * FROM review_plans WHERE user_id=? AND status='pending' AND due_at<TIMESTAMPADD(HOUR,16,DATE(TIMESTAMPADD(HOUR,8,UTC_TIMESTAMP()))) ORDER BY due_at,id",[user['id']]).rows:
                plan=row_json('review_plans',row);question=review_question(db,plan,user['id'])
                if question['status']=='archived':continue
                key=display_key(question['question_text'],question['id'])
                if key in seen:continue
                seen.add(key);visible={k:v for k,v in question.items() if k!='student_answer'}
                figures=query_array(db,'question_assets',"SELECT * FROM question_assets WHERE question_id=? AND kind='question_figure' ORDER BY created_at,id",question['id'])
                for figure in figures:figure['url']=media_url('/'+figure['path'],secret())
                visible['question_figures']=figures;plan['question']=visible
                version=question_version(db,question);plan.update(source_version=version,pending_attempt=None)
                pending=db.query("SELECT * FROM review_records WHERE plan_id=? AND grade='pending' AND COALESCE(JSON_UNQUOTE(JSON_EXTRACT(grading_details,'$.review_record_state')),'current')<>'superseded' ORDER BY created_at DESC,id DESC LIMIT 1",[row['id']]).rows
                if pending:
                    record=row_json('review_records',pending[0])
                    if (record.get('grading_details') or {}).get('memory_question_version','')==version:plan['pending_attempt']=receipt(record)
                if 'again' in (plan.get('reason') or '').lower():plan['reason']='本次作答需要重做，安排 1 天后再次复习'
                result.append(plan)
        return result


async def attempt_review(request):
    plan_id=request.path_params['plan_id']
    with Database.from_environment() as db:
        user=current_user(request,db);body=await read_json(request);answer=text(body.get('answer',''),12000,trim=True)
        with db.transaction():
            rows=db.query("SELECT * FROM review_plans WHERE id=? AND user_id=? AND status='pending' FOR UPDATE",[plan_id,user['id']]).rows
            if not rows:raise HTTPException(404,'待复习题不存在')
            plan=row_json('review_plans',rows[0]);question=review_question(db,plan,user['id'])
            if question['status']=='archived':raise HTTPException(409,'题目已归档')
            version=question_version(db,question);supplied=body.get('source_version') if isinstance(body.get('source_version'),str) else ''
            if supplied and supplied!=version:raise HTTPException(409,'原题或参考已更新，请刷新后核对答案')
            request_id=text_field(body,'request_id',80) if 'request_id' in body else ''
            request_digest=digest([body.get(k) for k in ['answer','handwriting_image_url','handwriting_recognition']])
            if request_id:
                previous=db.query("SELECT * FROM review_records WHERE plan_id=? AND JSON_UNQUOTE(JSON_EXTRACT(grading_details,'$.review_request_id'))=? LIMIT 1",[plan_id,request_id]).rows
                if previous:
                    record=row_json('review_records',previous[0]);details=record.get('grading_details') or {}
                    if details.get('review_record_state')=='superseded':raise HTTPException(409,'已有更新的复习作答，请刷新查看当前判题')
                    if details.get('review_request_digest')!=request_digest or details.get('memory_question_version')!=version:raise HTTPException(409,'提交编号对应的作答或原题已变化，请核对后重新提交')
                    return receipt(record)
            analyses=db.query('SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1',[plan['question_id']]).rows
            if not analyses or not analyses[0]['final_answer']:raise HTTPException(422,'这道题还没有标准答案，请先在题目详情中完成分析')
            analysis=row_json('problem_analyses',analyses[0]);handwriting=validate_handwriting(body,user['id'],plan_id,kind='review')
            references=query_array(db,'reference_steps','SELECT * FROM reference_steps WHERE analysis_id=? ORDER BY step_index',analysis['id'])
            grading=compute({'operation':'grade_answer','text':question['question_text'],'answer':answer,'expected':analysis['final_answer'],'subject':question['subject'],'question_type':question['question_type'],'options':question['options'],'reference_solution':[r['text'] for r in references]})
            details=dict(grading);details.update(memory_question_version=version,review_request_id=request_id,review_request_digest=request_digest,handwriting_image_url=handwriting['image_url'],handwriting_recognition=handwriting['recognition'])
            db.query("UPDATE review_records SET grading_details=JSON_SET(grading_details,'$.review_record_state','superseded') WHERE plan_id=? AND grade='pending'",[plan_id])
            record_id=new_id()
            db.query("INSERT INTO review_records (id,plan_id,grade,correct,student_answer,expected_answer,feedback,score,grading_details,created_at,updated_at) VALUES (?,?,'pending',?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[record_id,plan_id,grading['correct'],answer,analysis['final_answer'],grading['feedback'],grading['score'],json.dumps(details,ensure_ascii=False)])
            return receipt(row_json('review_records',db.query('SELECT * FROM review_records WHERE id=?',[record_id]).rows[0]))


async def grade_review(request):
    plan_id=request.path_params['plan_id']
    with Database.from_environment() as db:
        user=current_user(request,db);body=await read_json(request)
        with db.transaction():
            rows=db.query('SELECT * FROM review_plans WHERE id=? AND user_id=? FOR UPDATE',[plan_id,user['id']]).rows
            if not rows:raise HTTPException(404,'复习计划不存在')
            plan=row_json('review_plans',rows[0])
            if plan['status']!='pending':raise HTTPException(409,'这次复习已完成，请刷新复习列表')
            attempt_id=body.get('attempt_id') if isinstance(body.get('attempt_id'),str) else ''
            records=db.query("SELECT * FROM review_records WHERE id=? AND plan_id=? AND grade='pending'",[attempt_id,plan_id]).rows
            if not records:raise HTTPException(422,'请先提交答案并完成系统判定')
            record=row_json('review_records',records[0]);details=record.get('grading_details') or {}
            if details.get('review_record_state')=='superseded':raise HTTPException(409,'已有更新的复习作答，请刷新查看当前判题')
            if details.get('can_update_learning',True) is not True:raise HTTPException(409,'这次判题仍需核对，不能据此更新复习计划')
            question=review_question(db,plan,user['id']);version=details.get('memory_question_version','')
            if question['status']=='archived' or version and version!=question_version(db,question):raise HTTPException(409,'原题或参考已更新，请重新提交作答再评价复习')
            grade=body.get('grade','good');correct=record['correct'] is True
            labels={'again':(1,'还没想起来'),'hard':(2 if correct else 1,'有点困难'),'good':(7 if correct else 2,'已经掌握'),'easy':(15 if correct else 4,'很轻松')}
            if not isinstance(grade,str) or grade not in labels:raise HTTPException(422,'请选择有效的复习反馈')
            days,label=labels[grade]
            db.query("UPDATE review_plans SET status='completed',updated_at=UTC_TIMESTAMP() WHERE id=?",[plan_id])
            db.query('UPDATE review_records SET grade=?,updated_at=UTC_TIMESTAMP() WHERE id=?',[grade,record['id']])
            next_id=new_id();reason='上次作答'+('正确' if correct else '有误')+'，随后选择了“'+label+'”'
            db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,TIMESTAMPADD(DAY,?,UTC_TIMESTAMP()),?,?,'pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[next_id,user['id'],plan['question_id'],days,days,reason])
            saved=row_json('review_records',db.query('SELECT * FROM review_records WHERE id=?',[record['id']]).rows[0]);renew_handwriting(saved)
            return {'record':saved,'next_plan':row_json('review_plans',db.query('SELECT * FROM review_plans WHERE id=?',[next_id]).rows[0])}
