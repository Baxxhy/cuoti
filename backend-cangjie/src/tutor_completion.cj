package zhiwei

import stdx.encoding.json.*

func cognitionFirstLabel(value: JsonValue): String {
    if (let Some(values) <- (value as JsonArray)) {
        for (item in values.getItems()) {
            var text = ""
            if (let Some(object) <- (item as JsonObject)) {
                for (key in ["name","label","code"]) { text = tutorText(object,key); if (!text.isEmpty()) { break } }
            } else { text = tutorAnswerText(item) }
            text = stripWhitespace(text); if (!text.isEmpty()) { return text }
        }
    }
    return ""
}

func completeTutorLearning(db: Database, session: JsonObject, snapshot: JsonObject, insufficient: Bool): JsonObject {
    let state=tutorObject(session,"state"); let question=tutorObject(snapshot,"question")
    let owner=sqlValue(session["user_id"]); let questionId=jsonText(question,"id")
    let evidence=JsonObject()
    for (key in ["teach_back","near_transfer","far_transfer"]) { evidence.put(key,state.get(key) ?? JsonNull()) }
    evidence.put("hint_level",session["hint_level"]); evidence.put("strategy",JsonString(if (tutorFlag(state,"assisted")) { "assisted_progression" } else { "micro_activity" }))
    evidence.put("tutor_session_id",session["id"])
    let updated=applyLearningEvidence(db,jsonText(session,"user_id"),question,evidence)
    let score=editNumber(tutorObject(updated,"mastery_after")["mastery_score"])
    let days = if (insufficient) { 1 } else if (tutorFlag(state,"assisted")) { 3 } else { 15 }
    let planId=newId()
    db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,TIMESTAMPADD(DAY,?,UTC_TIMESTAMP()),?,?,'pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(planId),owner,Some(questionId),Some(days.toString()),Some(days.toString()),Some(if (insufficient) { "迁移练习还不稳定，已提高复习优先级" } else { "本轮学习已完成，按掌握情况复习" })])
    state.put("completion_summary",JsonString(if (insufficient) { "这次换一种题目还不够稳定，我已经把它放到近期优先复习。" } else { "本轮已经完成。下一次复习会根据这次是否需要提示来安排。" }))
    state.put("mastery_proven",JsonBool(!insufficient && tutorFlag(state,"far_transfer")))
    session.put("stage",JsonString("finished")); session.put("status",JsonString("completed")); session.put("mastery_score",JsonFloat(score))
    db.query("UPDATE tutor_sessions SET status='completed',mastery_score=? WHERE id=?",[Some(score.toString()),sqlValue(session["id"])])
    let output = JsonObject(); output.put("mastery",JsonFloat(score)); output.put("interval_days",JsonInt(days)); output.put("priority",JsonString(if (insufficient) { "high" } else { "normal" }))
    recordTutorTool(db,jsonText(session,"id"),"activity_finish","update_cognition",evidence,output)
    let result=JsonObject(); result.put("mastery",updated["mastery_after"]); result.put("misconception",updated["misconception_after"]); result.put("review",rowJson("review_plans",db.query("SELECT * FROM review_plans WHERE id=?",[Some(planId)]).rows[0])); return result
}
