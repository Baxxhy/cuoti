"""材料与案例共享的持久化操作。"""
import hashlib
import json
import uuid
from sqlalchemy import select
from .models import CaseDraftContent, CaseVersion, MaterialUnit, ModelJob, SourceMaterial, TeachingCase


def uid(prefix): return prefix + '-' + uuid.uuid4().hex[:min(32,39-len(prefix))]


def enqueue(db, owner, capability, data, file_id=None):
    digest = hashlib.sha256(json.dumps([capability, data, file_id], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(select(ModelJob).where(ModelJob.owner_id == owner, ModelJob.active_hash == digest))
    if existing: return existing
    item = ModelJob(id=uid('job'), owner_id=owner, capability=capability, request_key=uid('library'), input_hash=digest, active_hash=digest, input=data, file_id=file_id)
    db.add(item); db.flush()
    from .model_jobs import event
    event(db, item, '排队中')
    return item


def latest_version(db, case_id):
    return db.scalar(select(CaseVersion).where(CaseVersion.case_id == case_id).order_by(CaseVersion.number.desc()).limit(1))


def version_json(version):
    return {**version.data, 'id': version.case_id, 'versionId': version.id, 'version': version.number, 'publishedAt': version.published_at.isoformat(timespec='seconds') + 'Z'}


def current_case(db, case_id, version_id=None):
    case = db.get(TeachingCase, case_id)
    version = db.get(CaseVersion, version_id) if version_id else latest_version(db, case_id)
    if not case or not version or version.case_id != case_id: return None
    if not version_id and case.status != 'published': return None
    return version_json(version)


def reference(db, unit, quote=None):
    material = db.get(SourceMaterial, unit.material_id)
    return {'unitId': unit.id, 'materialId': material.id, 'materialTitle': material.title, 'label': unit.label, 'quote': quote if quote is not None else unit.text[:1000], 'source': material.metadata_json.get('sourceNote', ''), 'sourceUrl': material.metadata_json.get('sourceUrl', ''), 'author': material.metadata_json.get('author', '')}


def create_draft(db, data):
    case = TeachingCase(id=uid('case'), title=data.get('title') or '未命名案例', content='', source=data.get('source', ''), status='draft')
    db.add(case); db.flush()
    draft = CaseDraftContent(case_id=case.id, data=data, reviewed=False)
    db.add(draft); db.flush()
    return draft


def published_unit(db, unit_id):
    # 已经发布过的不可变版本始终可解释；撤回只停止新检索。
    for version in db.scalars(select(CaseVersion)).all():
        if any(r.get('unitId') == unit_id for r in version.data.get('references', [])): return True
    return False


def validate_references(db, references):
    for item in references:
        unit = db.get(MaterialUnit, item.get('unitId', ''))
        quote = str(item.get('quote', '')).strip()
        normalize = lambda value: ''.join(value.split())
        if not unit or not quote or not any(normalize(quote) in normalize(value) for value in (unit.text, unit.original_text, *[r['text'] for r in unit.details.get('revisions',[])])):
            raise ValueError('请重新核对原文摘录与所选材料位置。')


def draft_json(db, case):
    draft = db.get(CaseDraftContent, case.id)
    versions = db.scalars(select(CaseVersion).where(CaseVersion.case_id == case.id).order_by(CaseVersion.number.desc())).all()
    return {'id': case.id, 'status': case.status, 'draft': {**draft.data, 'reviewed': draft.reviewed, 'updatedAt': draft.updated_at.isoformat()+'Z'} if draft else None, 'versions': [{'id': v.id, 'number': v.number, 'publishedAt': v.published_at.isoformat()+'Z'} for v in versions], 'published': version_json(versions[0]) if versions else None}


def validate_knowledge(db, data):
    from .models import KnowledgePoint
    ids=data.get('knowledgeIds',[])
    if not isinstance(ids,list) or len(ids)>16 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise ValueError('请选择不重复的有效知识点。')
    if any(not db.get(KnowledgePoint,ident) for ident in ids):raise ValueError('所选知识点不存在。')
