package zhiwei

import std.collection.*
import std.env.*
import std.convert.*
import stdx.encoding.json.*

// Deployment-only snapshots. No public HTTP route accepts dataset answers.
func questionBankImport(db: Database, body: JsonObject): JsonObject {
    let source=(body["source"] as JsonObject).getOrThrow()
    let key=schoolText(source,"key","",80,nonempty:true)
    if (key!="cmmu" && key!="cmm-math") { throw ApiError(422,"仅支持已配置的公开题源") }
    let rows=(body["questions"] as JsonArray).getOrThrow()
    if (rows.getItems().isEmpty() || rows.getItems().size>100) { throw ApiError(422,"每批需要1至100道题") }
    let seen=HashSet<String>()
    let strings=[("source_item_id",190),("split",30),("subject",30),("grade",30),("grade_band",30),("title",255),("question_text",200000),("question_type",60),("solution",200000),("difficulty",30),("content_hash",64),("quality_status",30)]
    for (value in rows.getItems()) {
        let item=(value as JsonObject).getOrThrow()
        for ((field,limit) in strings) { schoolText(item,field,"",limit,nonempty:field=="source_item_id" || field=="subject" || field=="question_text" || field=="content_hash") }
        let id=jsonText(item,"source_item_id")
        if (seen.contains(id)) { throw ApiError(422,"批次包含重复题目") }; seen.add(id)
        let hash=jsonText(item,"content_hash")
        if (hash.size!=64) { throw ApiError(422,"内容指纹无效") }
        for (byte in hash.toArray()) { if (!(byte>=48 && byte<=57 || byte>=97 && byte<=102)) { throw ApiError(422,"内容指纹无效") } }
        for (field in ["options","knowledge_points","image_paths","links"]) { if (!(item[field] is JsonArray)) { throw ApiError(422,"题目集合字段无效") } }
        if (!(item["source_metadata"] is JsonObject)) { throw ApiError(422,"题目来源无效") }
        for (field in ["has_answer","has_solution","answer_verified","usable_for_practice","usable_for_auto_grade"]) { editBool(item[field]) }
        if (tutorFlag(item,"usable_for_practice") && (!tutorFlag(item,"has_answer") || tutorText(item,"quality_status")!="usable")) { throw ApiError(422,"未通过质量检查的题目不能用于练习") }
        if (tutorFlag(item,"usable_for_auto_grade") && !tutorFlag(item,"usable_for_practice")) { throw ApiError(422,"判题资格无效") }
        for (path in tutorArray(item,"image_paths").getItems()) { if (!(path is JsonString) || (path as JsonString).getOrThrow().getValue().contains("..")) { throw ApiError(422,"题目图片路径无效") } }
    }
    let name=schoolText(source,"name","",160,nonempty:true); let version=schoolText(source,"version","",100,nonempty:true)
    let homepage=schoolText(source,"homepage","",500); let license=schoolText(source,"license","",100); let localPath=schoolText(source,"local_path","",500)
    return db.transaction<JsonObject>({ tx =>
        tx.query("INSERT INTO dataset_sources (id,`key`,name,version,homepage,license,local_path,total_items,imported_items,source_metadata,created_at,updated_at) VALUES (?,?,?,?,?,?,?,0,0,JSON_OBJECT(),UTC_TIMESTAMP(6),UTC_TIMESTAMP(6)) ON DUPLICATE KEY UPDATE name=VALUES(name),version=VALUES(version),homepage=VALUES(homepage),license=VALUES(license),local_path=VALUES(local_path)", [Some(newId()),Some(key),Some(name),Some(version),Some(homepage),Some(license),Some(localPath)])
        let sourceId=rowText(tx.query("SELECT id FROM dataset_sources WHERE `key`=? FOR UPDATE",[Some(key)]).rows[0],"id")
        for (value in rows.getItems()) {
            let item=(value as JsonObject).getOrThrow()
            let fields="source_item_id,split,subject,grade,grade_band,title,question_text,question_type,options,answer,solution,knowledge_points,image_paths,difficulty,content_hash,source_metadata,has_answer,has_solution,answer_verified,quality_status,usable_for_practice,usable_for_auto_grade"
            let names=fields.split(","); let params=ArrayList<Option<String>>(); params.add(Some(newId())); params.add(Some(sourceId))
            let marks=StringBuilder(); let updates=StringBuilder(); var first=true
            for (field in names) {
                params.add(if (field=="answer") { Some(item[field].toString()) } else { sqlValue(item[field]) }); if (!first) { marks.append(","); updates.append(",") }; first=false
                marks.append("?"); updates.append("${field}=VALUES(${field})")
            }
            let previous=tx.query("SELECT * FROM dataset_questions WHERE dataset_source_id=? AND source_item_id=?",[Some(sourceId),sqlValue(item["source_item_id"])]).rows
            var unchanged=!previous.isEmpty()
            if (unchanged) {
                let saved=rowJson("dataset_questions",previous[0])
                for (field in names) { if (!jsonEquivalent(saved[field],item[field])) { unchanged=false; break } }
            }
            // Dataset memory is versioned by the stored row, including updated_at.
            if (!unchanged) { tx.query("INSERT INTO dataset_questions (id,dataset_source_id,${fields},created_at,updated_at) VALUES (?,?,${marks.toString()},UTC_TIMESTAMP(6),UTC_TIMESTAMP(6)) ON DUPLICATE KEY UPDATE ${updates.toString()},updated_at=UTC_TIMESTAMP(6)",params.toArray()) }
            let id=rowText(tx.query("SELECT id FROM dataset_questions WHERE dataset_source_id=? AND source_item_id=?",[Some(sourceId),sqlValue(item["source_item_id"])]).rows[0],"id")
            tx.query("DELETE FROM question_knowledge_links WHERE dataset_question_id=?",[Some(id)])
            for (entry in tutorArray(item,"links").getItems()) {
                let link=(entry as JsonObject).getOrThrow(); let code=schoolText(link,"code","",100,nonempty:true)
                let cards=tx.query("SELECT id FROM knowledge_points WHERE code=? AND subject=?",[Some(code),sqlValue(item["subject"])]).rows
                if (cards.isEmpty()) { throw ApiError(422,"知识卡不存在或学科不匹配") }
                let role=schoolText(link,"role","",30,nonempty:true)
                if (role!="primary" && role!="secondary") { throw ApiError(422,"知识映射角色无效") }
                let confidence=Float64.parse(link["confidence"].toString()); let method=schoolText(link,"method","",50,nonempty:true)
                if (!(confidence>=0.0 && confidence<=1.0) || method!="offline_rules" && method!="subject_grade_fallback") { throw ApiError(422,"知识映射依据无效") }
                tx.query("INSERT INTO question_knowledge_links (id,dataset_question_id,knowledge_point_id,role,confidence,mapping_method,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(id),Some(rowText(cards[0],"id")),Some(role),Some(confidence.toString()),Some(method)])
            }
        }
        let count=rowText(tx.query("SELECT COUNT(*) AS count FROM dataset_questions WHERE dataset_source_id=?",[Some(sourceId)]).rows[0],"count")
        tx.query("UPDATE dataset_sources SET total_items=?,imported_items=?,last_imported_at=UTC_TIMESTAMP(6),updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(count),Some(count),Some(sourceId)])
        let result=JsonObject(); result.put("stored",JsonString(count)); result.put("source",JsonString(key)); return result
    })
}

func questionBankCommand(): Int64 {
    try {
        let raw=getStdIn().readln() ?? ""
        if (raw.isEmpty() || raw.size>16000000) { throw ApiError(422,"题库命令输入无效或过大") }
        let body=(JsonValue.fromStr(raw) as JsonObject).getOrThrow()
        if ((getVariable("CANGJIE_DB_NAME") ?? "").isEmpty()) { throw ApiError(422,"必须显式配置独立仓颉数据库") }
        try (db=Database.fromEnvironment()) {
            if (db.query("SELECT version FROM cangjie_schema_versions WHERE version='009_task_sources'").rows.size!=1) { throw ApiError(409,"请先初始化或升级仓颉数据库") }
            let operation=schoolText(body,"operation","",30,nonempty:true)
            if (operation=="import") { println(questionBankImport(db,body).toString()); return 0 }
            if (operation=="cards") {
                let output=JsonArray(); for (row in db.query("SELECT * FROM knowledge_points ORDER BY code").rows) { output.add(rowJson("knowledge_points",row)) }
                println(output.toString()); return 0
            }
            if (operation=="export") {
                let source=schoolText(body,"source","",80,nonempty:true); let after=schoolText(body,"after","",36)
                let rows=db.query("SELECT q.* FROM dataset_questions q JOIN dataset_sources s ON s.id=q.dataset_source_id WHERE s.`key`=? AND q.id>? AND q.usable_for_practice=1 ORDER BY q.id LIMIT 100",[Some(source),Some(after)]).rows
                let output=JsonArray(); for (row in rows) { output.add(rowJson("dataset_questions",row)) }
                println(output.toString()); return 0
            }
            throw ApiError(422,"未知题库操作")
        }
    } catch (error: ApiError) {
        let output=JsonObject(); output.put("code",JsonInt(Int64(error.status))); output.put("message",JsonString(error.message)); println(output.toString()); return 1
    } catch (_: Exception) { println(##"{"code":503,"message":"题库操作未完成，请检查输入及独立仓颉环境；当前批次未提交"}"##); return 1 }
    return 1
}
