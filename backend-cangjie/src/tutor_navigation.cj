package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

func recordTutorTool(db: Database, sessionId: String, branch: String, name: String, input: JsonObject, output: JsonObject, runResult!: JsonObject=JsonObject()): Unit {
    let result = (JsonValue.fromStr(output.toString()) as JsonObject).getOrThrow(); result.put("branch",JsonString(branch)); for ((key,value) in runResult.getFields()) { result.put(key,value) }; let runId = newId()
    db.query("INSERT INTO agent_runs (id,session_id,agent_name,status,result,created_at,updated_at) VALUES (?,?,'mindtrace_tutor','completed',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(runId),Some(sessionId),Some(result.toString())])
    db.query("INSERT INTO agent_tool_calls (id,agent_run_id,tool_name,input_json,output_json,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(runId),Some(name),Some(input.toString()),Some(output.toString())])
}

public func navigateTutor(context: HttpContext, accounts: Accounts, rewind: Bool): JsonValue {
    requireMethod(context,"POST")
    let parts = context.request.url.path.split("/"); let id = parts[parts.size-2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db)
        let body = if (rewind) { JsonObject() } else { readJson(context) }
        return db.transaction<JsonValue>({ tx =>
            let rows = tx.query("SELECT * FROM tutor_sessions WHERE id = ? AND user_id = ?",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"教学会话不存在或无权访问") }
            let session = rowJson("tutor_sessions",rows[0]); let state = tutorObject(session,"state"); session.put("state",state)
            let snapshot = tutorDataSnapshot(tx,jsonText(session,"question_id"),user["id"])
            let question = (snapshot["question"] as JsonObject).getOrThrow()
            if (jsonText(question,"status") == "archived" || tutorFlag(state,"question_changed")) { throw ApiError(409,"题目已变化或归档，请重新开始学习") }
            let current = canonicalTutorStage(jsonText(session,"stage"))
            let compressed = tutorText(tutorObject(state,"teaching_policy"),"mode") == "compressed"
            var target = ""
            try {
                if (rewind) { target = if (compressed && current == "near_transfer") { "understanding" } else { previousTutorStage(current) } }
                else {
                    if (tutorText(body,"target_stage") != "teach_back") { throw ApiError(422,"只支持进入讲清阶段") }
                    target = transitionTutorStage(current,"understanding_advance",tutorFlag(state,"understanding_passed"))
                }
            } catch (error: IllegalArgumentException) { throw ApiError(409,error.message) }
            let branch = if (rewind) { "rewind_${current}_to_${target}" } else { "understanding_advance" }
            let input = JsonObject(); input.put("from",JsonString(current))
            let output = JsonObject(); output.put("to",JsonString(target))
            let message = "现在请用自己的话讲一遍：用了什么规则，为什么能用，又怎样得到结论。"
            if (!rewind) {
                state.put("next_goal",JsonString("用自己的话说明规则、依据和结论"))
                input.put("event",JsonString("understanding_advance"))
                tx.query("INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,'assistant',?,'teach_back',?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(id),Some(message),Some(##"{"branch":"understanding_advance","explicit_transition":true}"##)])
            } else {
                if (current == "teach_back" || current == "near_transfer") {
                    state.put("teach_back",JsonNull()); state.put("teach_back_passed",JsonNull()); state.put("teach_back_attempts",JsonInt(0))
                }
                if (current == "teach_back") {
                    state.put("understanding_passed",JsonBool(true)); state.put("understood",JsonBool(true)); state.put("next_goal",JsonString("回顾已经理解的关键点"))
                } else {
                    for (key in ["near_transfer","near_confirmation","far_transfer"]) { state.put(key,JsonNull()) }
                    for (key in ["near_attempts","far_attempts"]) { state.put(key,JsonInt(0)) }
                    state.put("next_goal",JsonString(if (current == "near_transfer") { "重新用自己的话说清关键判断" } else { "重新完成一道相似题" }))
                    if (compressed && current == "near_transfer") {
                        for (key in ["understanding_passed","understood","answer_reveal_acknowledged","targeted_check_pending"]) { state.put(key,JsonBool(false)) }
                        state.put("next_goal",JsonString("重新查看答案讲解"))
                    }
                }
                let label = if (target == "understanding") { "理解" } else if (target == "teach_back") { "讲清" } else { "练习" }
                state.put("activity_feedback",JsonString("已返回“${label}”。"))
            }
            state.put("branch",JsonString(branch)); session.put("stage",JsonString(target))
            tx.query("UPDATE tutor_sessions SET stage = ?,state = ?,updated_at = UTC_TIMESTAMP() WHERE id = ?",[Some(target),Some(state.toString()),Some(id)])
            recordTutorTool(tx,id,branch,if (rewind) { "rewind_tutor_stage" } else { "transition_tutor_stage" },input,output)
            if (rewind) {
                let saved = rowJson("tutor_sessions",tx.query("SELECT * FROM tutor_sessions WHERE id = ?",[Some(id)]).rows[0])
                return tutorSessionPayload(tx,accounts,saved,snapshot)
            }
            let result = JsonObject(); result.put("stage",JsonString(target)); result.put("message",JsonString(message)); result.put("next_goal",state["next_goal"])
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
