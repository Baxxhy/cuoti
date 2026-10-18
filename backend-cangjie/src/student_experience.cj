package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

// A read-only projection of current diagnoses. No new mastery or predicted marks.
func studentErrorSources(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let form=insightQuery(context); let days=insightDays(form,90,365); let subject=queryLast(form,"subject")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let rows=tx.query("SELECT q.* FROM questions q JOIN diagnoses d ON d.id=(SELECT d2.id FROM diagnoses d2 WHERE d2.question_id=q.id ORDER BY d2.created_at DESC,d2.id DESC LIMIT 1) WHERE q.user_id=? AND q.status<>'archived' AND q.confirmed=1 AND (?='' OR q.subject=?) AND d.created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) ORDER BY q.updated_at DESC,q.id DESC LIMIT 201",[user["id"],Some(subject),Some(subject),Some((-days).toString())]).rows
            let sources=JsonArray(); let seen=HashSet<String>(); var scanned: Int64=0
            for (row in rows) {
                if (scanned>=200) { break }; scanned++
                let key=questionDisplayKey(rowText(row,"question_text"),rowText(row,"id"))
                if (seen.contains(key)) { continue }; seen.add(key)
                let question=rowJson("questions",row)
                let diagnosis=firstJson(queryArray(tx,"diagnoses","SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",rowText(row,"id")))
                let item=JsonObject()
                for (field in ["id","subject","grade","question_text","knowledge_points","updated_at"]) { item.put(field,question[field]) }
                item.put("diagnosis",diagnosis)
                let plans=tx.query("SELECT id FROM review_plans WHERE user_id=? AND question_id=? AND status='pending' AND due_at<TIMESTAMP(DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR))+INTERVAL 16 HOUR ORDER BY due_at,id LIMIT 1",[user["id"],row["id"]]).rows
                item.put("due_review_id",if (plans.isEmpty()) { JsonNull() } else { JsonString(rowText(plans[0],"id")) })
                sources.add(item)
            }
            let result=JsonObject(); result.put("sources",sources); result.put("days",JsonInt(days)); result.put("limit",JsonInt(200)); result.put("truncated",JsonBool(rows.size>200)); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func studentLearningPreferences(context: HttpContext, accounts: Accounts): JsonValue {
    let method=context.request.method
    if (method!="GET" && method!="PATCH") { throw ApiError(405,"请求方法不支持") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        if (rowText(user,"role")!="student") { throw ApiError(403,"仅学生可以修改本人的学习方向") }
        let body=if (method=="PATCH") { readJson(context) } else { JsonObject() }
        return db.transaction<JsonValue>({ tx =>
            let rows=tx.query("SELECT * FROM student_profiles WHERE user_id=? FOR UPDATE",[user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"学生档案不存在") }
            let profile=rowJson("student_profiles",rows[0]); let preferences=tutorObject(profile,"preferences")
            let version=tutorNumber(preferences,"experience_version")
            if (method=="PATCH") {
                taskStrict(body,["subject","minutes","goal","version"])
                if (!((body.get("version") ?? JsonNull()) is JsonInt) || tutorNumber(body,"version")!=version) { throw ApiError(409,"学习方向已变化，请重新读取后保存") }
                let subject=textField(body,"subject",30)
                if (!(["语文","数学","英语","物理","化学","生物","历史","地理","道德与法治","思想政治"].contains(subject))) { throw ApiError(422,"请选择支持的学科") }
                let minutes=tutorNumber(body,"minutes")
                if (!((body.get("minutes") ?? JsonNull()) is JsonInt) || !([Int64(5),10,20].contains(minutes))) { throw ApiError(422,"请选择5、10或20分钟") }
                let goal=textField(body,"goal",30)
                if (!(["understand","practice","review"].contains(goal))) { throw ApiError(422,"请选择学习目标") }
                preferences.put("focus_subject",JsonString(subject)); preferences.put("daily_minutes",JsonInt(minutes)); preferences.put("focus_goal",JsonString(goal)); preferences.put("experience_version",JsonInt(version+1))
                tx.query("UPDATE student_profiles SET preferences=?,updated_at=UTC_TIMESTAMP(6) WHERE user_id=?",[Some(preferences.toString()),user["id"]])
            }
            let result=JsonObject(); result.put("grade",profile["grade"]); result.put("subject",JsonString(tutorText(preferences,"focus_subject"))); result.put("minutes",JsonInt(if (tutorNumber(preferences,"daily_minutes")>0) { tutorNumber(preferences,"daily_minutes") } else { 10 })); result.put("goal",JsonString(if (tutorText(preferences,"focus_goal").isEmpty()) { "understand" } else { tutorText(preferences,"focus_goal") })); result.put("version",JsonInt(tutorNumber(preferences,"experience_version"))); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
