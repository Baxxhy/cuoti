import re
from fastapi import HTTPException
from .algorithm import compute
from .question_edit import text
from .storage import read_media


def validate_handwriting(body,owner,session_id,kind='tutor'):
    raw=text(body.get('handwriting_image_url',''),2048,trim=True)
    recognition=body.get('handwriting_recognition')
    if not raw:
        if recognition is not None:raise HTTPException(422,'手写识别结果缺少对应原图')
        return {'image_url':'','recognition':None}
    path=raw.split('?',1)[0];prefix=f'/uploads/answers/{owner}/{kind}/{session_id}/handwriting-'
    if not path.startswith(prefix) or not re.fullmatch(r'[0-9a-f]{32}\.jpg',path[len(prefix):]):raise HTTPException(422,'手写作答图片无效')
    try:read_media(path[1:])
    except Exception:raise HTTPException(422,'手写作答图片无效') from None
    if recognition is not None and not isinstance(recognition,dict):raise HTTPException(422,'手写作答识别结果无效')
    return {'image_url':path,'recognition':compute({'operation':'validate_handwriting','recognition':recognition or {}})}


async def upload_handwriting(request):
    import base64
    from .accounts import current_user,secret
    from .algorithm import image_bytes
    from .database import Database
    from .ingest import read_upload
    from .practice_context import handwriting_context
    from .rows import row_json
    from .security import new_id,media_url
    from .storage import write_media
    from .tutor_read import session_activity
    from .tutor_variants import data_snapshot
    with Database.from_environment() as db:
        user=current_user(request,db)
        uploaded,filename,deferred,fields=await read_upload(request,include_fields=True)
        kind,context_id,activity_id=fields.get('context_type',''),fields.get('context_id',''),fields.get('activity_id','')
        if kind not in ['tutor','review','practice']:raise HTTPException(422,'不支持的答题场景')
        with db.transaction():
            if kind=='practice':visible=handwriting_context(db,user['id'],fields.get('mistake_id',''),context_id,fields.get('mode','reinforce'))
            elif kind=='review':
                plans=db.query("SELECT * FROM review_plans WHERE id=? AND user_id=? AND status='pending'",[context_id,user['id']]).rows
                if not plans:raise HTTPException(404,'待复习题不存在')
                questions=db.query('SELECT * FROM questions WHERE id=? AND user_id=?',[plans[0]['question_id'],user['id']]).rows
                if not questions:raise HTTPException(404,'题目不存在')
                question=row_json('questions',questions[0])
                if question['options']:raise HTTPException(422,'选择题请直接选择选项')
                visible={'subject':question['subject'],'text':question['question_text']}
            else:
                sessions=db.query('SELECT * FROM tutor_sessions WHERE id=? AND user_id=?',[context_id,user['id']]).rows
                if not sessions:raise HTTPException(404,'学习会话不存在')
                session=row_json('tutor_sessions',sessions[0]);value=data_snapshot(db,session['question_id'],user['id']);question=value['question']
                state=session['state'] if isinstance(session['state'],dict) else {}
                if state.get('question_changed') is True or question['status']=='archived':raise HTTPException(409,'题目已变化或归档，请重新开始学习')
                activity=session_activity(db,session,value)
                if not isinstance(activity,dict) or activity.get('id')!=activity_id:raise HTTPException(409,'当前练习已经变化，请刷新后重新上传')
                if activity.get('type') in ['single_choice','multiple_choice','explanation','teach_back']:raise HTTPException(422,'当前练习不需要上传手写过程')
                visible={'subject':question['subject'],'text':activity['question']}
        image=image_bytes(compute({'operation':'normalize','image_base64':base64.b64encode(uploaded).decode()}))
        path=f"uploads/answers/{user['id']}/{kind}/{context_id}/handwriting-{new_id().replace('-','')}.jpg"
        write_media(path,image)
        try:computed=compute({'operation':'recognize_handwriting','image_base64':base64.b64encode(image).decode(),'subject':visible['subject'],'text':visible['text']})
        except Exception:raise HTTPException(503,'照片已保留，但暂时无法识别，请稍后重试或使用文字输入') from None
        return {'image_url':media_url('/'+path,secret()),'recognition':computed['recognition']}
