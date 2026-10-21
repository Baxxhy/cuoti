package zhiwei

import stdx.encoding.json.*

func generatedPracticePayload(question: JsonObject, variant: JsonObject): JsonObject {
    let meta=tutorObject(variant,"generation_metadata"); let result=JsonObject()
    result.put("question_id",variant["id"]); result.put("stem",variant["question_text"])
    result.put("subject",question["subject"]); result.put("grade",question["grade"])
    result.put("question_type",meta["question_type"]); result.put("options",tutorArray(meta,"options"))
    result.put("images",JsonArray()); result.put("mode",meta["mode"]); result.put("generated",JsonBool(true))
    result.put("recommendation",JsonString("根据这道错题练习相同的方法"))
    return result
}

func generatedPractice(db: Database, owner: String, question: JsonObject, mode: String, force: Bool): JsonObject {
    let version=practiceSourceVersion(db,question); let questionId=jsonText(question,"id")
    let rows=db.query("SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE s.user_id=? AND v.question_id=? AND s.stage='standalone_practice' ORDER BY v.created_at DESC LIMIT 20",[Some(owner),Some(questionId)]).rows
    var previous: Option<JsonObject>=None
    for (row in rows) {
        let item=rowJson("variant_questions",row); let meta=tutorObject(item,"generation_metadata")
        if (tutorText(meta,"source_version")==version && tutorText(meta,"mode")==mode && tutorFlag(item,"verified")) {
            if (previous.isNone()) { previous=Some(item) }
            if (!force) {
                let result=generatedPracticePayload(question,item)
                let sessions=db.query("SELECT state FROM tutor_sessions WHERE id=?",[sqlValue(item["session_id"])]).rows
                if (!sessions.isEmpty()) {
                    let state=(JsonValue.fromStr(rowText(sessions[0],"state")) as JsonObject).getOrThrow()
                    if (let Some(receipt) <- state.get("receipt")) { result.put("previous_result",receipt); result.put("previous_answer",state["answer"]) }
                }
                return result
            }
        }
    }
    let input=JsonObject(); input.put("operation",JsonString("generate_practice"))
    let original=StringBuilder(); original.append(tutorText(question,"question_text")); original.append("\n选项："+tutorArray(question,"options").toString()); original.append("\n年级："+tutorText(question,"grade"))
    if (let Some(old) <- previous) { original.append("\n请勿重复此前练习："+tutorText(old,"question_text")) }
    input.put("text",JsonString(original.toString())); input.put("subject",question["subject"])
    input.put("question_type",question["question_type"]); input.put("transfer_type",JsonString(if (mode=="variation") { "far" } else { "near" }))
    let snapshot=tutorDataSnapshot(db,questionId,Some(owner)); input.put("knowledge_points",tutorStringArray(tutorKnowledge(snapshot)))
    var computed=JsonObject()
    try { computed=algorithmCompute(input) } catch (_: ApiError) { () }
    if (!tutorFlag(computed,"verified")) {
        if (let Some(old) <- previous) {
            let result=generatedPracticePayload(question,old); result.put("recommendation",JsonString("再练一次，巩固这道题的方法")); return result
        }
        throw ApiError(503,"类似题暂未通过核对，请稍后重试。原错题和学习记录已保留。")
    }
    let generated=tutorObject(computed,"variant"); let meta=tutorObject(computed,"generation")
    meta.put("options",tutorArray(generated,"options")); meta.put("mode",JsonString(mode)); meta.put("source_version",JsonString(version))
    meta.put("question_type",JsonString(if (tutorArray(generated,"options").getItems().isEmpty()) { "综合题" } else { tutorText(question,"question_type") }))
    return db.transaction<JsonObject>({ tx =>
        let current=tx.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived' FOR UPDATE",[Some(questionId),Some(owner)]).rows
        if (current.isEmpty() || practiceSourceVersion(tx,rowJson("questions",current[0]))!=version) { throw ApiError(409,"原题已更新，请重新获取练习") }
        let sid=newId(); let vid=newId()
        tx.query("INSERT INTO tutor_sessions (id,user_id,question_id,stage,hint_level,turn_count,mastery_score,state,status,created_at,updated_at) VALUES (?,?,?,'standalone_practice',0,0,0,JSON_OBJECT(),'standalone',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(sid),Some(owner),Some(questionId)])
        tx.query("INSERT INTO variant_questions (id,question_id,session_id,transfer_type,question_text,answer,explanation,reference_solution,verified,generation_metadata,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,1,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(vid),Some(questionId),Some(sid),Some(if (mode=="variation") { "far" } else { "near" }),sqlValue(generated["question_text"]),sqlValue(generated["answer"]),sqlValue(generated["explanation"]),Some(generated["reference_solution"].toString()),Some(meta.toString())])
        return generatedPracticePayload(question,rowJson("variant_questions",tx.query("SELECT * FROM variant_questions WHERE id=?",[Some(vid)]).rows[0]))
    })
}

func attemptGeneratedPractice(db: Database, owner: String, mistake: JsonObject, variant: JsonObject, mode: String, answer: JsonValue, duration: Int64): JsonObject {
    let meta=tutorObject(variant,"generation_metadata"); let id=jsonText(variant,"id")
    if (tutorText(meta,"mode")!=mode || tutorText(meta,"source_version")!=practiceSourceVersion(db,mistake)) { throw ApiError(409,"原题或练习目标已更新，请重新获取练习") }
    let input=JsonObject(); input.put("operation",JsonString("grade_answer")); input.put("text",variant["question_text"]); input.put("answer",answer); input.put("expected",variant["answer"])
    input.put("subject",mistake["subject"]); input.put("question_type",meta["question_type"]); input.put("options",tutorArray(meta,"options")); input.put("reference_solution",variant["reference_solution"])
    let states=db.query("SELECT state FROM tutor_sessions WHERE id=? FOR UPDATE",[sqlValue(variant["session_id"])]).rows
    let previousState=if (states.isEmpty()) { JsonObject() } else { (JsonValue.fromStr(rowText(states[0],"state")) as JsonObject).getOrThrow() }
    if (jsonEquivalent(previousState.get("answer") ?? JsonNull(),answer) && tutorFlag(tutorObject(previousState,"receipt"),"can_update_learning")) { return tutorObject(previousState,"receipt") }
    let grading=algorithmCompute(input); let decisive=tutorFlag(grading,"can_update_learning") && tutorFlag(variant,"verified")
    let answerSeen=tutorFlag(previousState,"answer_revealed")
    let prior=db.query("SELECT id FROM variant_attempts WHERE variant_id=? AND user_id=? LIMIT 1",[Some(id),Some(owner)]).rows
    let point=learningKnowledgePoint(db,mistake)
    let old=db.query("SELECT mastery_score FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? LIMIT 1",[Some(owner),sqlValue(mistake["subject"]),Some(point)]).rows
    let before: JsonValue=if (old.isEmpty()) { JsonFloat(0.0) } else { rowJson("mastery_states",old[0])["mastery_score"] }
    let saved=JsonObject(); saved.put("answer",answer); saved.put("grading",grading); saved.put("duration_seconds",JsonInt(duration)); saved.put("answer_revealed",JsonBool(true))
    db.query("UPDATE tutor_sessions SET state=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(saved.toString()),sqlValue(variant["session_id"])])
    var mastery: JsonValue=JsonNull()
    if (decisive) {
        let aid=newId()
        db.query("INSERT INTO variant_attempts (id,variant_id,user_id,answer,correct,elapsed_seconds,hint_level,created_at,updated_at) VALUES (?,?,?,?,?,?,0,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(aid),Some(id),Some(owner),Some(tutorAnswerText(answer)),sqlValue(grading["correct"]),Some(duration.toString())])
        // Repeated cached exercises remain usable but do not inflate mastery.
        if (prior.isEmpty() && !answerSeen) {
            let evidence=JsonObject(); evidence.put(if (mode=="reinforce") { "near_transfer" } else { "far_transfer" },grading["correct"]); evidence.put("hint_level",JsonInt(0)); evidence.put("strategy",JsonString("generated_practice")); evidence.put("variant_id",JsonString(id)); evidence.put("practice_attempt_id",JsonString(aid))
            mastery=tutorObject(applyLearningEvidence(db,owner,mistake,evidence),"mastery_after").get("mastery_score") ?? JsonNull()
        }
    }
    let result=JsonObject()
    for (key in ["verdict","confidence","evidence","feedback"]) { result.put(key,grading[key]) }
    result.put("correct",if (decisive) { grading["correct"] } else { JsonNull() }); result.put("can_update_learning",JsonBool(decisive))
    if (answerSeen) { result.put("learning_note",JsonString("已看过参考答案，这次练习不重复计入掌握情况。")) }
    result.put("answer",variant["answer"]); result.put("solution",variant["explanation"]); result.put("mastery_before",before); result.put("mastery",mastery); result.put("grading_method",grading["method"])
    saved.put("receipt",result)
    db.query("UPDATE tutor_sessions SET state=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(saved.toString()),sqlValue(variant["session_id"])])
    return result
}
