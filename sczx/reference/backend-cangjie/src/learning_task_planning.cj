package zhiwei

import std.convert.*
import std.collection.*
import stdx.encoding.json.*

func taskBankRow(row: HashMap<String,Option<String>>): JsonObject {
    let base=HashMap<String,Option<String>>()
    for ((key,value) in row) {
        if (key!="recent_n" && key!="recent_pass") { base[key]=value }
    }
    return rowJson("dataset_questions",base)
}

// Fixed ordering keeps the optimistic source comparison deterministic.
// Candidate IDs come only from the caller's due notebook or eligible bank.
func taskPlanCandidates(db: Database, owner: String, question: JsonObject, points: Array<String>): JsonArray {
    let result=JsonArray(); let questionId=tutorText(question,"id")
    for (row in db.query("SELECT q.* FROM questions q WHERE q.user_id=? AND q.subject=? AND q.id<>? AND EXISTS(SELECT 1 FROM review_plans r WHERE r.question_id=q.id AND r.user_id=? AND r.status='pending' AND r.due_at<=UTC_TIMESTAMP()) ORDER BY q.id LIMIT 30",[Some(owner),sqlValue(question["subject"]),Some(questionId),Some(owner)]).rows) {
        let source=rowJson("questions",row); let item=JsonObject()
        item.put("id",source["id"]); item.put("subject",source["subject"]); item.put("source",JsonString("notebook")); item.put("due",JsonBool(true)); item.put("estimated_minutes",JsonInt(3))
        item.put("question_type",source["question_type"]); result.add(item)
    }
    for (row in db.query("SELECT q.*,(SELECT COUNT(*) FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id WHERE s.user_id=? AND s.created_at>=UTC_TIMESTAMP()-INTERVAL 7 DAY AND JSON_UNQUOTE(JSON_EXTRACT(i.snapshot,'$.id'))=q.id) AS recent_n,EXISTS(SELECT 1 FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id WHERE s.user_id=? AND s.status='submitted' AND s.created_at>=UTC_TIMESTAMP()-INTERVAL 1 DAY AND JSON_UNQUOTE(JSON_EXTRACT(i.snapshot,'$.id'))=q.id AND JSON_EXTRACT(i.grading,'$.correct')=true AND JSON_EXTRACT(i.grading,'$.can_update_learning')=true) AS recent_pass FROM dataset_questions q WHERE q.subject=? AND q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND q.has_answer=1 ORDER BY q.id LIMIT 200",[Some(owner),Some(owner),sqlValue(question["subject"])]).rows) {
        if (result.getItems().size>=200) { break }
        let source=taskBankRow(row)
        if (!usableRetrievalCandidate(question,source,"practice")) { continue }
        var related=false
        for (raw in tutorArray(source,"knowledge_points").getItems()) {
            let label=if (raw is JsonString) { (raw as JsonString).getOrThrow().getValue() } else { tutorText((raw as JsonObject).getOrThrow(),"name") }
            for (point in points) { if (label==point && !label.isEmpty()) { related=true } }
        }
        // Without concept tags, keep only the current question type as an
        // explicit coarse fallback; do not suggest arbitrary same-subject work.
        if (!related && tutorText(source,"question_type")!=tutorText(question,"question_type")) { continue }
        let item=JsonObject()
        for (key in ["id","subject","question_type","grade_band","knowledge_points","options"]) { item.put(key,source[key]) }
        item.put("source",JsonString("dataset")); item.put("error_relevance",JsonFloat(if (related) { 1.0 } else { 0.2 })); item.put("estimated_minutes",JsonInt(3))
        let difficulty=tutorText(source,"difficulty")
        item.put("difficulty",JsonFloat(if (["easy","简单","容易"].contains(difficulty)) { 0.25 } else if (["hard","困难","较难"].contains(difficulty)) { 0.8 } else { 0.5 }))
        item.put("recent_exposures",JsonInt(Int64.parse(rowText(row,"recent_n"))))
        item.put("just_mastered",JsonBool(rowText(row,"recent_pass")=="1")); result.add(item)
    }
    return result
}

func validateTaskRecommendation(result: JsonObject, domain: JsonObject): Unit {
    let view=tutorObject(result,"student_view"); let plan=tutorObject(view,"recommendation"); let id=tutorText(plan,"question_id")
    if (id.isEmpty()) { return }
    var valid=false
    for (raw in tutorArray(domain,"practice_candidates").getItems()) {
        let candidate=(raw as JsonObject).getOrThrow()
        if (tutorText(candidate,"id")==id && tutorText(candidate,"source")==tutorText(plan,"question_source") && !tutorFlag(candidate,"just_mastered")) { valid=true }
    }
    if (!valid) { throw ApiError(503,"推荐题目不在本次可用范围内") }
    for (raw in tutorArray(plan,"alternatives").getItems()) {
        let alternate=(raw as JsonString).getOrThrow().getValue(); var found=false
        for (entry in tutorArray(domain,"practice_candidates").getItems()) {
            let candidate=(entry as JsonObject).getOrThrow()
            if (tutorText(candidate,"id")==alternate && !tutorFlag(candidate,"just_mastered")) { found=true }
        }
        if (!found || alternate==id) { throw ApiError(503,"备选题目不在本次可用范围内") }
    }
}
