import json

from fastapi import HTTPException

from .accounts import current_user
from .algorithm import compute
from .analysis import snapshot, fingerprint, images, analyze_question
from .database import Database
from .knowledge_links import label, sync_links
from .question_detail import query_array, read_question
from .rows import row_json
from .security import new_id


def knowledge_cards(db, query, subject, grade):
    available = [row_json('knowledge_points', r) for r in db.query('SELECT * FROM knowledge_points WHERE subject=? ORDER BY code LIMIT 200', [subject]).rows]
    def score(card):
        content = card['content'] if isinstance(card['content'], dict) else {}
        if grade.startswith('初') and content.get('grade', '').startswith('高'): return 0
        text, value = label(query), 0
        for name in [card['name'], card['code']]:
            key = label(name)
            if len(key) >= 2 and key in text: value = 100 + len(key)
        for alias in content.get('related_knowledge', []):
            if isinstance(alias, str):
                key = label(alias)
                if len(key) >= 2 and key in text and value == 0: value = len(key)
        return value
    ranked = sorted(available, key=score, reverse=True)
    anchors = [c for c in ranked if score(c) > 0][:3]
    result = [{**c, 'retrieval_role': 'anchor'} for c in anchors]
    seen = {c['code'] for c in anchors}
    for anchor in anchors:
        for row in db.query("SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON r.target_id=k.id WHERE r.source_id=? AND r.relation_type='prerequisite' AND k.subject=? ORDER BY k.code LIMIT 2", [anchor['id'], subject]).rows:
            card = row_json('knowledge_points', row)
            if len(result) >= 8 or card['code'] in seen: continue
            result.append({**card, 'retrieval_role': 'prerequisite', 'anchor_code': anchor['code']}); seen.add(card['code'])
    return result


def diagnosis_snapshot(db, question_id, owner):
    result = snapshot(db, question_id, owner)
    result['references'] = query_array(db, 'reference_steps', 'SELECT r.* FROM reference_steps r JOIN problem_analyses a ON r.analysis_id=a.id WHERE a.question_id=? ORDER BY r.step_index,r.id', question_id)
    diagnoses = query_array(db, 'diagnoses', 'SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1', question_id)
    result['diagnosis'] = diagnoses[0] if diagnoses else None
    question = result['question']
    result['diagnostic_cards'] = knowledge_cards(db, question['question_text'], question['subject'], question['grade'] or '')
    return result


def diagnosis_fingerprint(value):
    return fingerprint(value) + [value['references'], value['diagnosis']] + ([value['diagnostic_cards']] if 'diagnostic_cards' in value else [])


def diagnosis_input(value, include_images=True):
    question = value['question']
    result = {'operation': 'diagnose', 'text': question['question_text'], 'diagnostic_cards': value.get('diagnostic_cards', []), 'grade': question['grade'] or '', 'images_base64': images(value) if include_images else []}
    result.update({key: question[key] for key in ['subject', 'question_type', 'student_answer', 'options']})
    for source, target in [('references', 'reference_steps'), ('steps', 'student_records')]:
        result[target] = [{key: row[key] for key in ['id', 'text']} for row in value[source]]
    return result


def sql_value(value):
    if isinstance(value, (list, dict)): return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool): return int(value)
    return value


def insert_evidence(db, diagnosis_id, kind, content, entry, metadata):
    values = [new_id(), diagnosis_id, kind, content] + [sql_value(entry[k]) for k in ['reference_step_id', 'student_step_id', 'alignment', 'equivalent', 'uses_condition', 'is_first_error', 'propagated', 'math_valid']] + [json.dumps(metadata, ensure_ascii=False)]
    db.query('INSERT INTO diagnosis_evidence (id,diagnosis_id,kind,content,reference_step_id,student_step_id,alignment,equivalent,uses_condition,is_first_error,propagated,math_valid,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))', values)


def save_evidence(db, diagnosis_id, value, computed, include_alignment=True):
    refs, steps = {r['id'] for r in value['references']}, {r['id'] for r in value['steps']}
    counter = computed['counterfactual']; suspected = counter.get('suspected_step'); first = None
    for entry in computed['alignment']:
        for key, allowed in [('reference_step_id', refs), ('student_step_id', steps)]:
            if isinstance(entry[key], str) and entry[key] not in allowed: raise HTTPException(503, '诊断证据不属于当前作答')
        if include_alignment: insert_evidence(db, diagnosis_id, 'step_alignment', entry['reference_text'] + ' ⇄ ' + entry['student_text'], entry, entry)
        if suspected is not None and entry['index'] == suspected: first = entry
    record = {'reference_step_id': first['reference_step_id'] if first else None, 'student_step_id': first['student_step_id'] if first else None, 'alignment': counter['status'], 'equivalent': counter['root_cause_confirmed'], 'uses_condition': bool(first and first['reference_step_id'] is not None), 'is_first_error': suspected is not None, 'propagated': float(counter.get('recovered_steps', 0)) > 0, 'math_valid': counter['root_cause_confirmed']}
    insert_evidence(db, diagnosis_id, 'counterfactual_validation', counter['conclusion'], record, counter)
    assessment = computed.get('evidence_diagnosis') or {}
    if assessment.get('algorithm'):
        entry = {'reference_step_id': None, 'student_step_id': None, 'alignment': 'evidence_assessment', 'equivalent': False, 'uses_condition': False, 'is_first_error': False, 'propagated': False, 'math_valid': assessment.get('verified') is True}
        insert_evidence(db, diagnosis_id, 'eced_assessment', assessment.get('reason', ''), entry, assessment)


async def diagnose_question(request):
    question_id = request.path_params['question_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        with db.transaction(): initial = diagnosis_snapshot(db, question_id, user['id'])
        if initial['analysis'] is None: await analyze_question(request)
        with db.transaction(): value = diagnosis_snapshot(db, question_id, user['id'])
        if value['analysis'] is None: raise HTTPException(409, '题目分析已变化，请重新诊断')
        computed = compute(diagnosis_input(value)); diagnosis = computed['diagnosis']
        with db.transaction():
            current = diagnosis_snapshot(db, question_id, user['id'])
            if diagnosis_fingerprint(value) != diagnosis_fingerprint(current): raise HTTPException(409, '题目、作答或分析已变化，请重新诊断')
            diagnosis_id = new_id()
            keys = ['first_error_step', 'first_error_text', 'error_type', 'root_misconception', 'propagated_errors', 'strategy_candidates', 'confidence', 'error_location', 'missing_prerequisites', 'recommended_strategy']
            db.query('INSERT INTO diagnoses (id,question_id,first_error_step,first_error_text,error_type,root_misconception,propagated_errors,strategy_candidates,confidence,error_location,missing_prerequisites,recommended_strategy,user_confirmed,correction,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,JSON_OBJECT(),UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))', [diagnosis_id, question_id] + [sql_value(diagnosis[k]) for k in keys])
            save_evidence(db, diagnosis_id, value, computed)
            sync_links(db, value['question'], value['analysis'], diagnosis)
            db.query("UPDATE questions SET status='diagnosed',updated_at=UTC_TIMESTAMP() WHERE id=?", [question_id])
            result = row_json('diagnoses', db.query('SELECT * FROM diagnoses WHERE id=?', [diagnosis_id]).rows[0])
            result.update(evidence=computed['alignment'], counterfactual=computed['counterfactual'], evidence_diagnosis=computed.get('evidence_diagnosis'))
            return result


async def get_diagnosis(request):
    return (await read_question(request))['diagnosis']
