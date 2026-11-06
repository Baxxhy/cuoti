"""Snapshot-consistent question detail and archival, matching the original service."""
from fastapi import HTTPException

from .accounts import current_user, secret
from .database import Database
from .rows import row_json
from .security import media_url


def safe_counterfactual(value, diagnosis):
    if not isinstance(value, dict):
        return value
    if (value.get('verification_method') in ['qwen_proposal_sympy_check', 'reference_repair_sympy_check']
            and not value.get('validation_scope') and 'preserved_prefix' not in value):
        value.update(verification_method='legacy_reference_alignment', legacy_review_required=True)
        if value.get('root_cause_confirmed') is True:
            value.update(root_cause_confirmed=False, status='partial', confidence=.5,
                         conclusion='这是历史参考过程的修复建议，尚未经过当前规则核验，请结合原题核对。')
    if (diagnosis.get('user_confirmed') is True and value.get('status') != 'not_needed'
            and ('suspected_step' not in value or value['suspected_step'] != diagnosis.get('first_error_step'))):
        value.update(root_cause_confirmed=False, status='partial', stale_after_correction=True,
                     confidence=.5, verification_method='previous_diagnosis_evidence',
                     conclusion='你已调整出错步骤，原有修复建议需要重新核对。')
    return value


def asset_crop(assets):
    for asset in assets:
        if asset['kind'] != 'crop':
            continue
        try:
            box = asset['bbox']
            if not isinstance(box, list) or len(box) != 4:
                return None
            if any(isinstance(v, bool) or v is None for v in box):
                return None
            x, y, right, bottom = [float(v) for v in box]
            if not (x >= 0 and y >= 0 and right > x and bottom > y and right <= 1 and bottom <= 1):
                return None
            return [x, y, right - x, bottom - y]
        except (ValueError, TypeError):
            return None
    return None


def query_array(db, table, sql, item_id):
    return [row_json(table, row) for row in db.query(sql, [item_id]).rows]


async def read_question(request):
    question_id = request.path_params['question_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        with db.transaction():
            rows = db.query('SELECT * FROM questions WHERE id = ? AND user_id = ?', [question_id, user['id']]).rows
            if not rows:
                raise HTTPException(404, '内容不存在或无权访问')
            result = row_json('questions', rows[0])
            def related(table, suffix='', sql=None, item_id=question_id):
                return query_array(db, table, sql or f'SELECT * FROM {table} WHERE question_id = ?' + suffix, item_id)
            assets = related('question_assets')
            for asset in assets:
                asset['url'] = media_url('/' + asset['path'], secret())
            result['assets'] = assets
            for key, kind in [('question_figures', 'question_figure'), ('student_working_figures', 'student_working_figure'), ('teacher_annotation_regions', 'teacher_annotation_region')]:
                result[key] = [asset for asset in assets if asset['kind'] == kind]
            result['crop_box'] = asset_crop(assets)
            ocr = related('ocr_runs', ' ORDER BY created_at DESC')
            result['ocr_runs'] = ocr
            result['ocr'] = next((item for item in ocr if item['stream'] == 'qwen_crop'), ocr[0] if ocr else None)
            analyses = related('problem_analyses', ' LIMIT 1')
            analysis = analyses[0] if analyses else None
            result['analysis'] = analysis
            result['reference_steps'] = related('reference_steps', sql='SELECT * FROM reference_steps WHERE analysis_id = ? ORDER BY step_index', item_id=analysis['id']) if analysis else []
            diagnoses = related('diagnoses', ' ORDER BY created_at DESC,id DESC LIMIT 1')
            diagnosis = diagnoses[0] if diagnoses else None
            if diagnosis:
                evidence = related('diagnosis_evidence', sql="SELECT * FROM diagnosis_evidence WHERE diagnosis_id = ? ORDER BY COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(metadata_json,'$.index')) AS UNSIGNED),10000),created_at,id", item_id=diagnosis['id'])
                diagnosis['evidence'] = [item for item in evidence if item['kind'] == 'step_alignment']
                counterfactual, found = None, False
                for entry in evidence:
                    if entry['kind'] == 'counterfactual_validation' and not found:
                        counterfactual, found = entry['metadata_json'], True
                    if entry['kind'] == 'eced_assessment':
                        diagnosis['evidence_diagnosis'] = entry['metadata_json']
                diagnosis['counterfactual'] = safe_counterfactual(counterfactual, diagnosis)
            result['diagnosis'] = diagnosis
            result['student_steps'] = related('student_steps', sql='SELECT s.* FROM student_steps s WHERE s.work_id = (SELECT id FROM student_works WHERE question_id = ? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY s.step_index')
            result['teacher_marks'] = related('teacher_marks')
            jobs = related('processing_jobs', " AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running') ORDER BY created_at DESC LIMIT 1")
            result['processing_job'] = jobs[0] if jobs else None
            return result


async def archive_question(request):
    question_id = request.path_params['question_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        with db.transaction():
            rows = db.query('SELECT id FROM questions WHERE id = ? AND user_id = ? FOR UPDATE', [question_id, user['id']]).rows
            if not rows:
                raise HTTPException(404, '内容不存在或无权访问')
            db.query("UPDATE questions SET status = 'archived', updated_at = UTC_TIMESTAMP() WHERE id = ?", [question_id])
            db.query("UPDATE review_plans SET status = 'cancelled', updated_at = UTC_TIMESTAMP() WHERE question_id = ? AND status = 'pending'", [question_id])
    return {'deleted': True}
