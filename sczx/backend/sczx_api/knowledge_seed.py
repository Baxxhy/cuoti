"""Public knowledge initialization, matching the original Cangjie seed command."""
import json
from pathlib import Path
from .database import Database
from .security import new_id


def seed_public_knowledge():
    payload=json.loads((Path(__file__).resolve().parents[1]/'schema/knowledge_seed.json').read_text())
    with Database.from_environment() as db:
        with db.transaction():
            for card in payload['cards']:
                db.query('INSERT INTO knowledge_points (id,code,subject,name,content,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP()) ON DUPLICATE KEY UPDATE subject=VALUES(subject),name=VALUES(name),content=VALUES(content),updated_at=UTC_TIMESTAMP()', [new_id(),card['code'],card['subject'],card['name'],json.dumps(card['content'],ensure_ascii=False)])
            for relation in payload['relations']:
                db.query("INSERT INTO knowledge_relations (id,source_id,target_id,relation_type,created_at,updated_at) SELECT ?,s.id,t.id,'prerequisite',UTC_TIMESTAMP(),UTC_TIMESTAMP() FROM knowledge_points s JOIN knowledge_points t ON t.code=? WHERE s.code=? AND NOT EXISTS (SELECT 1 FROM knowledge_relations r WHERE r.source_id=s.id AND r.target_id=t.id AND r.relation_type='prerequisite')",[new_id(),relation['target'],relation['source']])
    return {'cards':len(payload['cards']),'relations':len(payload['relations'])}
