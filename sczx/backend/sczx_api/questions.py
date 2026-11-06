"""Question list ported from question_list.cj, including display deduplication."""
import json
from pathlib import Path

from .accounts import current_user, secret
from .database import Database
from .rows import row_json
from .security import media_url

_TAXONOMY = json.loads((Path(__file__).resolve().parents[1] / 'schema/error_taxonomy.json').read_text())


def display_key(text, question_id):
    clean = ''.join(c for c in text if not c.isspace())
    return ''.join(c for c in clean if c not in '，。？?：:').lower() if clean else 'pending:' + question_id


async def list_questions(request):
    subject = request.query_params.get('subject', '')
    search = request.query_params.get('search', '')
    with Database.from_environment() as db:
        user = current_user(request, db)
        sql = "SELECT q.* FROM questions q WHERE q.user_id = ? AND q.status <> 'archived'"
        params = [user['id']]
        if subject:
            sql += ' AND q.subject = ?'
            params.append(subject)
        if search:
            sql += (' AND (q.question_text LIKE ? OR q.title LIKE ? OR CAST(q.knowledge_points AS CHAR) LIKE ?'
                    ' OR CAST(q.tags AS CHAR) LIKE ? OR EXISTS (SELECT 1 FROM diagnoses d WHERE d.question_id = q.id'
                    ' AND (d.root_misconception LIKE ? OR d.error_type LIKE ? OR d.first_error_text LIKE ?')
            params += ['%' + search + '%'] * 7
            codes = set()
            for code, label in _TAXONOMY:
                if (search in label or label in search) and code not in codes:
                    codes.add(code)
                    sql += ' OR d.error_type = ?'
                    params.append(code)
            sql += ')))'
        sql += ' ORDER BY q.created_at DESC'
        result, seen = [], set()
        with db.transaction():
            for row in db.query(sql, params).rows:
                question_id = row['id']
                key = display_key(row['question_text'] or '', question_id)
                if key in seen:
                    continue
                seen.add(key)
                item = row_json('questions', row)
                diagnosis = db.query('SELECT root_misconception FROM diagnoses WHERE question_id = ? ORDER BY created_at DESC LIMIT 1', [question_id]).rows
                item['diagnosis_summary'] = diagnosis[0]['root_misconception'] if diagnosis else '等待完成错因诊断'
                review = db.query("SELECT due_at FROM review_plans WHERE question_id = ? AND user_id = ? AND status = 'pending' ORDER BY due_at LIMIT 1", [question_id, user['id']]).rows
                item['review_due_at'] = row_json('review_plans', review[0])['due_at'] if review else None
                knowledge = json.loads(row['knowledge_points'] or 'null') or ['__none__']
                mastery = db.query('SELECT mastery_score FROM mastery_states WHERE user_id = ? AND subject = ? AND JSON_CONTAINS(?, JSON_QUOTE(knowledge_point)) ORDER BY updated_at DESC LIMIT 1', [user['id'], row['subject'], json.dumps(knowledge)]).rows
                score = float(mastery[0]['mastery_score']) if mastery else 0.0
                item['mastery_score'] = score
                item['mastery_status'] = '基本稳定' if score >= .75 else '继续巩固' if score >= .5 else '需要巩固'
                assets = db.query("SELECT path FROM question_assets WHERE question_id = ? AND kind IN ('crop','original') ORDER BY created_at DESC LIMIT 1", [question_id]).rows
                item['thumbnail_url'] = media_url('/' + assets[0]['path'], secret()) if assets else None
                jobs = db.query('SELECT id,status FROM processing_jobs WHERE question_id = ? ORDER BY created_at DESC LIMIT 1', [question_id]).rows
                item['latest_job_id'] = jobs[0]['id'] if jobs else None
                item['latest_job_status'] = jobs[0]['status'] if jobs else None
                result.append(item)
        return result
