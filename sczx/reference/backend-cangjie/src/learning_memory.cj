package zhiwei

import std.collection.*
import std.time.*
import stdx.encoding.json.*

func memoryTime(value: String): Int64 { return DateTime.parse(value).toUnixTimeStamp().toSeconds() }

func memoryEntry(kind: String, row: JsonObject, questionId: String, classification: String, summary: String, days: Int64, sourceVersion: String, sources: JsonArray, independence!: String="not_applicable", outcome!: String="unknown"): JsonObject {
    let result=JsonObject(); let observed=memoryTime(tutorText(row,"updated_at")); let ref=kind+":"+jsonText(row,"id")
    result.put("ref",JsonString(ref)); result.put("kind",JsonString(kind)); result.put("classification",JsonString(classification)); result.put("question_id",JsonString(questionId)); result.put("source_refs",sources)
    result.put("observed_at",JsonInt(observed)); result.put("expires_at",JsonInt(observed+days*86400)); result.put("summary",JsonString(shortTitle(summary,400)))
    let version=JsonArray(); version.add(row); version.add(JsonString(sourceVersion)); result.put("version",JsonString(sha256(version.toString().toArray())))
    result.put("independence",JsonString(independence)); result.put("outcome",JsonString(outcome)); return result
}

func memoryRefs(values: Array<String>): JsonArray { let result=JsonArray(); for (v in values) { result.add(JsonString(v)) }; return result }

func memoryEstimateCurrent(db: Database, row: JsonObject, kind: String, owner: String, subject: String): Bool {
    let key=if (kind=="mastery") { "knowledge_point" } else { "code" }
    let sourceKey=if (kind=="mastery") { "mastery_id" } else { "misconception_id" }
    let rows=db.query("SELECT u.* FROM cognitive_updates u WHERE u.user_id=? AND u.entity_type=? AND u.entity_key=? AND (JSON_UNQUOTE(JSON_EXTRACT(u.evidence,'$.memory_source.${sourceKey}'))=? OR JSON_EXTRACT(u.evidence,'$.memory_source') IS NULL) ORDER BY u.created_at DESC,u.id DESC LIMIT 1",[Some(owner),Some(kind),sqlValue(row[key]),sqlValue(row["id"])]).rows
    if (rows.isEmpty()) { return true } // Unattributed estimates stay explicitly uncertain.
    let update=rowJson("cognitive_updates",rows[0]); let source=tutorObject(tutorObject(update,"evidence"),"memory_source")
    if (source.getFields().isEmpty()) { return true }
    return memoryUpdateValid(db,update,owner,subject)
}

// Rebuilt from source rows per execution; no immortal generated summary cache.
func learningMemory(db: Database, owner: String, question: JsonObject): JsonObject {
    let subject=jsonText(question,"subject"); let questionId=jsonText(question,"id"); let entries=JsonArray(); let legacy=JsonObject()
    for (key in ["mastery","misconceptions","updates","reviews"]) { legacy.put(key,JsonArray()) }
    let mastery=tutorArray(legacy,"mastery"); let mistakes=tutorArray(legacy,"misconceptions"); let updates=tutorArray(legacy,"updates"); let plans=tutorArray(legacy,"reviews")
    for (row in db.query("SELECT * FROM mastery_states WHERE user_id=? AND subject=? AND updated_at<=UTC_TIMESTAMP(6) AND updated_at>UTC_TIMESTAMP(6)-INTERVAL 30 DAY ORDER BY updated_at DESC,id DESC LIMIT 12",[Some(owner),Some(subject)]).rows) {
        if (mastery.getItems().size>=3) { break }
        let record=rowJson("mastery_states",row)
        if (!memoryEstimateCurrent(db,record,"mastery",owner,subject)) { continue }
        mastery.add(record); let ref="mastery:"+jsonText(record,"id")
        entries.add(memoryEntry("mastery",record,"","estimate",tutorText(record,"knowledge_point")+"：历史掌握估计 "+record["mastery_score"].toString()+"，不是掌握证明",30,"",memoryRefs([ref])))
    }
    for (row in db.query("SELECT * FROM misconception_states WHERE user_id=? AND subject=? AND status='active' AND updated_at<=UTC_TIMESTAMP(6) AND updated_at>UTC_TIMESTAMP(6)-INTERVAL 30 DAY ORDER BY updated_at DESC,id DESC LIMIT 12",[Some(owner),Some(subject)]).rows) {
        if (mistakes.getItems().size>=3) { break }
        let record=rowJson("misconception_states",row)
        if (!memoryEstimateCurrent(db,record,"misconception",owner,subject)) { continue }
        mistakes.add(record); let ref="misconception:"+jsonText(record,"id")
        entries.add(memoryEntry("misconception",record,"","candidate",tutorText(record,"label")+"：待核对误区候选，不能对学生定性",30,"",memoryRefs([ref])))
    }
    for (row in db.query("SELECT u.* FROM cognitive_updates u JOIN questions q ON q.id=u.question_id WHERE u.user_id=? AND q.subject=? AND u.entity_type='mastery' AND u.updated_at<=UTC_TIMESTAMP(6) AND u.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY u.updated_at DESC,u.id DESC LIMIT 30",[Some(owner),Some(subject)]).rows) {
        if (updates.getItems().size>=4) { break }
        let record=rowJson("cognitive_updates",row)
        if (!memoryUpdateValid(db,record,owner,subject)) { continue }
        let evidence=tutorObject(record,"evidence"); let strategy=tutorText(evidence,"strategy")
        let aemt=tutorObject(evidence,"aemt_event"); let aemtVerdict=tutorText(aemt,"verdict")
        let correct=tutorFlag(evidence,"near_transfer") || tutorFlag(evidence,"far_transfer") || (strategy=="aemt_assistance_aware" && aemtVerdict=="confirmed_correct")
        let outcome=if (correct) { "correct" } else if (strategy=="independent_dataset_practice" || (strategy=="aemt_assistance_aware" && aemtVerdict=="confirmed_incorrect")) { "incorrect" } else { "unknown" }
        let independence=if (strategy=="assisted_progression" || tutorNumber(evidence,"hint_level")>0) { "assisted" } else { "independent" }
        let ref="cognitive:"+jsonText(record,"id"); let sources=memoryRefs([ref,"question:"+tutorText(record,"question_id")])
        for ((key,prefix) in [("learning_task_id","task:"),("practice_attempt_id","practice:"),("tutor_session_id","tutor:")]) { let id=tutorText(evidence,key); if (!id.isEmpty()) { sources.add(JsonString(prefix+id)) } }
        let scope=if (strategy=="aemt_assistance_aware" && tutorText(aemt,"scope")=="original_question") { "本次原题作答" } else { "本次迁移作答" }
        let summary=tutorText(record,"entity_key")+"：历史学习事件，"+if (outcome=="correct") { if (strategy=="aemt_assistance_aware") { scope+"正确" } else { "本次迁移判定正确" } } else if (outcome=="incorrect") { if (strategy=="aemt_assistance_aware") { scope+"有误" } else { "本次迁移作答有误" } } else { "结果尚不充分" }
        entries.add(memoryEntry("cognitive",record,tutorText(record,"question_id"),"verified_event",summary+"；不代表整个知识点掌握",90,tutorText(tutorObject(evidence,"memory_source"),"question_version"),sources,independence:independence,outcome:outcome)); updates.add(record)
    }
    var reviewed: Int64=0
    for (row in db.query("SELECT r.* FROM review_records r JOIN review_plans p ON p.id=r.plan_id JOIN questions q ON q.id=p.question_id WHERE p.user_id=? AND q.user_id=? AND q.subject=? AND q.status<>'archived' AND q.confirmed=1 AND r.grade<>'pending' AND r.updated_at<=UTC_TIMESTAMP(6) AND r.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY r.updated_at DESC,r.id DESC LIMIT 20",[Some(owner),Some(owner),Some(subject)]).rows) {
        if (reviewed>=3) { break }
        let record=rowJson("review_records",row); let details=tutorObject(record,"grading_details")
        if (!tutorFlag(details,"can_update_learning") || !["confirmed_correct","confirmed_incorrect"].contains(tutorText(details,"verdict"))) { continue }
        let planRows=db.query("SELECT question_id FROM review_plans WHERE id=? AND user_id=?",[sqlValue(record["plan_id"]),Some(owner)]).rows
        if (planRows.isEmpty()) { continue }
        let id=rowText(planRows[0],"question_id"); let sourceQuestion=memoryQuestion(db,id,subject); let version=memoryQuestionVersion(db,sourceQuestion)
        if (tutorText(details,"memory_question_version")!=version) { continue }
        let outcome=if (tutorFlag(record,"correct")) { "correct" } else { "incorrect" }
        entries.add(memoryEntry("review_record",record,id,"verified_event","本次复习系统判定"+if (outcome=="correct") { "正确；难度自评不等于掌握" } else { "有误；不以学生的难度自评改为正确" },90,version,memoryRefs(["review_record:"+jsonText(record,"id"),"review:"+tutorText(record,"plan_id")]),independence:"unknown",outcome:outcome)); reviewed++
    }
    var notes: Int64=0
    for (row in db.query("SELECT n.* FROM learning_self_checks n JOIN learning_tasks t ON t.id=n.task_id JOIN questions q ON q.id=n.question_id WHERE n.user_id=? AND q.user_id=? AND q.subject=? AND q.status<>'archived' AND q.confirmed=1 AND n.deleted=0 AND t.status='completed' AND n.updated_at<=UTC_TIMESTAMP(6) AND n.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY n.updated_at DESC,n.id DESC LIMIT 20",[Some(owner),Some(owner),Some(subject)]).rows) {
        if (notes>=3) { break }
        let record=rowJson("learning_self_checks",row); let id=tutorText(record,"question_id")
        let version=taskFingerprint(taskSnapshot(db,id,owner,lock:false))
        if (version!=tutorText(record,"input_fingerprint")) { continue }
        entries.add(memoryEntry("self_check",record,id,"student_self_report","学生确认的自述（未证明掌握）："+tutorText(record,"text"),90,version,memoryRefs(["self_check:"+jsonText(record,"id"),"task:"+tutorText(record,"task_id")]))); notes++
    }
    for (row in db.query("SELECT p.* FROM review_plans p JOIN questions q ON q.id=p.question_id WHERE p.user_id=? AND q.user_id=? AND q.id=? AND q.subject=? AND q.status<>'archived' AND q.confirmed=1 AND p.status='pending' AND p.updated_at<=UTC_TIMESTAMP(6) AND p.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY p.due_at,p.id LIMIT 2",[Some(owner),Some(owner),Some(questionId),Some(subject)]).rows) {
        let record=rowJson("review_plans",row); let version=memoryQuestionVersion(db,question); plans.add(record)
        entries.add(memoryEntry("review",record,questionId,"reminder","当前题有待复习安排，到期时间："+tutorText(record,"due_at")+"；安排不证明学会",90,version,memoryRefs(["review:"+jsonText(record,"id"),"question:"+questionId])))
    }
    let snapshot=JsonObject(); snapshot.put("rule_version",JsonString("learning-memory-v1")); snapshot.put("entries",entries)
    let result=JsonObject(); result.put("snapshot",snapshot); result.put("legacy_rows",legacy); return result
}

func applyTaskMemoryContext(context: JsonObject, memory: JsonObject): Unit {
    let snapshot=tutorObject(memory,"snapshot"); let refs=JsonArray(); let versions=JsonObject(); let summary=StringBuilder()
    for (value in tutorArray(snapshot,"entries").getItems()) {
        let entry=(value as JsonObject).getOrThrow(); refs.add(entry["ref"]); versions.put(jsonText(entry,"ref"),entry["version"])
        let text=tutorText(entry,"summary")+"；"
        if (runeCount(summary.toString())+runeCount(text)<=1800) { summary.append(text) }
    }
    context.put("memory_snapshot",snapshot); context.put("memory_refs",refs); context.put("memory_versions",versions); context.put("memory_summary",JsonString(shortTitle(summary.toString(),1800)))
}

func memoryAuditManifest(snapshot: JsonObject): JsonArray {
    let result=JsonArray()
    for (raw in tutorArray(snapshot,"entries").getItems()) {
        let entry=(raw as JsonObject).getOrThrow(); let item=JsonObject()
        for (key in ["ref","version","classification","observed_at","expires_at","question_id","source_refs"]) { item.put(key,entry[key]) }
        result.add(item)
    }
    return result
}
