import json

from .rows import row_json
from .security import new_id
from .recognition import short_title


def label(text):
    text = text.translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))
    return ''.join(c for c in text if 'a' <= c <= 'z' or '0' <= c <= '9' or '\u4e00' <= c <= '\u9fff')


def sync_links(db, question, analysis, diagnosis=None):
    cards = [row_json('knowledge_points', row) for row in db.query('SELECT * FROM knowledge_points WHERE subject=? ORDER BY id', [question['subject']]).rows]
    selected = {}
    sources = [(question['knowledge_points'], 'primary'), (analysis['knowledge_points'], 'primary'), (analysis['prerequisites'], 'prerequisite')]
    if diagnosis: sources.append((diagnosis['missing_prerequisites'], 'prerequisite'))
    for phrases, role in sources:
        for phrase in phrases:
            needle = label(phrase)
            if len(needle) < 2: continue
            best_id, best_score, best_length = '', 0, -1
            for card in cards:
                aliases = card['content'].get('related_knowledge', []) if isinstance(card['content'], dict) else []
                names = [card['name'], card['code']] + [a if isinstance(a, str) else json.dumps(a, ensure_ascii=False) for a in aliases]
                score = 0
                for name in names:
                    normalized = label(name)
                    if normalized == needle: score = 1.; break
                    if len(normalized) >= 2 and (normalized in needle or needle in normalized): score = .86
                length = len(label(card['name']))
                if score > 0 and (score > best_score or score == best_score and length > best_length):
                    best_id, best_score, best_length = card['id'], score, length
            if not best_id: continue
            old = selected.get(best_id)
            if old and ((old['role'] == 'primary' and role == 'prerequisite') or (old['role'] == role and old['confidence'] >= best_score)): continue
            selected[best_id] = {'role': role, 'confidence': best_score, 'method': 'exact_label' if best_score == 1 else 'contained_label', 'evidence': short_title(phrase, 255)}
    for card_id, link in selected.items():
        db.query('INSERT INTO user_question_knowledge_links (id,user_id,question_id,knowledge_point_id,role,confidence,mapping_method,evidence_text,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP()) ON DUPLICATE KEY UPDATE role=VALUES(role),confidence=VALUES(confidence),mapping_method=VALUES(mapping_method),evidence_text=VALUES(evidence_text),updated_at=UTC_TIMESTAMP()', [new_id(), question['user_id'], question['id'], card_id, link['role'], link['confidence'], link['method'], link['evidence']])
