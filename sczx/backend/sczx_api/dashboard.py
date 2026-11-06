from .accounts import current_user
from .database import Database
from .insights import current_states,percent,graph_topic
from .questions import display_key
from .rows import row_json


def next_step(stage):
    return {'understanding':'理解错误原因','teach_back':'用自己的话讲清思路','teach_back_retry':'补充说明关键理由','near_transfer':'完成一道相似题','near_remediation':'再巩固一次','far_transfer':'完成综合应用','transfer_insufficient':'回顾方法后再练习'}.get(stage,'继续完成本次学习')


async def dashboard(request):
    with Database.from_environment() as db:
        user=current_user(request,db)
        with db.transaction():
            questions=db.query("SELECT id,question_text FROM questions WHERE user_id=? AND status<>'archived'",[user['id']]).rows
            unique={display_key(q['question_text'] or '',q['id']) for q in questions}
            reviews=int(db.query("SELECT COUNT(*) AS count FROM review_plans WHERE user_id=? AND status='pending' AND due_at<TIMESTAMP(DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR))+INTERVAL 16 HOUR",[user['id']]).rows[0]['count'])
            mastery,mistakes=current_states(db,user['id'],' LIMIT 8',' LIMIT 8');discoveries=[]
            for item in mistakes[:2]:discoveries.append({'kind':'attention','title':item['label'],'detail':'这是目前最需要优先巩固的错误原因','value':percent(item['probability'])})
            for item in mastery[:2]:
                stable=item['mastery_score']>=.75
                discoveries.append({'kind':'stable' if stable else 'progress','title':item['knowledge_point'],'detail':'掌握状态已经比较稳定' if stable else '继续完成相似题会更牢固','value':percent(item['mastery_score'])})
            sessions=db.query("SELECT * FROM tutor_sessions WHERE user_id=? AND status='active' ORDER BY updated_at DESC,id DESC LIMIT 1",[user['id']]).rows
            continuation=None
            if sessions:
                session=row_json('tutor_sessions',sessions[0]);active=db.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived'",[session['question_id'],user['id']]).rows
                state=session['state'] if isinstance(session['state'],dict) else {}
                if active and state.get('question_changed') is not True:continuation={'session_id':session['id'],'question_id':session['question_id'],'stage':session['stage'],'knowledge_point':graph_topic(row_json('questions',active[0])),'next_step':next_step(session['stage'])}
            streak=0;expected=-1
            days=db.query("SELECT DISTINCT DATEDIFF(DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR),DATE(created_at+INTERVAL 8 HOUR)) AS day_offset FROM questions WHERE user_id=? AND status<>'archived' AND created_at IS NOT NULL ORDER BY day_offset",[user['id']]).rows
            for row in days:
                day=int(row['day_offset'])
                if streak==0:
                    if day not in [0,1]:break
                    expected=day
                if day!=expected:break
                streak+=1;expected+=1
            profiles=db.query('SELECT grade FROM student_profiles WHERE user_id=? LIMIT 1',[user['id']]).rows
            grade=profiles[0]['grade'] if profiles else '初二'
            has_data=bool(questions or reviews>0 or mastery or mistakes or continuation is not None)
            minutes=max(3,reviews+(2 if continuation is None else 5)) if has_data else 0
            return {'today_reviews':reviews,'weekly_questions':len(unique),'mastered_points':sum(m['mastery_score']>=.7 for m in mastery),'streak_days':streak,'grade':grade,'estimated_minutes':minutes,'continue_learning':continuation,'discoveries':discoveries,'mastery':mastery,'misconceptions':mistakes,'ai_suggestion':'先弄懂最常出错的一步，再完成一道相似题。' if has_data else '拍下第一道错题，我会从你的解题步骤开始分析。'}
