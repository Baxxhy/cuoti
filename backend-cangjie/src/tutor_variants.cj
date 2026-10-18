package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

func tutorDataSnapshot(db: Database, questionId: String, owner: Option<String>): JsonObject {
    let questions = db.query("SELECT * FROM questions WHERE id = ? AND user_id = ?",[Some(questionId),owner]).rows
    if (questions.isEmpty()) { throw ApiError(404,"题目不存在或无权访问") }
    let snapshot = JsonObject(); snapshot.put("question",rowJson("questions",questions[0]))
    snapshot.put("analysis",firstJson(queryArray(db,"problem_analyses","SELECT * FROM problem_analyses WHERE question_id = ?",questionId)))
    snapshot.put("references",queryArray(db,"reference_steps","SELECT r.* FROM reference_steps r JOIN problem_analyses a ON a.id=r.analysis_id WHERE a.question_id = ? ORDER BY r.step_index,r.id",questionId))
    return snapshot
}

func tutorAnswerText(value: JsonValue): String {
    if (let Some(text) <- (value as JsonString)) { return text.getValue() }
    if (value is JsonNull) { return "" }
    if (let Some(items) <- (value as JsonArray)) {
        let result = StringBuilder(); var first = true
        for (item in items.getItems()) { if (!first) { result.append("、") }; first = false; result.append(tutorAnswerText(item)) }
        return result.toString()
    }
    if (let Some(items) <- (value as JsonObject)) {
        let result = StringBuilder(); var first = true
        for ((key,item) in items.getFields()) { if (!first) { result.append("；") }; first = false; result.append(key+"："+tutorAnswerText(item)) }
        return result.toString()
    }
    return value.toString()
}

func tutorVariantRetrieval(db: Database, snapshot: JsonObject, transfer: String): JsonObject {
    let result=JsonObject(); result.put("references",JsonArray()); result.put("status",JsonString("unavailable"))
    try {
        let question=tutorObject(snapshot,"question"); let mode=if (transfer=="near") { "reinforce" } else { "variation" }
        let excluded=JsonArray(); let usedTexts=HashSet<String>()
        for (row in db.query("SELECT * FROM variant_questions WHERE question_id=?",[sqlValue(question["id"])]).rows) {
            let old=rowJson("variant_questions",row); usedTexts.add(jsonText(old,"question_text"))
            for (id in tutorArray(tutorObject(old,"generation_metadata"),"retrieval_ids").getItems()) { excluded.add(id) }
        }
        let preparation=retrievalPreparation(db,question,snapshot["analysis"],"variant",mode)
        let ranked=retrievalCandidates(db,question,preparation,excluded,"variant",mode); let references=JsonArray()
        for (value in tutorArray(ranked,"references").getItems()) {
            let reference=(value as JsonObject).getOrThrow()
            if (!usedTexts.contains(jsonText(reference,"question_text"))) { references.add(reference) }
        }
        result.put("references",references); result.put("status",JsonString("ok"))
    } catch (_: Exception) { () }
    return result
}

func ensureTutorVariant(db: Database, session: JsonObject, snapshot: JsonObject, transfer: String): JsonObject {
    let state = (session["state"] as JsonObject).getOrThrow(); let sessionId = jsonText(session,"id")
    let existing = db.query("SELECT * FROM variant_questions WHERE id = ? AND session_id = ?",[Some(tutorText(state,transfer+"_variant_id")),Some(sessionId)]).rows
    if (!existing.isEmpty()) {
        let item=rowJson("variant_questions",existing[0]); let question=tutorObject(snapshot,"question")
        let candidate=JsonObject(); for (key in ["question_text","answer","explanation","reference_solution"]) { candidate.put(key,item[key]) }
        let validation=JsonObject(); validation.put("operation",JsonString("validate_variant")); validation.put("text",question["question_text"]); validation.put("subject",question["subject"])
        validation.put("knowledge_points",tutorStringArray(tutorKnowledge(snapshot))); validation.put("variant_candidate",candidate)
        if (tutorFlag(algorithmCompute(validation),"valid")) {
            state.put(transfer+"_validated_variant_id",item["id"])
            db.query("UPDATE tutor_sessions SET state=? WHERE id=?",[Some(state.toString()),Some(sessionId)])
            return item
        }
        let invalidated=tutorArray(state,"invalidated_variant_ids"); invalidated.add(item["id"]); state.put("invalidated_variant_ids",invalidated)
        state.put(transfer+"_variant_id",JsonNull()); state.put(transfer+"_validated_variant_id",JsonNull())
    }
    let question = (snapshot["question"] as JsonObject).getOrThrow(); let questionId = jsonText(question,"id")
    if (jsonText(question,"status") == "archived") { throw ApiError(409,"题目已归档，不能生成新练习") }
    if (tutorFlag(state,"question_changed")) { throw ApiError(409,"题目已变化，请重新开始学习") }
    let points = tutorKnowledge(snapshot); let context = StringBuilder(); context.append(jsonText(question,"question_text"))
    for (point in points) { context.append("；"+point) }
    let diagnoses = db.query("SELECT root_misconception FROM diagnoses WHERE question_id = ? ORDER BY created_at DESC,id DESC LIMIT 1",[Some(questionId)]).rows
    if (!diagnoses.isEmpty()) { context.append("；"+rowText(diagnoses[0],"root_misconception")) }
    let input = JsonObject(); input.put("operation",JsonString("generate_variant")); input.put("text",JsonString(context.toString()))
    input.put("subject",question["subject"]); input.put("question_type",question["question_type"]); input.put("transfer_type",JsonString(transfer))
    let retrieval=tutorVariantRetrieval(db,snapshot,transfer)
    input.put("knowledge_points",tutorStringArray(points)); input.put("variant_references",retrieval["references"])
    let computed = algorithmCompute(input); let generated = (computed["variant"] as JsonObject).getOrThrow()
    let generation = (computed["generation"] as JsonObject).getOrThrow()
    generation.put("retrieval_pipeline",JsonString("bge_m3_qdrant_reranker")); generation.put("retrieval_status",retrieval["status"])
    let id = newId()
    db.query("INSERT INTO variant_questions (id,question_id,session_id,transfer_type,question_text,answer,explanation,reference_solution,verified,generation_metadata,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(id),Some(questionId),Some(sessionId),Some(transfer),sqlValue(generated["question_text"]),sqlValue(generated["answer"]),sqlValue(generated["explanation"]),Some(generated["reference_solution"].toString()),sqlValue(computed["verified"]),Some(generation.toString())])
    state.put(transfer+"_variant_id",JsonString(id)); state.put(transfer+"_validated_variant_id",if (computed["verified"].toString() == "true") { JsonString(id) } else { JsonNull() })
    state.put(transfer+"_attempts",JsonInt(0)); state.put(transfer+"_variant_generation",generation); state.put(transfer+"_variant_options",generated["options"]); state.put("activity_feedback",JsonString(""))
    db.query("UPDATE tutor_sessions SET state = ?,updated_at = UTC_TIMESTAMP() WHERE id = ?",[Some(state.toString()),Some(sessionId)])
    let output = JsonObject(); output.put("variant_id",JsonString(id)); output.put("verified",computed["verified"])
    for ((key,value) in generation.getFields()) { output.put(key,value) }
    let runResult = (JsonValue.fromStr(output.toString()) as JsonObject).getOrThrow(); runResult.put("branch",JsonString(transfer+"_transfer_generated"))
    let toolInput = JsonObject(); toolInput.put("transfer_type",JsonString(transfer)); toolInput.put("knowledge_points",tutorStringArray(points)); toolInput.put("retrieval_pipeline",JsonString("bge_m3_qdrant_reranker"))
    let runId = newId()
    db.query("INSERT INTO agent_runs (id,session_id,agent_name,status,result,created_at,updated_at) VALUES (?,?,'mindtrace_tutor','completed',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(runId),Some(sessionId),Some(runResult.toString())])
    db.query("INSERT INTO agent_tool_calls (id,agent_run_id,tool_name,input_json,output_json,created_at,updated_at) VALUES (?,?,'generate_variant',?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(runId),Some(toolInput.toString()),Some(output.toString())])
    return rowJson("variant_questions",db.query("SELECT * FROM variant_questions WHERE id = ?",[Some(id)]).rows[0])
}

public func tutorVariant(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    let parts = context.request.url.path.split("/"); let id = parts[parts.size-2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db); let body = readJson(context,defaultEmpty: true)
        let transfer = (editText(body.get("transfer_type") ?? JsonString("near"),10) as JsonString).getOrThrow().getValue()
        if (transfer != "near" && transfer != "far") { throw ApiError(422,"迁移类型必须是 near 或 far") }
        return db.transaction<JsonValue>({ tx =>
            let rows = tx.query("SELECT * FROM tutor_sessions WHERE id = ? AND user_id = ?",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"教学会话不存在或无权访问") }
            let session = rowJson("tutor_sessions",rows[0]); let stage = canonicalTutorStage(jsonText(session,"stage"))
            if (stage != transfer+"_transfer") { throw ApiError(409,"当前教学阶段不能生成这类练习") }
            session.put("stage",JsonString(stage))
            let snapshot = tutorDataSnapshot(tx,jsonText(session,"question_id"),user["id"])
            let item = ensureTutorVariant(tx,session,snapshot,transfer); let result = JsonObject()
            for (key in ["id","question_id","session_id","transfer_type","question_text","verified","created_at","updated_at"]) { result.put(key,item[key]) }
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
