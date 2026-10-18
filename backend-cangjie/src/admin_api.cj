package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

func adminMetrics(db: Database, owner: String): JsonObject {
    let result=JsonObject()
    for ((key,table,extra) in [("questions","questions"," AND status<>'archived'"),("sessions","tutor_sessions",""),("pending_reviews","review_plans"," AND status='pending'")]) {
        result.put(key,JsonInt(schoolCount(db,"SELECT COUNT(*) AS count FROM ${table} WHERE user_id=?${extra}",[Some(owner)])))
    }
    return result
}

func adminStudentData(db: Database, id: String): JsonObject {
    let rows=db.query("SELECT * FROM users WHERE id=? AND role='student'",[Some(id)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"未找到学生") }
    let user=rowJson("users",rows[0]); let profiles=db.query("SELECT * FROM student_profiles WHERE user_id=?",[Some(id)]).rows
    let profile=if (profiles.isEmpty()) { JsonObject() } else { rowJson("student_profiles",profiles[0]) }
    let result=JsonObject(); let student=adminFields(user,["id","name","created_at"])
    student.put("grade",JsonString(if (profiles.isEmpty()) { "未设置" } else { tutorText(profile,"grade") })); student.put("learning_goal",JsonString(tutorText(profile,"learning_goal")))
    result.put("student",student); result.put("metrics",adminMetrics(db,id)); let mastery=JsonArray(); let misconceptions=JsonArray(); let reviews=JsonArray()
    for (row in db.query("SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at DESC,id DESC LIMIT 20",[Some(id)]).rows) {
        let value=rowJson("mastery_states",row); let item=adminFields(value,["subject","knowledge_point","confidence","forgetting_risk","evidence_count"]); item.put("score",value["mastery_score"]); mastery.add(item)
    }
    for (row in db.query("SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id DESC LIMIT 20",[Some(id)]).rows) { misconceptions.add(adminFields(rowJson("misconception_states",row),["code","label","probability","status","evidence_count"])) }
    for (row in db.query("SELECT * FROM review_plans WHERE user_id=? ORDER BY due_at,id LIMIT 20",[Some(id)]).rows) { reviews.add(adminFields(rowJson("review_plans",row),["id","question_id","due_at","status","reason"])) }
    result.put("mastery",mastery); result.put("misconceptions",misconceptions); result.put("reviews",reviews); return result
}

func adminSessionData(db: Database, id: String): JsonObject {
    let rows=db.query("SELECT * FROM tutor_sessions WHERE id=?",[Some(id)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"未找到教学会话") }
    let session=rowJson("tutor_sessions",rows[0]); let owner=jsonText(session,"user_id"); let questionId=jsonText(session,"question_id")
    let users=db.query("SELECT * FROM users WHERE id=?",[Some(owner)]).rows; let questions=db.query("SELECT * FROM questions WHERE id=?",[Some(questionId)]).rows
    let diagnoses=db.query("SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",[Some(questionId)]).rows
    let result=JsonObject(); result.put("session",adminFields(session,["id","stage","status","turn_count","hint_level","mastery_score","created_at","updated_at"]))
    result.put("student",if (users.isEmpty()) { JsonNull() } else { adminFields(rowJson("users",users[0]),["id","name"]) })
    result.put("question",if (questions.isEmpty()) { JsonNull() } else { adminFields(rowJson("questions",questions[0]),["id","title","subject","question_text","student_answer","knowledge_points"]) })
    result.put("diagnosis",if (diagnoses.isEmpty()) { JsonNull() } else { adminFields(rowJson("diagnoses",diagnoses[0]),["first_error_step","first_error_text","error_type","root_misconception","confidence","recommended_strategy"]) })
    let turns=JsonArray()
    for (row in db.query("SELECT * FROM tutor_turns WHERE session_id=? ORDER BY created_at,id",[Some(id)]).rows) {
        let value=rowJson("tutor_turns",row); let item=adminFields(value,["id","role","content","stage"]); item.put("time",adminTimestamp(value["created_at"])); item.put("decision",adminSanitize(value.get("metadata_json") ?? JsonObject())); turns.add(item)
    }
    let updates=JsonArray()
    for (row in db.query("SELECT * FROM cognitive_updates WHERE user_id=? AND question_id=? ORDER BY created_at,id",[Some(owner),Some(questionId)]).rows) {
        let value=rowJson("cognitive_updates",row); let item=adminFields(value,["id","entity_type","entity_key","old_value","new_value","reason"]); item.put("time",adminTimestamp(value["created_at"])); updates.add(item)
    }
    result.put("turns",turns); result.put("trace",adminTrace(db,id)); result.put("cognitive_updates",updates); return result
}

func adminWorkbenchData(db: Database): JsonObject {
    let result=JsonObject(); result.put("generated_at",JsonString(rowText(db.query("SELECT DATE_FORMAT(UTC_TIMESTAMP(6),'%Y-%m-%dT%H:%i:%s.%f+00:00') AS generated_at").rows[0],"generated_at")))
    let metrics=JsonObject()
    for ((key,table,condition) in [("students","users","role='student'"),("questions","questions","status<>'archived'"),("diagnoses","diagnoses","1=1"),("sessions","tutor_sessions","1=1"),("active_sessions","tutor_sessions","status='active'"),("agent_runs","agent_runs","1=1"),("cognitive_updates","cognitive_updates","1=1"),("pending_reviews","review_plans","status='pending'")]) {
        metrics.put(key,JsonInt(schoolCount(db,"SELECT COUNT(*) AS count FROM ${table} WHERE ${condition}",[])))
    }
    result.put("metrics",metrics); let students=JsonArray(); let sessions=JsonArray()
    for (row in db.query("SELECT * FROM users WHERE role='student' ORDER BY updated_at DESC,id DESC LIMIT 50").rows) {
        let user=rowJson("users",row); let id=jsonText(user,"id"); let item=adminFields(user,["id","name","updated_at"])
        let profiles=db.query("SELECT grade FROM student_profiles WHERE user_id=?",[Some(id)]).rows
        item.put("grade",JsonString(if (profiles.isEmpty()) { "未设置" } else { rowText(profiles[0],"grade") }))
        let counts=adminMetrics(db,id); item.put("question_count",counts["questions"]); item.put("session_count",counts["sessions"]); students.add(item)
    }
    for (row in db.query("SELECT s.*,u.name AS student_name,q.title AS question_title,q.subject AS question_subject FROM tutor_sessions s JOIN users u ON u.id=s.user_id JOIN questions q ON q.id=s.question_id ORDER BY s.updated_at DESC,s.id DESC LIMIT 50").rows) {
        let item=JsonObject()
        for (key in ["id","stage","status","updated_at"]) { item.put(key,if (key=="updated_at") { JsonString(rowText(row,key).replace(" ","T")) } else { JsonString(rowText(row,key)) }) }
        for ((key,source) in [("student_id","user_id"),("student_name","student_name"),("question_id","question_id"),("question_title","question_title"),("subject","question_subject")]) { item.put(key,JsonString(rowText(row,source))) }
        item.put("turn_count",JsonValue.fromStr(rowText(row,"turn_count"))); item.put("mastery_score",JsonValue.fromStr(rowText(row,"mastery_score"))); sessions.add(item)
    }
    result.put("students",students); result.put("sessions",sessions)
    let state=systemState(); let provider=tutorObject(state,"provider"); let voice=tutorObject(state,"voice"); let providerPublic=adminFields(provider,["logical_model","total_entries","text_entries","vision_entries"]); providerPublic.put("status",provider["last_status"])
    let system=JsonObject(); system.put("database",JsonString("mysql")); system.put("provider",providerPublic); system.put("voice",adminFields(voice,["status","loaded","stt_model","tts_model"])); result.put("system",system); return result
}

func adminApi(context: HttpContext, accounts: Accounts, kind: String): JsonValue {
    requireMethod(context,"GET")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        if (rowText(user,"role")!="admin") { throw ApiError(403,"请使用管理员账号") }
        let parts=context.request.url.path.split("/"); let id=parts[parts.size-1]
        return db.transaction<JsonValue>({ tx =>
            if (kind=="student") { return adminStudentData(tx,id) }
            if (kind=="session") { return adminSessionData(tx,id) }
            return adminWorkbenchData(tx)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
