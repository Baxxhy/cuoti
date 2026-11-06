from .algorithm import compute
from .manual_questions import image_layout, answer_text
from .question_detail import query_array
from .rows import row_json


def retrieval_grade(grade, band):
    clean=grade.strip()
    for prefix,label in [('七年级','初一'),('八年级','初二'),('九年级','初三'),('初中','初中'),('高中','高中')]:
        if clean.startswith(prefix): return label
    return clean or band


def usable_candidate(source,candidate,kind):
    if image_layout(candidate)[0]: return False
    if source['subject']!=candidate['subject'] or not candidate['usable_for_practice'] or not candidate['has_answer'] or not answer_text(candidate['answer']).strip(): return False
    if kind=='practice' and not candidate['usable_for_auto_grade']: return False
    raw=source.get('grade') or ''; band='高中' if raw.startswith('高') else '初中'
    grade=retrieval_grade(candidate.get('grade') or '',candidate.get('grade_band') or '')
    return grade in [retrieval_grade(raw,band),band]


def preparation(db,question,analysis,kind,mode):
    diagnoses=query_array(db,'diagnoses','SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',question['id'])
    cards=query_array(db,'knowledge_points','SELECT * FROM knowledge_points WHERE subject=?',question['subject'])
    return compute({'operation':'retrieval_prepare','retrieval_source':question,'retrieval_analysis':analysis,'retrieval_kind':kind,'retrieval_mode':mode,'retrieval_diagnosis':diagnoses[0] if diagnoses else {},'retrieval_cards':cards})


def candidates(db,question,prepared,excluded,kind,mode):
    grade=question.get('grade') or ''
    hits=compute({'operation':'retrieval_search','retrieval_query':prepared['query'],'subject':question['subject'],'grade':grade,'grade_band':'高中' if grade.startswith('高') else '初中'}).get('hits',[])
    values=[]
    for hit in hits:
        rows=db.query('SELECT * FROM dataset_questions WHERE id=? AND subject=? AND usable_for_practice=1',[hit['id'],question['subject']]).rows
        if not rows: continue
        item=row_json('dataset_questions',rows[0])
        if not usable_candidate(question,item,kind): continue
        value={key:hit[key] for key in ['dense_rank','sparse_rank','fusion_rank','fusion_score']}; value['question']=item
        sources=db.query('SELECT `key` FROM dataset_sources WHERE id=?',[item['dataset_source_id']]).rows
        value['source_dataset']=sources[0]['key'] if sources else 'unknown'
        value['knowledge_points']=db.query('SELECT k.id,k.name,l.role FROM question_knowledge_links l JOIN knowledge_points k ON k.id=l.knowledge_point_id WHERE l.dataset_question_id=?',[hit['id']]).rows
        values.append(value)
    return compute({'operation':'retrieval_rank','retrieval_query':prepared['query'],'text':question['question_text'],'question_type':question['question_type'],'retrieval_candidates':values,'retrieval_excluded_ids':excluded,'retrieval_kind':kind,'retrieval_mode':mode})
