package zhiwei

import stdx.encoding.base64.*
import stdx.encoding.json.*
import stdx.net.http.*

func validateTutorHandwriting(body: JsonObject, owner: String, sessionId: String, kind!: String = "tutor"): JsonObject {
    let raw = (editText(body.get("handwriting_image_url") ?? JsonString(""),2048,trim: true) as JsonString).getOrThrow().getValue()
    let recognition = body.get("handwriting_recognition") ?? JsonNull(); let result = JsonObject()
    if (raw.isEmpty()) {
        if (!(recognition is JsonNull)) { throw ApiError(422,"手写识别结果缺少对应原图") }
        result.put("image_url",JsonString("")); result.put("recognition",JsonNull()); return result
    }
    let path = raw.split("?",2)[0]; let prefix = "/uploads/answers/${owner}/${kind}/${sessionId}/handwriting-"
    if (!path.startsWith(prefix) || !path.endsWith(".jpg")) { throw ApiError(422,"手写作答图片无效") }
    let suffix = path[prefix.size..path.size-4]
    if (suffix.size != 32) { throw ApiError(422,"手写作答图片无效") }
    for (byte in suffix.toArray()) { if (!((byte >= 48 && byte <= 57) || (byte >= 97 && byte <= 102))) { throw ApiError(422,"手写作答图片无效") } }
    try { readMedia(path[1..]) } catch (_: Exception) { throw ApiError(422,"手写作答图片无效") }
    if (!(recognition is JsonObject) && !(recognition is JsonNull)) { throw ApiError(422,"手写作答识别结果无效") }
    let input = JsonObject(); input.put("operation",JsonString("validate_handwriting")); input.put("recognition",if (recognition is JsonNull) { JsonObject() } else { recognition })
    result.put("image_url",JsonString(path)); result.put("recognition",algorithmCompute(input)); return result
}

public func uploadHandwriting(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db); let upload = readImageUpload(context)
        let kind = upload.fields.get("context_type") ?? ""; let id = upload.fields.get("context_id") ?? ""; let activityId = upload.fields.get("activity_id") ?? ""
        if (kind != "tutor" && kind != "review" && kind != "assignment" && kind != "practice") { throw ApiError(422,"不支持的答题场景") }
        let visible = db.transaction<JsonObject>({ tx =>
            if (kind == "practice") { return practiceHandwritingContext(tx,rowText(user,"id"),upload.fields.get("mistake_id") ?? "",id,upload.fields.get("mode") ?? "reinforce") }
            if (kind == "assignment") {
                let snapshot=assignmentContext(tx,id,requireStudent(user)); requireAssignmentPending(snapshot)
                let question=tutorObject(snapshot,"question"); let result=JsonObject(); result.put("subject",question["subject"]); result.put("text",question["question_text"]); return result
            }
            if (kind == "review") {
                let plans = tx.query("SELECT * FROM review_plans WHERE id=? AND user_id=? AND status='pending'",[Some(id),user["id"]]).rows
                if (plans.isEmpty()) { throw ApiError(404,"待复习题不存在") }
                let question = reviewQuestion(tx,rowJson("review_plans",plans[0]),rowText(user,"id"))
                if (!tutorArray(question,"options").getItems().isEmpty()) { throw ApiError(422,"选择题请直接选择选项") }
                let result = JsonObject(); result.put("subject",question["subject"]); result.put("text",question["question_text"]); return result
            }
            let rows = tx.query("SELECT * FROM tutor_sessions WHERE id = ? AND user_id = ?",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"学习会话不存在") }
            let session = rowJson("tutor_sessions",rows[0]); let snapshot = tutorDataSnapshot(tx,jsonText(session,"question_id"),user["id"])
            let question = (snapshot["question"] as JsonObject).getOrThrow()
            if (tutorFlag(tutorObject(session,"state"),"question_changed") || jsonText(question,"status") == "archived") { throw ApiError(409,"题目已变化或归档，请重新开始学习") }
            let value = tutorActivityForSession(tx,session,snapshot)
            if (!(value is JsonObject)) { throw ApiError(409,"当前练习已经变化，请刷新后重新上传") }
            let activity = (value as JsonObject).getOrThrow()
            if (tutorText(activity,"id") != activityId) { throw ApiError(409,"当前练习已经变化，请刷新后重新上传") }
            let activityType = tutorText(activity,"type")
            if (activityType == "single_choice" || activityType == "multiple_choice" || activityType == "explanation" || activityType == "teach_back") { throw ApiError(422,"当前练习不需要上传手写过程") }
            let result = JsonObject(); result.put("subject",question["subject"]); result.put("text",activity["question"]); return result
        })
        let normalize = JsonObject(); normalize.put("operation",JsonString("normalize")); normalize.put("image_base64",JsonString(toBase64String(upload.bytes)))
        let image = algorithmImage(algorithmCompute(normalize)); let owner = rowText(user,"id")
        let imageId = newId().replace("-",""); let path = "uploads/answers/${owner}/${kind}/${id}/handwriting-${imageId}.jpg"
        writeMedia(path,image)
        let input = JsonObject(); input.put("operation",JsonString("recognize_handwriting")); input.put("image_base64",JsonString(toBase64String(image)))
        input.put("subject",visible["subject"]); input.put("text",visible["text"])
        var computed = JsonObject()
        try { computed = algorithmCompute(input) } catch (_: Exception) { throw ApiError(503,"照片已保留，但暂时无法识别，请稍后重试或使用文字输入") }
        let result = JsonObject(); result.put("image_url",JsonString(accounts.mediaUrl("/"+path))); result.put("recognition",computed["recognition"]); return result
    }
    throw ApiError(503,"数据库暂时不可用")
}
