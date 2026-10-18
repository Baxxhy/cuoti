package zhiwei

import std.collection.*
import stdx.encoding.base64.*
import stdx.encoding.json.*
import stdx.net.http.*

func analysisSnapshot(db: Database, id: String, owner: Option<String>): JsonObject {
    let rows = db.query("SELECT * FROM questions WHERE id = ? AND user_id = ? FOR UPDATE", [Some(id),owner]).rows
    if (rows.isEmpty() || rowText(rows[0],"status") == "archived") { throw ApiError(404,"题目不存在或已归档") }
    let question = rowJson("questions",rows[0])
    if (question["confirmed"].toString() != "true" || stripWhitespace(jsonText(question,"question_text")).isEmpty()) { throw ApiError(409,"请先核对并确认题目文字，再开始分析") }
    let result = JsonObject()
    result.put("question",question)
    result.put("work",firstJson(queryArray(db,"student_works","SELECT * FROM student_works WHERE question_id = ? ORDER BY created_at DESC,id DESC LIMIT 1",id)))
    result.put("steps",queryArray(db,"student_steps","SELECT s.* FROM student_steps s WHERE work_id = (SELECT id FROM student_works WHERE question_id = ? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id",id))
    result.put("assets",queryArray(db,"question_assets","SELECT * FROM question_assets WHERE question_id = ? AND kind IN ('crop','question_figure') ORDER BY created_at,id",id))
    result.put("analysis",firstJson(queryArray(db,"problem_analyses","SELECT * FROM problem_analyses WHERE question_id = ?",id)))
    return result
}

func analysisFingerprint(snapshot: JsonObject): JsonArray {
    let result = JsonArray()
    let question = (snapshot["question"] as JsonObject).getOrThrow()
    for (key in ["question_text","subject","grade","question_type","student_answer","options","knowledge_points","confirmed","status"]) { result.getItems().add(question[key]) }
    // These values are constructed from the same ordered SQL columns on each read.
    for (key in ["work","steps","assets","analysis"]) { result.getItems().add(snapshot[key]) }
    return result
}

public func analyzeQuestion(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    let parts = context.request.url.path.split("/")
    let id = parts[parts.size - 2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db)
        let snapshot = db.transaction<JsonObject>({ tx => analysisSnapshot(tx,id,user["id"]) })
        let expected = analysisFingerprint(snapshot)
        let question = (snapshot["question"] as JsonObject).getOrThrow()
        let input = JsonObject()
        input.put("operation",JsonString("analyze")); input.put("text",question["question_text"])
        for (key in ["subject","question_type","student_answer","options"]) { input.put(key,question[key]) }
        input.put("grade",if (question["grade"] is JsonNull) { JsonString("") } else { question["grade"] })
        let steps = JsonArray()
        for (item in (snapshot["steps"] as JsonArray).getOrThrow().getItems()) { steps.getItems().add((item as JsonObject).getOrThrow()["text"]) }
        input.put("student_steps",steps)
        let images = JsonArray(); let seen = HashSet<String>()
        for (item in (snapshot["assets"] as JsonArray).getOrThrow().getItems()) {
            let path = jsonText((item as JsonObject).getOrThrow(),"path")
            if (!seen.contains(path)) { images.getItems().add(JsonString(toBase64String(readMedia(path)))); seen.add(path) }
        }
        input.put("images_base64",images)
        let computed = algorithmCompute(input)
        let analysis = (computed["analysis"] as JsonObject).getOrThrow()
        let references = (analysis["reference_steps"] as JsonArray).getOrThrow().getItems()
        let valid = (computed["reference_math_valid"] as JsonArray).getOrThrow().getItems()
        if (valid.size != references.size || stripWhitespace(jsonText(analysis,"final_answer")).isEmpty()) { throw ApiError(503,"分析结果不完整") }
        return db.transaction<JsonValue>({ tx =>
            let current = analysisSnapshot(tx,id,user["id"])
            if (!jsonEquivalent(analysisFingerprint(current), expected)) { throw ApiError(409,"题目或作答已变化，请重新分析") }
            invalidateQuestionLearning(tx,id)
            let analysisId = newId()
            tx.query("INSERT INTO problem_analyses (id,question_id,subject,problem_type,known_conditions,goal,knowledge_points,prerequisites,final_answer,verified,raw_result,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [Some(analysisId),Some(id),Some(jsonText(analysis,"subject")),Some(jsonText(analysis,"problem_type")),Some(analysis["known_conditions"].toString()),Some(jsonText(analysis,"goal")),Some(analysis["knowledge_points"].toString()),Some(analysis["prerequisites"].toString()),Some(jsonText(analysis,"final_answer")),Some(if (analysis["answer_verified"].toString() == "true") { "1" } else { "0" }),Some(analysis.toString())])
            for (index in 0..references.size) {
                let text = (references[index] as JsonString).getOrThrow().getValue()
                let equation = text.contains("=")
                tx.query("INSERT INTO reference_steps (id,analysis_id,step_index,text,expression,explanation,math_valid,uses_condition,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [Some(newId()),Some(analysisId),Some(index.toString()),Some(text),if (equation) { Some(text) } else { None },Some(if (equation) { "由题目条件进行等价变形" } else { "推理步骤" }),Some(if (valid[index].toString() == "true") { "1" } else { "0" }),Some(if (index == 0) { "1" } else { "0" })])
            }
            syncKnowledgeLinks(tx,question,analysis)
            tx.query("UPDATE questions SET status = 'analyzed',updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(id)])
            let result = rowJson("problem_analyses",tx.query("SELECT * FROM problem_analyses WHERE id = ?",[Some(analysisId)]).rows[0])
            result.put("reference_steps",analysis["reference_steps"])
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
