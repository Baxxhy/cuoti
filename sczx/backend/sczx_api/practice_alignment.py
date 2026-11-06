import hashlib
import json
from .algorithm import compute
from .practice_context import source_version,equivalent
from .question_detail import query_array
from .retrieval import preparation
from .rows import row_json


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def current_preparation(db,question,mode):
    analyses=query_array(db,'problem_analyses','SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',question['id'])
    return preparation(db,question,analyses[0] if analyses else None,'practice',mode)


def aligned(db,source,prepared,candidates):
    rows=db.query('SELECT * FROM knowledge_points WHERE id=? AND subject=?',[prepared.get('target_knowledge_id',''),source['subject']]).rows
    if not rows:return []
    return compute({'operation':'practice_alignment','retrieval_source':source,'retrieval_target':row_json('knowledge_points',rows[0]),'retrieval_candidates':candidates}).get('checks',[])


def alignment_method(checks,question_id):
    return next((c.get('method','') for c in checks if c.get('id')==question_id and c.get('aligned') is True),'')


def admitted(checks,question_id):
    return any(c.get('id')==question_id and c.get('aligned') is True for c in checks)


def proof_context(db,source,prepared,candidate):
    cards=db.query('SELECT * FROM knowledge_points WHERE id=? AND subject=?',[prepared.get('target_knowledge_id'),source['subject']]).rows
    return {'policy':1,'source':source_version(db,source),'candidate':digest(candidate),'target':digest(row_json('knowledge_points',cards[0])) if cards else ''}


def proof_valid(db,source,prepared,candidate,trace):
    proof=trace.get('alignment_proof') or {}
    return proof.get('method') in ['symbolic_linear','qwen_grounded_concept'] and equivalent(proof.get('context'),proof_context(db,source,prepared,candidate))


def save_proof(db,source,prepared,candidate,trace,method):
    trace.update(alignment_proof={'method':method,'context':proof_context(db,source,prepared,candidate)},alignment_method=method)
