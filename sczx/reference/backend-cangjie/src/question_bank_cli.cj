package zhiwei

import std.collection.*
import std.env.*
import std.convert.*
import stdx.encoding.json.*

// Deployment-only snapshots. No public HTTP route accepts dataset answers.
func questionBankImport(db: Database, body: JsonObject): JsonObject {
    let source=(body["source"] as JsonObject).getOrThrow()
    let key=optionalText(source,"key","",80,nonempty:true)
    if (key!="cmmu" && key!="cmm-math" && key!="gaokao" && key!="race" && key!="tal") { throw ApiError(422,"仅支持已配置的公开题源") }
    let rows=(body["questions"] as JsonArray).getOrThrow()
    if (rows.getItems().isEmpty() || rows.getItems().size>500) { throw ApiError(422,"每批需要1至500道题") }
    let seen=HashSet<String>()
    let strings=[("source_item_id",190),("split",30),("subject",30),("grade",30),("grade_band",30),("title",255),("question_text",200000),("question_type",60),("solution",200000),("difficulty",30),("content_hash",64),("quality_status",30)]
    for (value in rows.getItems()) {
        let item=(value as JsonObject).getOrThrow()
        for ((field,limit) in strings) { optionalText(item,field,"",limit,nonempty:field=="source_item_id" || field=="subject" || field=="question_text" || field=="content_hash") }
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
    let name=optionalText(source,"name","",160,nonempty:true); let version=optionalText(source,"version","",100,nonempty:true)
    let homepage=optionalText(source,"homepage","",500); let license=optionalText(source,"license","",100); let localPath=optionalText(source,"local_path","",500)
    return db.transaction<JsonObject>({ tx =>
        tx.query("INSERT INTO dataset_sources (id,`key`,name,version,homepage,license,local_path,total_items,imported_items,source_metadata,created_at,updated_at) VALUES (?,?,?,?,?,?,?,0,0,JSON_OBJECT(),UTC_TIMESTAMP(6),UTC_TIMESTAMP(6)) ON DUPLICATE KEY UPDATE name=VALUES(name),version=VALUES(version),homepage=VALUES(homepage),license=VALUES(license),local_path=VALUES(local_path)", [Some(newId()),Some(key),Some(name),Some(version),Some(homepage),Some(license),Some(localPath)])
        let sourceId=rowText(tx.query("SELECT id FROM dataset_sources WHERE `key`=? FOR UPDATE",[Some(key)]).rows[0],"id")
        for (value in rows.getItems()) {
            let item=(value as JsonObject).getOrThrow()
            let previous=tx.query("SELECT * FROM dataset_questions WHERE dataset_source_id=? AND source_item_id=?",[Some(sourceId),sqlValue(item["source_item_id"])]).rows
            if (!previous.isEmpty()) {
                let saved=rowJson("dataset_questions",previous[0])
                // Re-importing the same source cannot silently re-enable a
                // quarantined question or discard its review evidence.
                let savedMetadata=tutorObject(saved,"source_metadata"); let review=tutorObject(savedMetadata,"format_review")
                let history=tutorArray(savedMetadata,"format_review_history")
                if (jsonText(saved,"content_hash")!=jsonText(item,"content_hash") && !tutorArray(review,"fields").getItems().isEmpty()) {
                    var recorded=false
                    for (entry in history.getItems()) { if (jsonText((entry as JsonObject).getOrThrow(),"content_hash")==jsonText(review,"content_hash")) { recorded=true } }
                    if (!recorded) { history.add(review) }
                }
                if (!history.getItems().isEmpty()) { let metadata=tutorObject(item,"source_metadata"); metadata.put("format_review_history",history); item.put("source_metadata",metadata) }
                if (jsonText(saved,"content_hash")==jsonText(item,"content_hash") && !tutorArray(review,"fields").getItems().isEmpty()) {
                    let metadata=tutorObject(item,"source_metadata"); metadata.put("format_review",review); item.put("source_metadata",metadata)
                    item.put("quality_status",JsonString("format_review")); item.put("usable_for_practice",JsonBool(false)); item.put("usable_for_auto_grade",JsonBool(false))
                }
            }
            let fields="source_item_id,split,subject,grade,grade_band,title,question_text,question_type,options,answer,solution,knowledge_points,image_paths,difficulty,content_hash,source_metadata,has_answer,has_solution,answer_verified,quality_status,usable_for_practice,usable_for_auto_grade"
            let names=fields.split(","); let params=ArrayList<Option<String>>(); params.add(Some(newId())); params.add(Some(sourceId))
            let marks=StringBuilder(); let updates=StringBuilder(); var first=true
            for (field in names) {
                params.add(if (field=="answer") { Some(item[field].toString()) } else { sqlValue(item[field]) }); if (!first) { marks.append(","); updates.append(",") }; first=false
                marks.append("?"); updates.append("${field}=VALUES(${field})")
            }
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
                let link=(entry as JsonObject).getOrThrow(); let code=optionalText(link,"code","",100,nonempty:true)
                let cards=tx.query("SELECT id FROM knowledge_points WHERE code=? AND subject=?",[Some(code),sqlValue(item["subject"])]).rows
                if (cards.isEmpty()) { throw ApiError(422,"知识卡不存在或学科不匹配") }
                let role=optionalText(link,"role","",30,nonempty:true)
                if (role!="primary" && role!="secondary") { throw ApiError(422,"知识映射角色无效") }
                let confidence=Float64.parse(link["confidence"].toString()); let method=optionalText(link,"method","",50,nonempty:true)
                if (!(confidence>=0.0 && confidence<=1.0) || method!="offline_rules" && method!="subject_grade_fallback") { throw ApiError(422,"知识映射依据无效") }
                tx.query("INSERT INTO question_knowledge_links (id,dataset_question_id,knowledge_point_id,role,confidence,mapping_method,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(id),Some(rowText(cards[0],"id")),Some(role),Some(confidence.toString()),Some(method)])
            }
        }
        let count=rowText(tx.query("SELECT COUNT(*) AS count FROM dataset_questions WHERE dataset_source_id=?",[Some(sourceId)]).rows[0],"count")
        tx.query("UPDATE dataset_sources SET total_items=?,imported_items=?,last_imported_at=UTC_TIMESTAMP(6),updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(count),Some(count),Some(sourceId)])
        let result=JsonObject(); result.put("stored",JsonString(count)); result.put("source",JsonString(key)); return result
    })
}

// Deployment-only format reviews use the exported content hash as a CAS guard.
// Source text, answers, assets and student work are never rewritten here.
func questionBankFormatReview(db: Database, body: JsonObject): JsonObject {
    let rows=tutorArray(body,"questions")
    if (rows.getItems().isEmpty() || rows.getItems().size>100) { throw ApiError(422,"每批需要1至100道题") }
    let seen=HashSet<String>()
    for (raw in rows.getItems()) {
        if (!(raw is JsonObject)) { throw ApiError(422,"核验记录无效") }
        let item=(raw as JsonObject).getOrThrow(); let id=optionalText(item,"id","",36,nonempty:true)
        if (seen.contains(id)) { throw ApiError(422,"核验记录重复") }; seen.add(id)
        let hash=optionalText(item,"content_hash","",64,nonempty:true)
        if (hash.size!=64) { throw ApiError(422,"内容指纹无效") }
        for (byte in hash.toArray()) { if (!(byte>=48 && byte<=57 || byte>=97 && byte<=102)) { throw ApiError(422,"内容指纹无效") } }
        if (!(item["fields"] is JsonArray)) { throw ApiError(422,"核验字段无效") }
        let fields=tutorArray(item,"fields"); if (fields.getItems().isEmpty() || fields.getItems().size>20) { throw ApiError(422,"核验字段无效") }
        for (entry in fields.getItems()) {
            if (!(entry is JsonString)) { throw ApiError(422,"核验字段无效") }
            let field=(entry as JsonString).getOrThrow().getValue()
            if (field!="question" && field!="solution" && !(field.startsWith("option.") && field.size==8 && field.toArray()[7]>=65 && field.toArray()[7]<=72)) { throw ApiError(422,"核验字段无效") }
        }
    }
    return db.transaction<JsonObject>({ tx =>
        var changed: Int64=0
        for (raw in rows.getItems()) {
            let item=(raw as JsonObject).getOrThrow(); let id=jsonText(item,"id")
            let saved=tx.query("SELECT * FROM dataset_questions WHERE id=? FOR UPDATE",[Some(id)]).rows
            if (saved.isEmpty()) { throw ApiError(404,"题目不存在") }
            let value=rowJson("dataset_questions",saved[0])
            if (jsonText(value,"content_hash")!=jsonText(item,"content_hash")) { throw ApiError(409,"题目已更新，请重新核验") }
            let metadata=tutorObject(value,"source_metadata"); let review=JsonObject()
            review.put("content_hash",item["content_hash"]); review.put("fields",item["fields"])
            if (!jsonEquivalent(metadata.get("format_review") ?? JsonNull(),review) || jsonText(value,"quality_status")!="format_review" || tutorFlag(value,"usable_for_practice") || tutorFlag(value,"usable_for_auto_grade")) {
                metadata.put("format_review",review)
                tx.query("UPDATE dataset_questions SET source_metadata=?,quality_status='format_review',usable_for_practice=0,usable_for_auto_grade=0,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(metadata.toString()),Some(id)]); changed++
            }
        }
        let result=JsonObject(); result.put("changed",JsonInt(changed)); return result
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
            let operation=optionalText(body,"operation","",30,nonempty:true)
            if (operation=="import") { println(questionBankImport(db,body).toString()); return 0 }
            if (operation=="review-format") { println(questionBankFormatReview(db,body).toString()); return 0 }
            if (operation=="audit-export") {
                let after=optionalText(body,"after","",36); let output=JsonArray()
                for (row in db.query("SELECT * FROM dataset_questions WHERE id>? ORDER BY id LIMIT 100",[Some(after)]).rows) { output.add(rowJson("dataset_questions",row)) }
                println(output.toString()); return 0
            }
            if (operation=="cards") {
                let output=JsonArray(); for (row in db.query("SELECT * FROM knowledge_points ORDER BY code").rows) { output.add(rowJson("knowledge_points",row)) }
                println(output.toString()); return 0
            }
            if (operation=="export") {
                let source=optionalText(body,"source","",80,nonempty:true); let after=optionalText(body,"after","",36)
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
