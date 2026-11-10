"""Retry uses the original actor and current business source authority."""
from fastapi import HTTPException
from .models import Account,StudentRecord,LearningTask,SourceMaterial,TeachingCase,MaterialUnit

def validate_retry(db,job):
    from .model_jobs import require_job_write
    from .model_provider import ModelError
    try:require_job_write(db,job)
    except ModelError as e:raise HTTPException(409,str(e)) from None
    owner=db.get(Account,job.owner_id)
    if not owner or not owner.active:raise HTTPException(409,'提交账号已停用。')
    data=job.input or {}
    if job.capability=='lesson_agent':
        from .curriculum import published_lesson
        latest=published_lesson(db,data.get('lessonId'))
        if not latest or latest.get('versionId')!=(data.get('lesson') or {}).get('versionId'):raise HTTPException(409,'课时来源已失效或修订，请使用当前版本重新生成。')
    for key in ('caseId',):
        if data.get(key):
            row=db.get(TeachingCase,data[key])
            if not row or row.status!='published':raise HTTPException(409,'案例来源已撤回。')
    if data.get('materialId') and not db.get(SourceMaterial,data['materialId']):raise HTTPException(409,'原资料已不存在。')
    if data.get('unitId') and not db.get(MaterialUnit,data['unitId']):raise HTTPException(409,'原文片段已不存在。')
    for unit in data.get('units',[]):
        row=db.get(MaterialUnit,unit.get('id'))
        if not row or row.text!=unit.get('text'):raise HTTPException(409,'原文已修订，请基于当前片段重新整理。')
    if job.capability=='lesson_agent':
        from .library import current_case
        for ref in data.get('selectedReferences',[]):
            current=current_case(db,ref['id'])
            if not current or current['versionId']!=ref['versionId']:raise HTTPException(409,'参考案例已修订或撤回，请重新选择。')
    if job.record_id:
        rec=db.get(StudentRecord,job.record_id);task=db.get(LearningTask,rec.task_id) if rec else None
        if not task or (owner.role=='teacher' and task.teacher_id!=owner.id):raise HTTPException(409,'任务业务权限已失效。')
