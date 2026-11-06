import json

from fastapi import HTTPException

from .accounts import current_user, read_json
from .algorithm import compute
from .database import Database
from .rows import row_json
from .security import new_id
from .tutor_core import canonical_stage
from .tutor_start import record_tool
from .tutor_variants import data_snapshot, ensure_variant


def evaluate_teach_back(explanation, question, points, references):
    return compute({'operation': 'evaluate_teach_back', 'text': explanation,
                    'subject': question['subject'], 'question_type': question['question_type'],
                    'teach_back_points': points, 'reference_solution': references})


async def teach_back(request):
    session_id = request.path_params['session_id']
    with Database.from_environment() as db:
        user = current_user(request, db)
        body = await read_json(request)
        explanation = body.get('explanation', '')
        if not isinstance(explanation, str):
            raise HTTPException(422, 'explanation 必须是文字')
        if len(explanation) > 12000:
            raise HTTPException(422, 'explanation 长度不正确')
        with db.transaction():
            rows = db.query('SELECT * FROM tutor_sessions WHERE id=? AND user_id=? FOR UPDATE', [session_id, user['id']]).rows
            if not rows:
                raise HTTPException(404, '教学会话不存在或无权访问')
            session = row_json('tutor_sessions', rows[0])
            stage = canonical_stage(session['stage'])
            if stage != 'teach_back':
                raise HTTPException(409, '请先完成理解检查并进入讲清阶段')
            value = data_snapshot(db, session['question_id'], user['id'])
            question = value['question']
            state = session['state'] if isinstance(session['state'], dict) else {}
            session['state'] = state
            if state.get('question_changed') is True or question['status'] == 'archived':
                raise HTTPException(409, '题目已变化或归档，请重新开始学习')
            points = value['analysis']['knowledge_points'] if isinstance(value['analysis'], dict) else question['knowledge_points']
            assessment = evaluate_teach_back(explanation, question, points, [r['text'] for r in value['references']])
            passed = assessment.get('passed') is True
            count = state.get('teach_back_attempts', 0) + 1
            assisted = not passed and count >= 2
            branch = 'teach_back_pass' if passed else 'teach_back_fail'
            feedback = assessment['feedback']
            state.update(teach_back=passed, teach_back_passed=passed, teach_back_attempts=count, branch=branch,
                         next_goal='完成一道相似题' if passed or assisted else '补充一个关键理由')
            if assisted:
                state['assisted'] = True
            session['stage'] = stage
            if passed or assisted:
                session['stage'] = 'near_transfer'
                ensure_variant(db, session, value, 'near')
                if not passed:
                    feedback = '这次还少一个关键点，我先记录下来，我们继续练一道相似题。'
            db.query('UPDATE tutor_sessions SET stage=?,state=?,updated_at=UTC_TIMESTAMP() WHERE id=?',
                     [session['stage'], json.dumps(state, ensure_ascii=False), session_id])
            for role, content, turn_stage, metadata in [
                ('user', explanation, 'teach_back', {'branch': branch}),
                ('assistant', feedback, session['stage'], {'branch': branch, 'passed': passed}),
            ]:
                db.query('INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))',
                         [new_id(), session_id, role, content, turn_stage, json.dumps(metadata, ensure_ascii=False)])
            output = {'passed': passed, 'stage': session['stage'], 'matched_concepts': assessment['matched_concepts']}
            record_tool(db, session_id, 'evaluate_teach_back', {'explanation': explanation, 'subject': question['subject']}, output, {**output, 'branch': branch})
            return {'passed': passed, 'assisted': assisted, 'branch': branch, 'stage': session['stage'],
                    'feedback': feedback, 'next_goal': state['next_goal']}
