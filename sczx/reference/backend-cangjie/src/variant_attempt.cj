package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

func variantAttempt(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let body=readJson(context)
        let answer=optionalText(body,"answer","",12000)
        let elapsedValue=editNumber(body.get("elapsed_seconds") ?? JsonInt(0))
        if (elapsedValue<0.0 || elapsedValue>2147483647.0) { throw ApiError(422,"作答时长无效") }
        return db.transaction<JsonValue>({ tx =>
            let variants=tx.query("SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND s.user_id=?",[Some(id),user["id"]]).rows
            if (variants.isEmpty()) { throw ApiError(404,"迁移题不存在或无权访问") }
            let variant=rowJson("variant_questions",variants[0]); let sessionId=jsonText(variant,"session_id")
            let session=rowJson("tutor_sessions",tx.query("SELECT * FROM tutor_sessions WHERE id=?",[Some(sessionId)]).rows[0])
            let state=tutorObject(session,"state"); session.put("state",state)
            let transfer=jsonText(variant,"transfer_type"); let stage=canonicalTutorStage(jsonText(session,"stage")); session.put("stage",JsonString(stage))
            if (stage!="${transfer}_transfer") { throw ApiError(409,"这道练习与当前教学阶段不匹配") }
            let current=tutorText(state,"${transfer}_variant_id")
            if (!current.isEmpty() && current!=id) { throw ApiError(409,"这道练习已经变化，请刷新") }
            let snapshot=tutorDataSnapshot(tx,jsonText(session,"question_id"),user["id"]); let question=tutorObject(snapshot,"question")
            if (tutorFlag(state,"question_changed") || jsonText(question,"status")=="archived") { throw ApiError(409,"题目已变化或归档，请重新开始学习") }
            let hintValue=editNumber(body.get("hint_level") ?? session["hint_level"])
            if (hintValue<0.0 || hintValue>2147483647.0) { throw ApiError(422,"提示等级无效") }
            let input=JsonObject(); input.put("operation",JsonString("grade_answer")); input.put("text",variant["question_text"]); input.put("answer",JsonString(answer)); input.put("expected",variant["answer"])
            input.put("reference_solution",tutorArray(variant,"reference_solution")); input.put("subject",question["subject"]); input.put("question_type",question["question_type"])
            let grading=algorithmCompute(input); let decisive=tutorFlag(grading,"can_update_learning"); let correct=tutorFlag(grading,"correct")
            var feedback=jsonText(grading,"feedback"); let branch="${transfer}_transfer_${if (!decisive) { "review_required" } else if (correct) { "pass" } else { "fail" }}"
            var attempt: JsonValue=JsonNull()
            if (decisive) {
                let attemptId=newId()
                tx.query("INSERT INTO variant_attempts (id,variant_id,user_id,answer,correct,elapsed_seconds,hint_level,created_at,updated_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(attemptId),Some(id),user["id"],Some(answer),sqlValue(grading["correct"]),Some(Int64(elapsedValue).toString()),Some(Int64(hintValue).toString())])
                attempt=rowJson("variant_attempts",tx.query("SELECT * FROM variant_attempts WHERE id=?",[Some(attemptId)]).rows[0])
                let count=tutorNumber(state,"${transfer}_attempts")+1; state.put("${transfer}_attempts",JsonInt(count)); state.put("branch",JsonString(branch))
                if (transfer=="near" && correct) { state.put("near_transfer",JsonBool(true)); session.put("stage",JsonString("far_transfer")); ensureTutorVariant(tx,session,snapshot,"far") }
                else if (transfer=="near" && count>=2) {
                    state.put("near_transfer",JsonBool(false)); state.put("assisted",JsonBool(true))
                    let explanation=if (tutorText(variant,"explanation").isEmpty()) { "先对照题目条件，再按顺序完成关键步骤。" } else { tutorText(variant,"explanation") }
                    state.put("near_confirmation",tutorActivity("near-remediation-${id}","看懂这一步就继续","根据刚才的讲解，这道题的参考结论是什么？",[("expected",tutorAnswerText(variant["answer"])),("unsure","我还不能确定")],["expected"],"",explanation))
                    feedback="先看这道题的简短讲解，再完成一个简单确认。"
                } else if (transfer=="far" && (correct || count>=2)) {
                    state.put("far_transfer",JsonBool(correct))
                    if (!correct) { state.put("transfer_insufficient",JsonBool(true)); state.put("assisted",JsonBool(true)) }
                    completeTutorLearning(tx,session,snapshot,!correct)
                    if (!correct) { feedback="这次换一种题目还不稳定，本轮先结束，并提高后续复习优先级。" }
                }
                tx.query("UPDATE tutor_sessions SET stage=?,state=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[sqlValue(session["stage"]),Some(state.toString()),Some(sessionId)])
            }
            let userMeta=JsonObject(); userMeta.put("branch",JsonString(branch)); userMeta.put("variant_id",JsonString(id))
            let assistantMeta=JsonObject(); assistantMeta.put("branch",JsonString(branch))
            if (!decisive) { userMeta.put("grading",grading); userMeta.put("attempt_consumed",JsonBool(false)); assistantMeta.put("grading_verdict",grading["verdict"]) }
            else { assistantMeta.put("correct",JsonBool(correct)) }
            for ((role,content,turnStage,metadata) in [("user",answer,"${transfer}_transfer",userMeta),("assistant",feedback,jsonText(session,"stage"),assistantMeta)]) {
                tx.query("INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(sessionId),Some(role),Some(content),Some(turnStage),Some(metadata.toString())])
            }
            let result=JsonObject(); result.put("attempt",attempt); result.put("correct",if (decisive) { JsonBool(correct) } else { JsonNull() }); result.put("branch",JsonString(branch)); result.put("stage",session["stage"]); result.put("feedback",JsonString(feedback)); result.put("grading",grading)
            if (decisive) {
                let toolInput=JsonObject(); toolInput.put("variant_id",JsonString(id)); toolInput.put("answer",JsonString(answer))
                let toolOutput=JsonObject(); toolOutput.put("correct",JsonBool(correct)); toolOutput.put("stage",session["stage"]); recordTutorTool(tx,sessionId,branch,"grade_answer",toolInput,toolOutput)
            }
            for ((name,table) in [("mastery","mastery_states"),("misconception","misconception_states")]) {
                let rows=if (decisive) { tx.query("SELECT * FROM ${table} WHERE user_id=? ORDER BY updated_at DESC,id DESC LIMIT 1",[user["id"]]).rows } else { tx.query("SELECT * FROM ${table} WHERE 1=0").rows }
                result.put(name,if (rows.isEmpty()) { JsonNull() } else { rowJson(table,rows[0]) })
            }
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
