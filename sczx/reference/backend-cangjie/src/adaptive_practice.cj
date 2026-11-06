package zhiwei

import std.collection.*
import stdx.encoding.json.*

func adaptivePracticeSelection(db: Database, owner: String, subject: String, band: String, source: String, search: String, count: Int64, grade!: String): JsonObject {
    let candidates=JsonArray(); let allowed=HashSet<String>()
    for (row in db.query("SELECT q.*"+bankScopedWhere(grade)+" ORDER BY RAND() LIMIT 200",bankFilter(subject,band,source,search,grade:grade)).rows) {
        let q=rowJson("dataset_questions",row); let item=JsonObject()
        for (key in ["id","subject","grade_band","question_type","knowledge_points","options"]) { item.put(key,q[key]) }
        candidates.add(item); allowed.add(jsonText(q,"id"))
    }
    if (candidates.getItems().size<count) { throw ApiError(422,"当前范围可用题目不足，请减少题数或更换学科") }
    let observations=JsonArray()
    let history=db.query("SELECT i.snapshot,i.grading FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id JOIN dataset_questions q ON q.id=JSON_UNQUOTE(JSON_EXTRACT(i.snapshot,'$.id')) WHERE s.user_id=? AND s.status='submitted' AND q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND (?='' OR q.subject=?) ORDER BY s.created_at DESC,i.position DESC LIMIT 400",[Some(owner),Some(subject),Some(subject)]).rows
    for (offset in 0..history.size) {
        let row=history[history.size-1-offset]
        let grade=(JsonValue.fromStr(rowText(row,"grading")) as JsonObject).getOrThrow()
        let correctness=grade.get("correct") ?? JsonNull()
        if (!tutorFlag(grade,"can_update_learning") || !(correctness is JsonBool)) { continue }
        let q=(JsonValue.fromStr(rowText(row,"snapshot")) as JsonObject).getOrThrow(); let item=JsonObject()
        for (key in ["id","subject","grade_band","question_type","knowledge_points","options"]) { item.put(key,q[key]) }
        item.put("correct",grade["correct"]); item.put("confirmed",JsonBool(true)); item.put("independent",JsonBool(true)); observations.add(item)
    }
    let payload=JsonObject(); payload.put("candidates",candidates); payload.put("observations",observations); payload.put("count",JsonInt(count))
    let input=JsonObject(); input.put("operation",JsonString("adaptive_practice")); input.put("adaptive_practice",payload)
    let result=algorithmCompute(input); let ids=tutorArray(result,"question_ids"); let seen=HashSet<String>()
    if (ids.getItems().size!=count) { throw ApiError(503,"选题未完成，请重试") }
    for (id in ids.getItems()) {
        let value=(id as JsonString).getOrThrow().getValue()
        if (!allowed.contains(value) || seen.contains(value)) { throw ApiError(503,"选题结果无效，请重试") }; seen.add(value)
    }
    return result
}
