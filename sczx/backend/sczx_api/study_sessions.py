import json
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from .accounts import current_user,read_json
from .adaptive_practice import selection
from .algorithm import compute
from .database import Database
from .dataset_images import image_layout,bank_question,solution_images
from .memory_sources import task_snapshot,task_fingerprint
from .question_edit import text
from .retrieval import usable_candidate
from .review_search import optional_text
from .rows import row_json
from .security import new_id
from .study_bank import student_grade,scoped_where,bank_filter


def integer(value,minimum,maximum):
    if type(value) is not int:raise HTTPException(422,'请填写整数')
    if not minimum<=value<=maximum:raise HTTPException(422,'整数超出允许范围')
    return value


def session_row(row):
    value={}
    for key,raw in row.items():
        value[key]=None if raw is None else int(raw) if key in ['version','duration_seconds','remaining_seconds','question_count','expired'] else json.loads(raw) if key=='results' else raw
    return value


def owned(db,session_id,owner,lock=False):
    rows=db.query('SELECT *,CEIL(GREATEST(0,COALESCE(TIMESTAMPDIFF(MICROSECOND,UTC_TIMESTAMP(6),deadline_at),0))/1000000) AS remaining_seconds,IF(deadline_at IS NOT NULL AND deadline_at<=UTC_TIMESTAMP(6),1,0) AS expired FROM study_sessions WHERE id=? AND user_id=?'+(' FOR UPDATE' if lock else ''),[session_id,owner]).rows
    if not rows:raise HTTPException(404,'没有找到这次练习或考试')
    return session_row(rows[0])


def items(db,session_id):
    return [{'id':r['id'],'position':int(r['position']),'snapshot':json.loads(r['snapshot']),'student_answer':json.loads(r['student_answer']) if r['student_answer'] is not None else None,'grading':json.loads(r['grading']) if r['grading'] is not None else None} for r in db.query('SELECT * FROM study_session_items WHERE session_id=? ORDER BY position',[session_id]).rows]


def available(db,snapshot,lock=False):
    if image_layout(snapshot)['review'] or snapshot['quality_status']=='format_review':return False
    rows=db.query('SELECT quality_status,source_metadata FROM dataset_questions WHERE id=?'+(' FOR SHARE' if lock else ''),[snapshot['id']]).rows
    if not rows:return True
    if rows[0]['quality_status']=='format_review':return False
    metadata=json.loads(rows[0]['source_metadata'])
    return not any(e.get('content_hash','')==snapshot.get('content_hash','') for e in metadata.get('format_review_history',[]))


def detail(db,value):
    public=[];submitted=value['status']=='submitted'
    for item in items(db,value['id']):
        snapshot=item['snapshot'];usable=available(db,snapshot)
        result={'id':item['id'],'position':item['position'],'student_answer':item['student_answer'],'unavailable':not usable,'question':bank_question(snapshot) if usable else {k:snapshot[k] for k in ['subject','question_type']}}
        if submitted:
            added=db.query("SELECT id FROM questions WHERE user_id=? AND status<>'archived' AND JSON_CONTAINS(tags,JSON_QUOTE(?)) LIMIT 1",[value['user_id'],'study-item:'+item['id']]).rows
            result.update(mistake_id=added[0]['id'] if added else None,grading=item['grading'])
            if usable:result.update(answer=snapshot['answer'],solution=snapshot['solution'],**solution_images(snapshot))
        public.append(result)
    value.update(items=public,question_count=len(public));return value


async def sessions(request):
    with Database.from_environment() as db:
        user=current_user(request,db);owner=user['id']
        if request.method=='GET':return [session_row(r) for r in db.query('SELECT s.*,(SELECT COUNT(*) FROM study_session_items i WHERE i.session_id=s.id) AS question_count FROM study_sessions s WHERE s.user_id=? ORDER BY s.created_at DESC,s.id DESC LIMIT 50',[owner]).rows]
        grade=student_grade(db,owner);body=await read_json(request);mode=optional_text(body,'mode',20,'practice')
        if mode not in ['practice','exam']:raise HTTPException(422,'请选择练习或模拟考试')
        subject=optional_text(body,'subject',30);band=optional_text(body,'grade_band',30);source=optional_text(body,'source_id',36);search=optional_text(body,'search',300)
        count=integer(body.get('count',5),1,20);minutes=integer(body.get('minutes',15),1,180);ids=body.get('question_ids',[])
        if not isinstance(ids,list):raise HTTPException(422,'题目编号格式无效')
        if len(ids)>1:raise HTTPException(422,'单题练习请选择一道题')
        strategy=optional_text(body,'selection_strategy',20,'random')
        if strategy not in ['random','adaptive']:raise HTTPException(422,'选题方式无效')
        selected_result=selection(db,owner,subject,band,source,search,count,grade) if strategy=='adaptive' and mode=='practice' and not ids else {}
        selected=selected_result.get('question_ids') or [];task_id=optional_text(body,'learning_task_id',36)
        if task_id and (mode!='practice' or len(ids)!=1):raise HTTPException(422,'请选择本次学习推荐的一道题')
        with db.transaction():
            filters=bank_filter(subject,band,source,search,grade);base='SELECT q.*'+scoped_where(grade)
            if task_id:
                tasks=db.query('SELECT * FROM learning_tasks WHERE id=? AND user_id=?',[task_id,owner]).rows
                if not tasks:raise HTTPException(404,'学习任务不存在或无权访问')
                task=row_json('learning_tasks',tasks[0]);recommendation=(task.get('student_view') or {}).get('recommendation') or {};requested=text(ids[0],36,1,True)
                if task['status']!='completed' or recommendation.get('question_source')!='dataset' or recommendation.get('question_id')!=requested:raise HTTPException(409,'请从已完成的学习任务打开推荐题')
                snapshot=task_snapshot(db,task['question_id'],owner,lock=True)
                if task['input_fingerprint']!=task_fingerprint(db,task['question_id'],owner) or snapshot['question']['status']=='archived' or snapshot['question']['confirmed'] is not True:raise HTTPException(409,'原题已更新，请重新学习后获取推荐')
                rows=db.query('SELECT * FROM dataset_questions WHERE id=?',[requested]).rows
                if not rows or not usable_candidate(snapshot['question'],row_json('dataset_questions',rows[0]),'practice'):raise HTTPException(409,'推荐题已更新，请重新获取练习')
            elif selected:
                rows=[]
                for item_id in selected:rows.extend(db.query(base+' AND q.id=?',filters+[item_id]).rows)
            elif not ids:rows=db.query(base+f' ORDER BY RAND() LIMIT {count}',filters).rows
            else:rows=db.query(base+' AND q.id=?',filters+[text(ids[0],36,1,True)]).rows
            if not rows or not ids and len(rows)<count:raise HTTPException(422,'当前范围可用题目不足，请减少题数或更换学科')
            for row in rows:
                if image_layout(row_json('dataset_questions',row))['review']:raise HTTPException(422,'题图需要核对，请选择其他题目')
            session_id=new_id();title=(subject or '综合')+'模拟试卷' if mode=='exam' else (subject or '题库')+'练习'
            db.query("INSERT INTO study_sessions (id,user_id,mode,title,subject,grade_band,status,duration_seconds,deadline_at,version,created_at,updated_at) VALUES (?,?,?,?,?,?,'active',?,IF(?='exam',TIMESTAMPADD(SECOND,?,UTC_TIMESTAMP(6)),NULL),1,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[session_id,owner,mode,title,subject,band,minutes*60,mode,minutes*60])
            for position,row in enumerate(rows):
                snapshot=row_json('dataset_questions',row);sources=db.query('SELECT name FROM dataset_sources WHERE id=?',[row['dataset_source_id']]).rows
                if selected:snapshot['adaptive_selection']=selected_result
                snapshot['source_name']=sources[0]['name'] if sources else '题库'
                db.query('INSERT INTO study_session_items (id,session_id,position,snapshot,student_answer,grading) VALUES (?,?,?,?,NULL,NULL)',[new_id(),session_id,position,json.dumps(snapshot,ensure_ascii=False)])
            return detail(db,owned(db,session_id,owner))


def study_answer(value):
    if value is None:return None
    if isinstance(value,str):return text(value,3000)
    if isinstance(value,list):
        if len(value)>12:raise HTTPException(422,'选项过多')
        result=[]
        for entry in value:
            clean=text(entry,30,1,True)
            if clean in result:raise HTTPException(422,'选项不能重复')
            result.append(clean)
        return result
    raise HTTPException(422,'作答格式无效')


def answered(value):
    return bool(value.strip()) if isinstance(value,str) else bool(value) if isinstance(value,list) else False


def unavailable_grade():return {'correct':None,'can_update_learning':False,'method':'question_unavailable','feedback':'此题已暂停使用，未计分'}


def grade_item(item):
    if not answered(item['student_answer']):return {'correct':False,'can_update_learning':True,'feedback':'未作答','method':'unanswered'}
    question=item['snapshot']
    return compute({'operation':'grade_answer','text':question['question_text'],'answer':item['student_answer'],'expected':question['answer'],'subject':question['subject'],'question_type':question['question_type'],'options':question['options'],'reference_solution':[line for line in question['solution'].split('\n') if line.strip()]},timeout=20)


def grade_batches(current_items,blocked):
    results=[]
    for start in range(0,len(current_items),4):
        batch=current_items[start:start+4]
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures=[executor.submit(unavailable_grade) if item['id'] in blocked else executor.submit(grade_item,item) for item in batch]
            results.extend(job.result() for job in futures)
    return results


async def session_api(request,submitting=False):
    session_id=request.path_params['session_id']
    with Database.from_environment() as db:
        user=current_user(request,db);owner=user['id']
        if request.method=='GET':return detail(db,owned(db,session_id,owner))
        body=await read_json(request);version=integer(body.get('version'),1,100000000)
        if not submitting:
            answers=body.get('answers')
            if not isinstance(answers,list):raise HTTPException(422,'请提交作答列表')
            with db.transaction():
                session=owned(db,session_id,owner,True)
                if session['status']!='active':raise HTTPException(409,'已经交卷，不能修改作答')
                if session['version']!=version:raise HTTPException(409,'作答已在其他页面更新，请重新读取')
                if session['mode']=='exam' and session['expired']==1:raise HTTPException(409,'考试时间已到，请交卷')
                current=items(db,session_id);allowed={i['id'] for i in current};seen=set()
                if len(answers)!=len(current):raise HTTPException(422,'作答题目与试卷不一致')
                for raw in answers:
                    if not isinstance(raw,dict):raise HTTPException(422,'作答格式无效')
                    item_id=optional_text(raw,'id',36)
                    if item_id not in allowed or item_id in seen:raise HTTPException(422,'作答题目与试卷不一致')
                    seen.add(item_id);clean=study_answer(raw.get('answer'))
                    db.query('UPDATE study_session_items SET student_answer=? WHERE id=? AND session_id=?',[json.dumps(clean,ensure_ascii=False),item_id,session_id])
                db.query('UPDATE study_sessions SET version=version+1,updated_at=UTC_TIMESTAMP(6) WHERE id=?',[session_id])
                return detail(db,owned(db,session_id,owner))
        before=owned(db,session_id,owner)
        if before['status']=='submitted':return detail(db,before)
        if before['version']!=version:raise HTTPException(409,'作答已更新，请重新读取后交卷')
        current_items=items(db,session_id);blocked={i['id'] for i in current_items if not available(db,i['snapshot'])}
        results=await run_in_threadpool(grade_batches,current_items,blocked)
        with db.transaction():
            session=owned(db,session_id,owner,True)
            if session['status']=='submitted':return detail(db,session)
            if session['version']!=version:raise HTTPException(409,'作答已更新，本次判分未保存，请重新交卷')
            correct=pending=answer_count=excluded=0
            for item,result in zip(current_items,results):
                usable=available(db,item['snapshot'],True);grading=result if usable else unavailable_grade()
                if answered(item['student_answer']):answer_count+=1
                if not usable:excluded+=1
                elif grading.get('can_update_learning') is not True:pending+=1
                elif grading.get('correct') is True:correct+=1
                db.query('UPDATE study_session_items SET grading=? WHERE id=? AND session_id=?',[json.dumps(grading,ensure_ascii=False),item['id'],session_id])
            summary={'correct':correct,'pending':pending,'answered':answer_count,'total':len(current_items),'score':correct*5,'max_score':(len(current_items)-excluded)*5}
            if excluded:summary['excluded']=excluded
            db.query("UPDATE study_sessions SET status='submitted',results=?,version=version+1,submitted_at=UTC_TIMESTAMP(6),updated_at=UTC_TIMESTAMP(6) WHERE id=?",[json.dumps(summary),session_id])
            return detail(db,owned(db,session_id,owner))
