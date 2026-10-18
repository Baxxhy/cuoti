package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.encoding.url.*
import stdx.net.http.*

func paperCandidatesData(db: Database, owner: String, filters: JsonObject): JsonArray {
    let result=JsonArray(); let seen=HashSet<String>(); let params=ArrayList<Option<String>>([Some(owner)])
    var sql="SELECT * FROM questions WHERE user_id=? AND status<>'archived'"
    let subject=tutorText(filters,"subject")
    if (!subject.isEmpty()) { sql+=" AND subject=?"; params.add(Some(subject)) }
    sql+=" ORDER BY created_at DESC,id DESC"
    for (row in db.query(sql,params.toArray()).rows) {
        let question=rowJson("questions",row); let id=jsonText(question,"id"); let key=questionDisplayKey(jsonText(question,"question_text"),id)
        if (seen.contains(key)) { continue }; seen.add(key)
        let analyses=db.query("SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1",[Some(id)]).rows
        let knowledge=if (!tutorArray(question,"knowledge_points").getItems().isEmpty()) { tutorArray(question,"knowledge_points") } else if (analyses.isEmpty()) { JsonArray() } else { tutorArray(rowJson("problem_analyses",analyses[0]),"knowledge_points") }
        let diagnoses=db.query("SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",[Some(id)]).rows
        let diagnosis=if (diagnoses.isEmpty()) { JsonObject() } else { rowJson("diagnoses",diagnoses[0]) }
        let knowledgeFilter=tutorText(filters,"knowledge_point"); var matched=knowledgeFilter.isEmpty()
        for (point in knowledge.getItems()) { if (tutorAnswerText(point).contains(knowledgeFilter)) { matched=true } }
        if (!matched) { continue }
        let errorFilter=tutorText(filters,"error_type")
        if (!errorFilter.isEmpty() && !tutorText(diagnosis,"error_type").contains(errorFilter)) { continue }
        var score=0.0
        for (masteryRow in db.query("SELECT * FROM mastery_states WHERE user_id=? AND subject=? ORDER BY updated_at DESC,id DESC",[Some(owner),row["subject"]]).rows) {
            let point=rowText(masteryRow,"knowledge_point"); var matchPoint=false
            for (value in knowledge.getItems()) { if (tutorAnswerText(value)==point) { matchPoint=true } }
            if (matchPoint) { score=editNumber(rowJson("mastery_states",masteryRow)["mastery_score"]); break }
        }
        if (score<editNumber(filters.get("mastery_min") ?? JsonInt(0)) || score>editNumber(filters.get("mastery_max") ?? JsonInt(1))) { continue }
        let reviews=db.query("SELECT * FROM review_plans WHERE user_id=? AND question_id=? ORDER BY due_at DESC,id DESC LIMIT 1",[Some(owner),Some(id)]).rows
        if (tutorFlag(filters,"due_review") && (reviews.isEmpty() || rowText(reviews[0],"status")!="pending")) { continue }
        question.put("knowledge_points",knowledge); question.put("mastery_score",JsonFloat(score))
        question.put("error_type",JsonString(if (diagnoses.isEmpty()) { "未诊断" } else { tutorText(diagnosis,"error_type") })); question.put("root_misconception",JsonString(tutorText(diagnosis,"root_misconception")))
        question.put("review_due_at",if (reviews.isEmpty()) { JsonNull() } else { rowJson("review_plans",reviews[0])["due_at"] }); result.add(question)
    }
    return result
}

func paperCandidates(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let form=Form(context.request.url.rawQuery ?? ""); let raw=JsonObject()
    for (key in ["subject","knowledge_point","error_type"]) { let value=queryLast(form,key); if (!value.isEmpty()) { raw.put(key,JsonString(value)) } }
    for (key in ["mastery_min","mastery_max"]) {
        let value=queryLast(form,key)
        if (!value.isEmpty()) { try { raw.put(key,JsonValue.fromStr(value)) } catch (_: Exception) { throw ApiError(422,"掌握度范围无效") } }
    }
    let due=queryLast(form,"due_review"); if (!due.isEmpty()) { raw.put("due_review",JsonString(due)) }
    let filters=paperFilters(raw)
    try (db=Database.fromEnvironment()) { let user=accounts.currentUser(context,db); return paperCandidatesData(db,rowText(user,"id"),filters) }
    throw ApiError(503,"数据库暂时不可用")
}
