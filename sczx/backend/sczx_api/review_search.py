import json
import re
from fastapi import HTTPException
from .accounts import current_user,read_json
from .database import Database
from .security import new_id


def optional_text(body,key,limit,default=''):
    value=body.get(key,default)
    if not isinstance(value,str):raise HTTPException(422,f'{key} 必须是文字')
    if len(value)>limit:raise HTTPException(422,f'{key} 长度不正确')
    return value


async def search_reviews(request):
    query=request.query_params.get('q','').strip();subject=request.query_params.get('subject','');scope=request.query_params.get('scope') or 'pending';raw=request.query_params.get('page') or '1'
    if len(query.encode())>300 or len(subject.encode())>100 or scope not in ['pending','today','completed']:raise HTTPException(422,'复习筛选条件无效')
    if not re.fullmatch(r'[+-]?[0-9]+',raw):raise HTTPException(422,'页码无效')
    page=int(raw)
    if not 1<=page<=10000:raise HTTPException(422,'页码无效')
    with Database.from_environment() as db:
        user=current_user(request,db)
        criteria=" FROM review_plans p JOIN questions q ON q.id=p.question_id AND q.user_id=p.user_id WHERE p.user_id=? AND q.status<>'archived'"
        params=[user['id']];criteria+=" AND p.status='completed'" if scope=='completed' else " AND p.status='pending'"
        if scope=='today':criteria+=' AND p.due_at<TIMESTAMPADD(HOUR,16,DATE(TIMESTAMPADD(HOUR,8,UTC_TIMESTAMP())))'
        if subject:criteria+=' AND q.subject=?';params.append(subject)
        if query:
            criteria+=' AND (LOCATE(?,q.question_text)>0 OR LOCATE(?,CAST(q.knowledge_points AS CHAR))>0 OR LOCATE(?,p.reason)>0 OR LOCATE(?,q.title)>0)';params.extend([query]*4)
        total=int(db.query('SELECT COUNT(*) AS total'+criteria,params).rows[0]['total'])
        sql='SELECT p.id,p.question_id,p.due_at,p.reason,p.status,q.subject,q.grade,q.title,q.question_text,q.knowledge_points,(p.due_at<TIMESTAMPADD(HOUR,16,DATE(TIMESTAMPADD(HOUR,8,UTC_TIMESTAMP())))) AS is_due'+criteria+' ORDER BY p.due_at '+('DESC' if scope=='completed' else 'ASC')+f',p.id LIMIT 20 OFFSET {(page-1)*20}'
        items=[]
        for row in db.query(sql,params).rows:
            item={k:row[k] or '' for k in ['id','question_id','due_at','reason','status','subject','grade','title','question_text']}
            item.update(due_at=row['due_at'].replace(' ','T')+'+00:00',knowledge_points=json.loads(row['knowledge_points']),is_due=row['is_due']=='1');items.append(item)
        return {'items':items,'total':total,'page':page,'page_size':20}


async def saved_filters(request,deleting=False):
    with Database.from_environment() as db:
        user=current_user(request,db)
        if deleting:
            filter_id=request.path_params['filter_id']
            if not db.query('SELECT id FROM saved_review_filters WHERE id=? AND user_id=?',[filter_id,user['id']]).rows:raise HTTPException(404,'复习范围不存在')
            db.query('DELETE FROM saved_review_filters WHERE id=? AND user_id=?',[filter_id,user['id']]);return {'deleted':True}
        if request.method=='POST':
            body=await read_json(request);name=optional_text(body,'name',80).strip();query=optional_text(body,'q',300).strip();subject=optional_text(body,'subject',30);scope=optional_text(body,'scope',20,'pending')
            if not name or scope not in ['pending','today','completed']:raise HTTPException(422,'请填写名称并选择有效的复习范围')
            with db.transaction():
                db.query('SELECT id FROM users WHERE id=? FOR UPDATE',[user['id']])
                existing=db.query('SELECT id FROM saved_review_filters WHERE user_id=? AND name=? AND query_text=? AND subject=? AND scope=?',[user['id'],name,query,subject,scope]).rows
                if not existing:
                    if int(db.query('SELECT COUNT(*) AS total FROM saved_review_filters WHERE user_id=?',[user['id']]).rows[0]['total'])>=20:raise HTTPException(409,'最多保存20个复习范围，请先移除不再使用的范围')
                    db.query('INSERT INTO saved_review_filters (id,user_id,name,query_text,subject,scope,created_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6))',[new_id(),user['id'],name,query,subject,scope])
        result=[]
        for row in db.query('SELECT * FROM saved_review_filters WHERE user_id=? ORDER BY created_at DESC,id DESC',[user['id']]).rows:
            result.append({**{k:row[k] for k in ['id','name','subject','scope']},'q':row['query_text']})
        return result
