import json
from fastapi import HTTPException
from .accounts import current_user,read_json,secret
from .database import Database
from .manual_questions import answer_text
from .paper_validation import filters,payload
from .question_detail import query_array
from .questions import display_key
from .rows import row_json
from .security import new_id,media_url


def owned(db,paper_id,owner):
    rows=db.query('SELECT * FROM papers WHERE id=? AND user_id=?',[paper_id,owner]).rows
    if not rows:raise HTTPException(404,'试卷不存在或无权访问')
    return row_json('papers',rows[0])


def paper_question(db,question_id,owner):
    rows=db.query('SELECT * FROM questions WHERE id=? AND user_id=?',[question_id,owner]).rows
    if not rows:raise HTTPException(404,'题目不存在或无权访问')
    return row_json('questions',rows[0])


def analysis_ready(db,question_id):
    rows=db.query('SELECT id,final_answer FROM problem_analyses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',[question_id]).rows
    if not rows or not rows[0]['final_answer'].strip():return False
    return any(row['text'].strip() for row in db.query('SELECT text FROM reference_steps WHERE analysis_id=? ORDER BY step_index,id',[rows[0]['id']]).rows)


def detail(db,paper):
    paper_id=paper['id'];items=query_array(db,'paper_items','SELECT * FROM paper_items WHERE paper_id=? ORDER BY position,id',paper_id)
    for item in items:item.update(question=paper_question(db,item['question_id'],paper['user_id']),analysis_ready=analysis_ready(db,item['question_id']))
    exports=query_array(db,'export_jobs','SELECT * FROM export_jobs WHERE paper_id=? ORDER BY created_at DESC,id DESC',paper_id)
    for item in exports:item['url']=media_url('/'+item['path'],secret())
    paper.update(items=items,exports=exports);return paper


def insert_items(db,paper_id,owner,items):
    for position,item in enumerate(items):
        paper_question(db,item['question_id'],owner)
        db.query('INSERT INTO paper_items (id,paper_id,question_id,position,score,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[new_id(),paper_id,item['question_id'],position,item['score']])


def candidates_data(db,owner,criteria):
    result=[];seen=set();params=[owner];sql="SELECT * FROM questions WHERE user_id=? AND status<>'archived'"
    if criteria.get('subject'):sql+=' AND subject=?';params.append(criteria['subject'])
    for row in db.query(sql+' ORDER BY created_at DESC,id DESC',params).rows:
        question=row_json('questions',row);question_id=question['id'];key=display_key(question['question_text'],question_id)
        if key in seen:continue
        seen.add(key);analyses=db.query('SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1',[question_id]).rows
        knowledge=question['knowledge_points'] or (row_json('problem_analyses',analyses[0])['knowledge_points'] if analyses else [])
        diagnoses=db.query('SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',[question_id]).rows;diagnosis=row_json('diagnoses',diagnoses[0]) if diagnoses else {}
        needle=criteria.get('knowledge_point','')
        if needle and not any(needle in answer_text(point) for point in knowledge):continue
        error=criteria.get('error_type','')
        if error and error not in (diagnosis.get('error_type') or ''):continue
        score=0.
        for mastery in db.query('SELECT * FROM mastery_states WHERE user_id=? AND subject=? ORDER BY updated_at DESC,id DESC',[owner,row['subject']]).rows:
            if any(answer_text(p)==mastery['knowledge_point'] for p in knowledge):score=row_json('mastery_states',mastery)['mastery_score'];break
        if score<criteria.get('mastery_min',0) or score>criteria.get('mastery_max',1):continue
        reviews=db.query('SELECT * FROM review_plans WHERE user_id=? AND question_id=? ORDER BY due_at DESC,id DESC LIMIT 1',[owner,question_id]).rows
        if criteria.get('due_review') is True and (not reviews or reviews[0]['status']!='pending'):continue
        question.update(knowledge_points=knowledge,mastery_score=score,error_type=diagnosis.get('error_type','') if diagnoses else '未诊断',root_misconception=diagnosis.get('root_misconception') or '',review_due_at=row_json('review_plans',reviews[0])['due_at'] if reviews else None);result.append(question)
    return result


async def paper_candidates(request):
    raw={}
    for key in ['subject','knowledge_point','error_type']:
        value=request.query_params.get(key,'')
        if value:raw[key]=value
    for key in ['mastery_min','mastery_max']:
        value=request.query_params.get(key,'')
        if value:
            try:raw[key]=json.loads(value)
            except ValueError:raise HTTPException(422,'掌握度范围无效') from None
    if request.query_params.get('due_review'):raw['due_review']=request.query_params['due_review']
    criteria=filters(raw)
    with Database.from_environment() as db:return candidates_data(db,current_user(request,db)['id'],criteria)


async def papers(request):
    with Database.from_environment() as db:
        user=current_user(request,db);owner=user['id']
        if request.method=='GET':return query_array(db,'papers','SELECT * FROM papers WHERE user_id=? ORDER BY created_at,id',owner)
        body=payload(await read_json(request),True)
        with db.transaction():
            paper_id=new_id();criteria=body.get('filters') or {};ids=body['question_ids'] or [q['id'] for q in candidates_data(db,owner,criteria)[:body['limit']]]
            selected=[]
            for question_id in ids:
                score=body['default_score']
                for item in body.get('items',[]):
                    if item['question_id']==question_id:score=item['score']
                selected.append({'question_id':question_id,'score':score})
            db.query('INSERT INTO papers (id,user_id,title,filters,created_at,updated_at) VALUES (?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[paper_id,owner,body.get('title','我的错题练习'),json.dumps(criteria,ensure_ascii=False)])
            insert_items(db,paper_id,owner,selected);return owned(db,paper_id,owner)


async def paper_api(request):
    paper_id=request.path_params['paper_id']
    with Database.from_environment() as db:
        user=current_user(request,db);owner=user['id'];body=payload(await read_json(request),False) if request.method=='PATCH' else {}
        with db.transaction():
            if request.method=='DELETE':
                exists=bool(db.query('SELECT id FROM papers WHERE id=? AND user_id=?',[paper_id,owner]).rows)
                if exists:
                    for table in ['export_jobs','paper_items','papers']:db.query('DELETE FROM '+table+' WHERE '+('id' if table=='papers' else 'paper_id')+'=?',[paper_id])
                return {'deleted':exists}
            owned(db,paper_id,owner)
            if request.method=='PATCH':
                if 'title' in body:db.query('UPDATE papers SET title=?,updated_at=UTC_TIMESTAMP() WHERE id=?',[body['title'],paper_id])
                if 'filters' in body:db.query('UPDATE papers SET filters=?,updated_at=UTC_TIMESTAMP() WHERE id=?',[json.dumps(body['filters'],ensure_ascii=False),paper_id])
                if 'items' in body:
                    db.query('DELETE FROM paper_items WHERE paper_id=?',[paper_id]);insert_items(db,paper_id,owner,body['items'])
            return detail(db,owned(db,paper_id,owner))
