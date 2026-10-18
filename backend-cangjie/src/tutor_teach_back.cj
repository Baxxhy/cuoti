package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

// All teach-back evaluation uses the original Python function. This module only
// controls persisted progress, transitions, turns and tool evidence.
func evaluateTutorTeachBack(answer: String,question: JsonObject,points: JsonArray,references: JsonArray): JsonObject {
    let input=JsonObject(); input.put("operation",JsonString("evaluate_teach_back")); input.put("text",JsonString(answer))
    input.put("subject",question["subject"]); input.put("question_type",question["question_type"]); input.put("teach_back_points",points); input.put("reference_solution",references)
    return algorithmCompute(input)
}

func teachBackTutor(context: HttpContext,accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let body=readJson(context)
        let explanation=schoolText(body,"explanation","",12000)
        return db.transaction<JsonValue>({ tx =>
            let rows=tx.query("SELECT * FROM tutor_sessions WHERE id=? AND user_id=? FOR UPDATE",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"教学会话不存在或无权访问") }
            let session=rowJson("tutor_sessions",rows[0]); let stage=canonicalTutorStage(jsonText(session,"stage"))
            if (stage!="teach_back") { throw ApiError(409,"请先完成理解检查并进入讲清阶段") }
            let snapshot=tutorDataSnapshot(tx,jsonText(session,"question_id"),user["id"]); let question=tutorObject(snapshot,"question"); let state=tutorObject(session,"state"); session.put("state",state)
            if (tutorFlag(state,"question_changed") || jsonText(question,"status")=="archived") { throw ApiError(409,"题目已变化或归档，请重新开始学习") }
            let analysis=snapshot.get("analysis") ?? JsonNull()
            let points=if (analysis is JsonObject) { tutorArray((analysis as JsonObject).getOrThrow(),"knowledge_points") } else { tutorArray(question,"knowledge_points") }
            let assessment=evaluateTutorTeachBack(explanation,question,points,tutorStringArray(tutorRowTexts(snapshot["references"])))
            let passed=tutorFlag(assessment,"passed"); let count=tutorNumber(state,"teach_back_attempts")+1; let assisted = !passed && count>=2
            let branch=if (passed) { "teach_back_pass" } else { "teach_back_fail" }; var feedback=jsonText(assessment,"feedback")
            state.put("teach_back",JsonBool(passed)); state.put("teach_back_passed",JsonBool(passed)); state.put("teach_back_attempts",JsonInt(count)); state.put("branch",JsonString(branch))
            state.put("next_goal",JsonString(if (passed || assisted) { "完成一道相似题" } else { "补充一个关键理由" }))
            if (assisted) { state.put("assisted",JsonBool(true)) }
            session.put("stage",JsonString(stage))
            if (passed || assisted) {
                session.put("stage",JsonString("near_transfer")); ensureTutorVariant(tx,session,snapshot,"near")
                if (!passed) { feedback="这次还少一个关键点，我先记录下来，我们继续练一道相似题。" }
            }
            tx.query("UPDATE tutor_sessions SET stage=?,state=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[sqlValue(session["stage"]),Some(state.toString()),Some(id)])
            let userMeta=JsonObject(); userMeta.put("branch",JsonString(branch)); let assistantMeta=JsonObject(); assistantMeta.put("branch",JsonString(branch)); assistantMeta.put("passed",JsonBool(passed))
            for ((role,content,turnStage,metadata) in [("user",explanation,"teach_back",userMeta),("assistant",feedback,jsonText(session,"stage"),assistantMeta)]) {
                tx.query("INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(id),Some(role),Some(content),Some(turnStage),Some(metadata.toString())])
            }
            let input=JsonObject(); input.put("explanation",JsonString(explanation)); input.put("subject",question["subject"])
            let output=JsonObject(); output.put("passed",JsonBool(passed)); output.put("stage",session["stage"]); output.put("matched_concepts",assessment["matched_concepts"])
            recordTutorTool(tx,id,branch,"evaluate_teach_back",input,output)
            let result=JsonObject(); result.put("passed",JsonBool(passed)); result.put("assisted",JsonBool(assisted)); result.put("branch",JsonString(branch)); result.put("stage",session["stage"]); result.put("feedback",JsonString(feedback)); result.put("next_goal",state["next_goal"]); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
