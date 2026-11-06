package zhiwei

import std.collection.*
import std.env.*
import std.convert.*
import stdx.encoding.json.*
import stdx.net.http.*

// Keep Python's sorted JSON separators so recommendations survive switching backends.
func learningFingerprintJson(value: JsonValue): String {
    let output=StringBuilder()
    if (let Some(object) <- (value as JsonObject)) {
        let keys=ArrayList<String>(); for ((key,_) in object.getFields()) { keys.add(key) }
        let ordered=keys.toArray()
        for (i in 0..ordered.size) { for (j in i+1..ordered.size) { if (ordered[j]<ordered[i]) { let swap=ordered[i]; ordered[i]=ordered[j]; ordered[j]=swap } } }
        output.append("{"); var first=true
        for (key in ordered) { if (!first) { output.append(", ") }; first=false; output.append(JsonString(key).toString()); output.append(": "); output.append(learningFingerprintJson(object[key])) }
        output.append("}"); return output.toString()
    }
    if (let Some(array) <- (value as JsonArray)) {
        output.append("["); var first=true
        for (item in array.getItems()) { if (!first) { output.append(", ") }; first=false; output.append(learningFingerprintJson(item)) }
        output.append("]"); return output.toString()
    }
    return value.toString()
}

func learningSourceFingerprint(db: Database, question: JsonObject): String {
    let source=JsonObject()
    for (key in ["question_text","student_answer","subject","grade","title","formulas","options","question_type","knowledge_points"]) { source.put(key,question[key]) }
    let works=JsonArray()
    for (row in db.query("SELECT id FROM student_works WHERE question_id=? ORDER BY id",[Some(jsonText(question,"id"))]).rows) { works.add(JsonString(rowText(row,"id"))) }
    source.put("student_work_revisions",works)
    return sha256(learningFingerprintJson(source).toArray())
}

func practiceServed(db: Database, owner: String, mistake: JsonObject, questionId: String, mode: String): JsonObject {
    let rows=db.query("SELECT * FROM practice_recommendations WHERE user_id=? AND mistake_id=? AND dataset_question_id=? AND mode=? ORDER BY created_at DESC LIMIT 1",[Some(owner),Some(jsonText(mistake,"id")),Some(questionId),Some(mode)]).rows
    if (rows.isEmpty()) { throw ApiError(409,"请先获取推荐题再作答") }
    let served=rowJson("practice_recommendations",rows[0])
    if (tutorText(tutorObject(served,"retrieval_trace"),"source_question_fingerprint")!=learningSourceFingerprint(db,mistake)) { throw ApiError(409,"题目或推荐已更新，请重新获取推荐题再提交") }
    return served
}

func practiceHandwritingContext(db: Database, owner: String, mistakeId: String, questionId: String, mode: String): JsonObject {
    let mistakes=db.query("SELECT * FROM questions WHERE id=? AND user_id=?",[Some(mistakeId),Some(owner)]).rows
    let generated=db.query("SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND v.question_id=? AND s.user_id=? AND s.stage='standalone_practice'",[Some(questionId),Some(mistakeId),Some(owner)]).rows
    if (!mistakes.isEmpty() && !generated.isEmpty()) {
        let variant=rowJson("variant_questions",generated[0]); let meta=tutorObject(variant,"generation_metadata")
        let mistake=rowJson("questions",mistakes[0])
        if (tutorText(meta,"mode")!=mode || tutorText(meta,"source_version")!=practiceSourceVersion(db,mistake)) { throw ApiError(409,"原题已更新，请重新获取练习") }
        if (!tutorArray(meta,"options").getItems().isEmpty()) { throw ApiError(422,"选择题请直接选择选项") }
        let result=JsonObject(); result.put("subject",mistake["subject"]); result.put("text",variant["question_text"]); return result
    }
    let questions=db.query("SELECT * FROM dataset_questions WHERE id=?",[Some(questionId)]).rows
    if (mistakes.isEmpty() || questions.isEmpty()) { throw ApiError(404,"没有找到这道练习题") }
    let question=rowJson("dataset_questions",questions[0]); practiceServed(db,owner,rowJson("questions",mistakes[0]),questionId,mode)
    if (!tutorArray(question,"options").getItems().isEmpty()) { throw ApiError(422,"选择题请直接选择选项") }
    let result=JsonObject(); result.put("subject",question["subject"]); result.put("text",question["question_text"]); return result
}

func servePracticeImage(context: HttpContext, accounts: Accounts): Unit {
    try {
        if (context.request.method!="GET" && context.request.method!="HEAD") { throw ApiError(405,"请求方法不支持") }
        if (!accounts.validMedia(context)) { throw ApiError(403,"资源链接已失效，请返回页面刷新") }
        let parts=context.request.url.path.split("/"); let id=parts[parts.size-3]
        let index=try { Int64.parse(parts[parts.size-1]) } catch (_: Exception) { throw ApiError(422,"图片序号无效") }
        var stored=""
        try (db=Database.fromEnvironment()) {
            let rows=db.query("SELECT * FROM dataset_questions WHERE id=?",[Some(id)]).rows
            if (rows.isEmpty()) { throw ApiError(404,"图片不存在") }
            let paths=tutorArray(rowJson("dataset_questions",rows[0]),"image_paths")
            if (index<0 || index>=paths.getItems().size) { throw ApiError(404,"图片不存在") }
            stored=(paths[index] as JsonString).getOrThrow().getValue()
        }
        let working=getWorkingDirectory().toString()
        let project=if (working.endsWith("/backend-cangjie")) { working[..working.size-16] } else { working }
        let configured=getVariable("CANGJIE_QUESTION_BANK_ROOT") ?? "data/question_bank_assets"
        let root=if (configured.startsWith("/")) { configured } else { project+"/"+configured }
        let relative=if (stored.startsWith("/")) { stored } else { project+"/"+stored }
        if (!relative.startsWith(root+"/")) { throw ApiError(404,"图片不存在") }
        serveMedia(context,accounts,storageRoot: Some(root),storagePath: Some(relative[root.size+1..]))
    } catch (error: ApiError) { let body=JsonObject(); body.put("detail",JsonString(error.message)); jsonResponse(context,body,status: error.status) }
    catch (_: Exception) { let body=JsonObject(); body.put("detail",JsonString("图片暂时不可用")); jsonResponse(context,body,status: 503) }
}

// Persist the result, but renew expiring image links whenever it is read.
func refreshedPracticeReceipt(accounts: Accounts, question: JsonObject, receipt: JsonObject): JsonObject {
    for ((key,value) in datasetSolutionImages(question,accounts).getFields()) { receipt.put(key,value) }
    return receipt
}
