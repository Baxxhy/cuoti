import copy
import json
from fastapi import HTTPException
from .accounts import current_user,secret
from .algorithm import compute
from .database import Database
from .dataset_images import question_images,solution_images
from .handwriting import validate_handwriting
from .learning_evidence import apply_evidence,knowledge_point
from .manual_questions import answer_text
from .paper_validation import integer
from .practice_alignment import current_preparation,aligned,admitted,alignment_method,proof_valid,proof_context,save_proof
from .practice_context import source_version,source_fingerprint,served,equivalent
from .practice_generated import generate,attempt_generated
from .question_edit import flag
from .retrieval import candidates,usable_candidate
from .rows import row_json
from .security import new_id,media_url


def authorize(request):
    with Database.from_environment() as db:current_user(request,db)


def request_text(body,key,limit,nonempty=False):
    value=body.get(key,'')
    if not isinstance(value,str):raise HTTPException(422,f'{key} 必须是文字')
    if len(value)>limit or nonempty and not value.strip():raise HTTPException(422,f'{key} 长度不正确')
    return value


def mode(body):
    value=request_text(body,'mode',30)
    if value not in ['reinforce','variation']:raise HTTPException(422,'请选择有效的练习模式')
    return value


def payload(question,kind,trace,points):
    pictures=question_images(question)
    options=compute({'operation':'normalize_options','raw_options':question['options']}).get('options',[])
    for item,pictured in zip(options,pictures['options']):
        if pictured.get('image_urls'):item['image_urls']=pictured['image_urls']
    names=trace.get('knowledge_match') or [];name=answer_text(names[0]) if names else '关键方法'
    return {'question_id':question['id'],'subject':question['subject'],'grade':question['grade'],'question_type':question['question_type'],'stem':question['question_text'],'images':pictures['image_urls'],'options':options,'knowledge_points':points,'recommendation':f'这道题会继续检查你需要加强的{name}。','mode':kind}


def refresh(question,receipt):
    return {**receipt,**solution_images(question)}


def recommend(request,body):
    with Database.from_environment() as db:
        owner=current_user(request,db)['id'];qid=request_text(body,'mistake_id',100,True);kind=mode(body);debug=flag(body.get('debug',False));force=flag(body.get('force_new',False))
        with db.transaction():
            rows=db.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived'",[qid,owner]).rows
            if not rows:raise HTTPException(404,'没有找到这道错题')
            question=row_json('questions',rows[0]);fingerprint=source_fingerprint(db,question);version=source_version(db,question);generated=False;cached=None
            old=db.query("SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE s.user_id=? AND v.question_id=? AND s.stage='standalone_practice' AND v.verified=1 ORDER BY v.created_at DESC LIMIT 20",[owner,qid]).rows
            for row in old:
                meta=row_json('variant_questions',row)['generation_metadata'] or {}
                if meta.get('mode')==kind and meta.get('source_version')==version:generated=True;break
            prepared={}
            if not generated:
                try:prepared=current_preparation(db,question,kind)
                except HTTPException:pass
                if not force:
                    previous=db.query('SELECT * FROM practice_recommendations WHERE user_id=? AND mistake_id=? AND mode=? ORDER BY created_at DESC LIMIT 1',[owner,qid,kind]).rows
                    if previous:
                        saved=row_json('practice_recommendations',previous[0]);trace=saved['retrieval_trace'] or {};selected_id=saved['dataset_question_id']
                        attempts=db.query('SELECT * FROM dataset_practice_attempts WHERE user_id=? AND mistake_id=? AND dataset_question_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1',[owner,qid,selected_id,kind]).rows
                        selected_rows=db.query('SELECT * FROM dataset_questions WHERE id=?',[selected_id]).rows
                        if trace.get('source_question_fingerprint')==fingerprint and trace.get('target_knowledge_id','')==prepared.get('target_knowledge_id','') and selected_rows:
                            selected=row_json('dataset_questions',selected_rows[0])
                            if usable_candidate(question,selected,'practice'):
                                valid=proof_valid(db,question,prepared,selected,trace)
                                if not valid:
                                    checks=aligned(db,question,prepared,[{'question':selected}]);valid=admitted(checks,selected_id)
                                    if valid:
                                        save_proof(db,question,prepared,selected,trace,alignment_method(checks,selected_id));db.query('UPDATE practice_recommendations SET retrieval_trace=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?',[json.dumps(trace,ensure_ascii=False),saved['id']])
                                if valid and attempts:
                                    details=row_json('dataset_practice_attempts',attempts[0])['grading_details'] or {}
                                    valid=bool(details.get('practice_receipt')) and equivalent((details.get('alignment_proof') or {}).get('context'),proof_context(db,question,prepared,selected))
                                if valid:
                                    cached=payload(selected,kind,trace,selected['knowledge_points'])
                                    if attempts:
                                        record=row_json('dataset_practice_attempts',attempts[0]);receipt=(record['grading_details'] or {}).get('practice_receipt') or {}
                                        if receipt:cached.update(previous_result=refresh(selected,receipt),previous_answer=record['student_answer'])
                                    if debug:cached['debug']=trace
        if cached is not None:return cached
        if generated:return generate(db,owner,question,kind,force)
        excluded=[]
        for table in ['dataset_practice_attempts','practice_recommendations']:
            for row in db.query('SELECT dataset_question_id FROM '+table+' WHERE user_id=? AND mistake_id=?',[owner,qid]).rows:
                if row['dataset_question_id'] not in excluded:excluded.append(row['dataset_question_id'])
        if not prepared.get('target_knowledge_id'):return generate(db,owner,question,kind,force)
        try:
            ranked=candidates(db,question,prepared,excluded,'practice',kind).get('ranked',[]);checks=aligned(db,question,prepared,ranked)
        except HTTPException:return generate(db,owner,question,kind,force)
        allowed=[c for c in ranked if admitted(checks,c['question']['id'])]
        if not allowed:return generate(db,owner,question,kind,force)
        with db.transaction():
            rows=db.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived' FOR UPDATE",[qid,owner]).rows
            if not rows or source_fingerprint(db,row_json('questions',rows[0]))!=fingerprint:raise HTTPException(409,'题目已修改，请重新获取推荐题')
            current=row_json('questions',rows[0])
            if source_version(db,current)!=version:raise HTTPException(409,'题目分析或诊断已更新，请重新获取练习')
            candidate=allowed[0];selected=candidate['question'];selected_id=selected['id']
            if current_preparation(db,current,kind).get('target_knowledge_id','')!=prepared['target_knowledge_id']:raise HTTPException(409,'学习目标已更新，请重新获取练习')
            fresh=db.query('SELECT * FROM dataset_questions WHERE id=? AND subject=? AND usable_for_practice=1',[selected_id,question['subject']]).rows
            if not fresh or not usable_candidate(question,row_json('dataset_questions',fresh[0]),'practice') or not equivalent(row_json('dataset_questions',fresh[0]),selected):raise HTTPException(409,'推荐题已更新，请重新获取')
            for table in ['practice_recommendations','dataset_practice_attempts']:
                if db.query('SELECT id FROM '+table+' WHERE user_id=? AND mistake_id=? AND dataset_question_id=? LIMIT 1',[owner,qid,selected_id]).rows:raise HTTPException(409,'推荐已变化，请重新获取练习题')
            trace={'source_question_fingerprint':fingerprint,'alignment_method':alignment_method(checks,selected_id)}
            trace.update({k:prepared[k] for k in ['knowledge_match','target_knowledge_id','target_knowledge_name','target_skill','error_match']})
            trace.update(difficulty_match=selected.get('difficulty') or '同年级',question_type_difference=selected['question_type']!=question['question_type'])
            trace.update({k:candidate[k] for k in ['dense_rank','sparse_rank','fusion_rank']});trace.update({k:(candidate.get('score_trace') or {}).get(k) for k in ['structure_similarity','reranker_score','mode_score']})
            save_proof(db,question,prepared,selected,trace,alignment_method(checks,selected_id))
            db.query('INSERT INTO practice_recommendations (id,user_id,mistake_id,dataset_question_id,mode,retrieval_rank,retrieval_trace,created_at,updated_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))',[new_id(),owner,qid,selected_id,kind,candidate['fusion_rank'],json.dumps(trace,ensure_ascii=False)])
            result=payload(selected,kind,trace,candidate['knowledge_points'])
            if debug:result['debug']=trace
            return result


def attempt(request,body):
    with Database.from_environment() as db:
        owner=current_user(request,db)['id'];mistake_id=request_text(body,'mistake_id',100);qid=request_text(body,'question_id',100);kind=mode(body)
        if 'student_answer' not in body:raise HTTPException(422,'请提交作答')
        answer=body['student_answer'];duration=integer(body.get('duration_seconds',0),0,7200)
        with db.transaction():
            rows=db.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived' FOR UPDATE",[mistake_id,owner]).rows
            if not rows:raise HTTPException(404,'没有找到这道错题')
            mistake=row_json('questions',rows[0])
            generated=db.query("SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND v.question_id=? AND s.user_id=? AND s.stage='standalone_practice' FOR UPDATE",[qid,mistake_id,owner]).rows
            if generated:
                validate_handwriting(body,owner,qid,'practice');return attempt_generated(db,owner,mistake,row_json('variant_questions',generated[0]),kind,answer,duration)
            questions=db.query('SELECT * FROM dataset_questions WHERE id=? FOR UPDATE',[qid]).rows
            if not questions or questions[0]['usable_for_auto_grade']!='1':raise HTTPException(422,'这道题不能自动判分')
            question=row_json('dataset_questions',questions[0])
            existing=db.query('SELECT * FROM dataset_practice_attempts WHERE user_id=? AND mistake_id=? AND dataset_question_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1 FOR UPDATE',[owner,mistake_id,qid,kind]).rows
            if existing:
                served(db,owner,mistake,qid,kind);record=row_json('dataset_practice_attempts',existing[0]);details=record['grading_details'] or {};receipt=details.get('practice_receipt') or {}
                context=proof_context(db,mistake,current_preparation(db,mistake,kind),question)
                if equivalent((details.get('alignment_proof') or {}).get('context'),context) and equivalent(record['student_answer'],answer) and receipt:return refresh(question,receipt)
                raise HTTPException(409,'这道练习已经完成，请换一道题继续练习')
            handwriting=validate_handwriting(body,owner,qid,'practice');record=served(db,owner,mistake,qid,kind);trace=record['retrieval_trace'] or {};seen=trace.get('answer_revealed') is True;prepared=current_preparation(db,mistake,kind)
            if not usable_candidate(mistake,question,'practice') or not trace.get('target_knowledge_id') or trace['target_knowledge_id']!=prepared.get('target_knowledge_id',''):raise HTTPException(409,'学习目标或题目资格已变化，请重新获取练习')
            if not proof_valid(db,mistake,prepared,question,trace):
                checks=aligned(db,mistake,prepared,[{'question':question}])
                if not admitted(checks,qid):raise HTTPException(409,'这道练习与当前学习目标不匹配，请重新获取练习；本次未更新学习记录')
                save_proof(db,mistake,prepared,question,trace,alignment_method(checks,qid))
            grading=compute({'operation':'grade_answer','text':question['question_text'],'answer':answer,'expected':question['answer'],'subject':question['subject'],'question_type':question['question_type'],'options':question['options'],'reference_solution':[line.strip() for line in question['solution'].split('\n') if line.strip()]})
            decisive=grading.get('can_update_learning') is True
            db.query("UPDATE practice_recommendations SET retrieval_trace=JSON_SET(retrieval_trace,'$.answer_revealed',true),updated_at=UTC_TIMESTAMP(6) WHERE id=?",[record['id']])
            cards=db.query('SELECT * FROM knowledge_points WHERE id=? AND subject=? FOR UPDATE',[trace['target_knowledge_id'],mistake['subject']]).rows
            if not cards or cards[0]['name']!=prepared.get('target_knowledge_name',''):raise HTTPException(409,'练习知识点已变化，请重新获取练习')
            card=row_json('knowledge_points',cards[0]);preferred=card['name'];point=knowledge_point(db,mistake,preferred,False)
            old=db.query('SELECT mastery_score FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? LIMIT 1',[owner,mistake['subject'].strip(),point]).rows
            before=row_json('mastery_states',old[0])['mastery_score'] if old else 0.;mastery=None;aid=''
            if decisive:
                sources=db.query('SELECT `key` FROM dataset_sources WHERE id=?',[question['dataset_source_id']]).rows
                details=copy.deepcopy(grading);details.update(independent_answer=not seen,handwriting_image_url=media_url(handwriting['image_url'],secret()),handwriting_recognition=handwriting['recognition'],alignment_method=trace['alignment_proof']['method'],target_knowledge_name=prepared['target_knowledge_name'],alignment_proof=trace['alignment_proof'])
                aid=new_id();db.query('INSERT INTO dataset_practice_attempts (id,user_id,mistake_id,dataset_question_id,source_dataset,knowledge_id,mode,student_answer,correct,duration_seconds,grading_details,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[aid,owner,mistake_id,qid,sources[0]['key'] if sources else 'unknown',card['id'],kind,json.dumps(answer,ensure_ascii=False),int(grading['correct']),duration,json.dumps(details,ensure_ascii=False)])
                evidence={'near_transfer' if kind=='reinforce' else 'far_transfer':grading['correct'],'hint_level':0,'strategy':'independent_dataset_practice','dataset_question_id':qid,'practice_attempt_id':aid}
                if not seen:mastery=(apply_evidence(db,owner,mistake,evidence,preferred,False).get('mastery_after') or {}).get('mastery_score')
            result={k:grading[k] for k in ['verdict','can_update_learning','confidence','evidence','feedback']}
            result.update(correct=grading['correct'] if decisive else None,answer=question['answer'],solution=question['solution'],**solution_images(question),mastery_before=before,mastery=mastery,grading_method=grading['method'])
            if seen:result['learning_note']='已看过参考答案，这次练习不重复计入掌握情况。'
            if aid:db.query("UPDATE dataset_practice_attempts SET grading_details=JSON_SET(grading_details,'$.practice_receipt',JSON_EXTRACT(?,'$')) WHERE id=?",[json.dumps(result,ensure_ascii=False),aid])
            return result
