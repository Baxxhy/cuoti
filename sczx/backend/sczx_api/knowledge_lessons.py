import hashlib
import json
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from .accounts import current_user,read_json
from .algorithm import compute
from .database import Database
from .learning_evidence import digest
from .review_search import optional_text
from .rows import row_json
from .security import new_id


async def personal_framework(request):
    with Database.from_environment() as db:
        user=current_user(request,db);nodes=[];edges=[];ids={}
        counts={r['knowledge_point_id']:int(r['total']) for r in db.query("SELECT l.knowledge_point_id,COUNT(DISTINCT l.question_id) AS total FROM user_question_knowledge_links l JOIN questions q ON q.id=l.question_id AND q.user_id=l.user_id WHERE l.user_id=? AND q.status<>'archived' GROUP BY l.knowledge_point_id",[user['id']]).rows}
        mastery={}
        for row in db.query('SELECT * FROM mastery_states WHERE user_id=?',[user['id']]).rows:
            value=row_json('mastery_states',row);mastery[(value['subject'],value['knowledge_point'])]=value
        for row in db.query('SELECT * FROM knowledge_points ORDER BY subject,code').rows:
            card=row_json('knowledge_points',row);content=card['content'] if isinstance(card['content'],dict) else {};ids[card['id']]=card['code']
            nodes.append({**{k:card[k] for k in ['code','subject','name']},'grade':content.get('grade') if isinstance(content.get('grade'),str) else '','chapter':content.get('chapter') if isinstance(content.get('chapter'),str) else '','question_count':counts.get(card['id'],0),'mastery':mastery.get((card['subject'],card['name']))})
        for row in db.query("SELECT source_id,target_id FROM knowledge_relations WHERE relation_type='prerequisite' ORDER BY source_id,target_id").rows:
            if row['source_id'] in ids and row['target_id'] in ids:edges.append({'code':ids[row['source_id']],'prerequisite_code':ids[row['target_id']]})
        profiles=db.query('SELECT grade,preferences FROM student_profiles WHERE user_id=?',[user['id']]).rows;subject='数学';grade=''
        if profiles:
            grade=profiles[0]['grade'] or '';preferences=json.loads(profiles[0]['preferences']) if profiles[0]['preferences'] else {}
            if isinstance(preferences,dict) and isinstance(preferences.get('focus_subject'),str) and preferences['focus_subject']:subject=preferences['focus_subject']
        return {'nodes':nodes,'relations':edges,'default_subject':subject,'default_grade':grade}


def lesson_row(row):
    return {**{k:row[k] or '' for k in ['id','knowledge_code','prompt','created_at']},'result':json.loads(row['result'])}


def lesson_cards(db,code):
    rows=db.query('SELECT * FROM knowledge_points WHERE code=?',[code]).rows
    if not rows:raise HTTPException(404,'知识卡不存在')
    cards=[row_json('knowledge_points',rows[0])]
    for row in db.query("SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON k.id=r.target_id WHERE r.source_id=? AND r.relation_type='prerequisite' AND k.subject=? ORDER BY k.code LIMIT 3",[rows[0]['id'],rows[0]['subject']]).rows:
        card=row_json('knowledge_points',row);card.update(retrieval_role='prerequisite',anchor_code=code);cards.append(card)
    return cards


def source_version(cards):return digest([[card.get(k) for k in ['code','name','subject','content','retrieval_role','anchor_code']] for card in cards])


def prompt_hash(prompt):return hashlib.sha256(prompt.encode()).hexdigest()


def version_matches(record,cards,prompt):
    suffix=':'+prompt_hash(prompt)
    return record.get('input_fingerprint','') in [source_version(cards)+suffix,digest(cards)+suffix]


async def knowledge_lessons(request):
    code=request.path_params['code']
    with Database.from_environment() as db:
        user=current_user(request,db)
        if request.method=='GET':
            cards=lesson_cards(db,code);result=[]
            for row in db.query('SELECT * FROM knowledge_lessons WHERE user_id=? AND knowledge_code=? ORDER BY created_at DESC,id DESC LIMIT 10',[user['id'],code]).rows:
                item=lesson_row(row);item['source_current']=version_matches(row,cards,row['prompt']);result.append(item)
            return result
        body=await read_json(request);prompt=optional_text(body,'prompt',800).strip();request_id=optional_text(body,'request_id',80).strip()
        if not request_id:raise HTTPException(422,'缺少请求编号')
        cards=lesson_cards(db,code);source_hash=source_version(cards);fingerprint=source_hash+':'+prompt_hash(prompt)
        previous=db.query('SELECT * FROM knowledge_lessons WHERE user_id=? AND request_id=?',[user['id'],request_id]).rows
        if previous:
            if previous[0]['knowledge_code']!=code or not version_matches(previous[0],cards,prompt):raise HTTPException(409,'这次提问或知识内容已变化，请重新提问')
            return lesson_row(previous[0])
        anchor=cards[0];content=anchor['content'] if isinstance(anchor['content'],dict) else {}
        payload={'operation':'knowledge_lesson','subject':anchor['subject'],'grade':content.get('grade') if isinstance(content.get('grade'),str) else '','text':prompt,'dialogue_cards':cards}
        recent=db.query('SELECT prompt,result FROM knowledge_lessons WHERE user_id=? AND knowledge_code=? AND (input_fingerprint LIKE ? OR input_fingerprint LIKE ?) ORDER BY created_at DESC,id DESC LIMIT 3',[user['id'],code,source_hash+':%',digest(cards)+':%']).rows
        history=[]
        for row in reversed(recent):
            value=json.loads(row['result']);history.append({'question':row['prompt'],'explanation':value.get('explanation') if isinstance(value.get('explanation'),str) else '','check_question':value.get('check_question') if isinstance(value.get('check_question'),str) else ''})
        payload['knowledge_history']=history
        try:result=await run_in_threadpool(compute,payload,timeout=30)
        except HTTPException:raise HTTPException(503,'讲解暂时没有完成，请稍后重试。可以先查看知识卡中的公式和示例。') from None
        if result.get('can_update_learning') is not False:raise HTTPException(503,'讲解结果未通过检查')
        with db.transaction():
            latest=lesson_cards(db,code)
            if source_version(latest)!=source_hash:raise HTTPException(409,'知识内容刚刚更新，请重新提问')
            db.query('INSERT INTO knowledge_lessons (id,user_id,knowledge_code,request_id,input_fingerprint,prompt,result,created_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(6)) ON DUPLICATE KEY UPDATE id=id',[new_id(),user['id'],code,request_id,fingerprint,prompt,json.dumps(result,ensure_ascii=False)])
            saved=db.query('SELECT * FROM knowledge_lessons WHERE user_id=? AND request_id=?',[user['id'],request_id]).rows[0]
            if not version_matches(saved,latest,prompt) or saved['knowledge_code']!=code:raise HTTPException(409,'请求编号已用于其他提问')
            return lesson_row(saved)
