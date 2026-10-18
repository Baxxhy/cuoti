package zhiwei

import std.fs.*
import stdx.encoding.json.*

func seedPublicKnowledge(): Unit {
    let data=(JsonValue.fromStr(String.fromUtf8(File.readFrom("schema/knowledge_seed.json"))) as JsonObject).getOrThrow()
    try (db=Database.fromEnvironment()) {
        db.transaction<Unit>({ tx =>
            for (value in tutorArray(data,"cards").getItems()) {
                let card=(value as JsonObject).getOrThrow()
                tx.query("INSERT INTO knowledge_points (id,code,subject,name,content,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP()) ON DUPLICATE KEY UPDATE subject=VALUES(subject),name=VALUES(name),content=VALUES(content),updated_at=UTC_TIMESTAMP()",[Some(newId()),sqlValue(card["code"]),sqlValue(card["subject"]),sqlValue(card["name"]),Some(card["content"].toString())])
            }
            for (value in tutorArray(data,"relations").getItems()) {
                let relation=(value as JsonObject).getOrThrow()
                tx.query("INSERT INTO knowledge_relations (id,source_id,target_id,relation_type,created_at,updated_at) SELECT ?,s.id,t.id,'prerequisite',UTC_TIMESTAMP(),UTC_TIMESTAMP() FROM knowledge_points s JOIN knowledge_points t ON t.code=? WHERE s.code=? AND NOT EXISTS (SELECT 1 FROM knowledge_relations r WHERE r.source_id=s.id AND r.target_id=t.id AND r.relation_type='prerequisite')",[Some(newId()),sqlValue(relation["target"]),sqlValue(relation["source"])])
            }
            ()
        })
    }
}
