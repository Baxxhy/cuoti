package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

func publicTutorSession(session: JsonObject): JsonObject {
    let result=(JsonValue.fromStr(session.toString()) as JsonObject).getOrThrow()
    result.put("state",publicTutorProgress(tutorObject(session,"state"))); return result
}

func finishTutor(context: HttpContext,accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); readJson(context,defaultEmpty:true)
        return db.transaction<JsonValue>({ tx =>
            let rows=tx.query("SELECT * FROM tutor_sessions WHERE id=? AND user_id=? FOR UPDATE",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"教学会话不存在或无权访问") }
            let session=rowJson("tutor_sessions",rows[0]); session.put("stage",JsonString(canonicalTutorStage(jsonText(session,"stage"))))
            if (jsonText(session,"stage")!="finished") { throw ApiError(409,"请先完成讲清、相似题和综合应用") }
            let result=JsonObject()
            if (jsonText(session,"status")=="completed") {
                result.put("session",publicTutorSession(session)); result.put("mastery",JsonNull())
                let plans=tx.query("SELECT * FROM review_plans WHERE user_id=? AND question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",[user["id"],sqlValue(session["question_id"])]).rows
                result.put("review",if (plans.isEmpty()) { JsonNull() } else { rowJson("review_plans",plans[0]) }); return result
            }
            let snapshot=tutorDataSnapshot(tx,jsonText(session,"question_id"),user["id"]); let state=tutorObject(session,"state"); session.put("state",state)
            if (tutorFlag(state,"question_changed") || jsonText(tutorObject(snapshot,"question"),"status")=="archived") { throw ApiError(409,"题目已变化或归档，请重新开始学习") }
            let insufficient=tutorFlag(state,"transfer_insufficient") || (state.get("far_transfer") ?? JsonNull()).toString()=="false"
            let learning=completeTutorLearning(tx,session,snapshot,insufficient)
            tx.query("UPDATE tutor_sessions SET stage=?,state=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[sqlValue(session["stage"]),Some(state.toString()),Some(id)])
            let saved=rowJson("tutor_sessions",tx.query("SELECT * FROM tutor_sessions WHERE id=?",[Some(id)]).rows[0])
            result.put("session",publicTutorSession(saved)); result.put("mastery",learning["mastery"]); result.put("review",learning["review"]); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
