package zhiwei

import std.convert.*
import stdx.encoding.json.*
import stdx.net.http.*

func tutorFlag(state: JsonObject, key: String): Bool { return (state.get(key) ?? JsonBool(false)).toString() == "true" }
func tutorText(state: JsonObject, key: String): String {
    return if (let Some(text) <- ((state.get(key) ?? JsonNull()) as JsonString)) { text.getValue() } else { "" }
}
func tutorNumber(state: JsonObject, key: String): Int64 {
    return if (let Some(value) <- ((state.get(key) ?? JsonNull()) as JsonInt)) { Int64.parse(value.toString()) } else { 0 }
}
func tutorObject(state: JsonObject, key: String): JsonObject {
    return (state.get(key) ?? JsonObject()) as JsonObject ?? JsonObject()
}
func tutorArray(state: JsonObject, key: String): JsonArray {
    return (state.get(key) ?? JsonArray()) as JsonArray ?? JsonArray()
}

func tutorActivityForSession(db: Database, session: JsonObject, snapshot: JsonObject): JsonValue {
    let state = (session["state"] as JsonObject).getOrThrow(); let stage = jsonText(session,"stage")
    let feedback = tutorText(state,"activity_feedback")
    if (stage == "understanding" && !tutorFlag(state,"understanding_passed")) {
        if (tutorText(tutorObject(state,"teaching_policy"),"mode") == "compressed") {
            if (!tutorFlag(state,"answer_reveal_acknowledged")) {
                return JsonValue.fromStr(##"{"id":"answer-reveal","type":"explanation","title":"先看清这次错在哪","question":"","options":[],"attempt":1,"max_attempts":1,"feedback":"","teaching":""}"##)
            }
            if (tutorFlag(state,"targeted_check_pending")) {
                let check = tutorObject(tutorObject(state,"teaching_brief"),"check")
                return publicTutorActivity(check,tutorNumber(tutorObject(state,"activity_attempts"),tutorText(check,"id"))+1,feedback: feedback)
            }
            return JsonNull()
        }
        let plan = tutorArray(state,"understanding_plan").getItems()
        if (plan.isEmpty()) { return JsonNull() }
        let rawIndex = tutorNumber(state,"understanding_index")
        let index = if (rawIndex < 0) { 0 } else if (rawIndex >= plan.size) { plan.size-1 } else { rawIndex }
        let source = (plan[index] as JsonObject).getOrThrow()
        if (tutorFlag(state,"understanding_confirmation")) {
            let confirmation = tutorActivity(jsonText(source,"id")+"-confirmation","确认一下就继续",
                "解题时，需要依据题目条件一步一步检查，对吗？",[("yes","对，需要检查条件"),("unsure","我还不确定")],["yes"],"",tutorText(source,"teaching"))
            return publicTutorActivity(confirmation,1,feedback: feedback)
        }
        return publicTutorActivity(source,tutorNumber(tutorObject(state,"activity_attempts"),jsonText(source,"id"))+1,feedback: feedback)
    }
    if (stage == "teach_back") {
        let item = tutorActivity("teach-back","用一句话讲清楚","如果再遇到这种题，你会先看什么、再怎么判断？",[],[],"","")
        item.put("type",JsonString("teach_back")); item.put("sentence_starter",JsonString("我会先看……"))
        let points = tutorKnowledge(snapshot); let keywords = JsonArray(); var cube = false
        for (text in points) { if (text.contains("正方体") || text.contains("相对面")) { cube = true } }
        for (text in tutorRowTexts(snapshot["references"])) { if (text.contains("正方体") || text.contains("相对面")) { cube = true } }
        if (cube) { for (word in ["相间","Z字两端","折叠"]) { keywords.add(JsonString(word)) } }
        else { for (index in 0..points.size) { if (index >= 3) { break }; keywords.add(JsonString(points[index])) } }
        item.put("keywords",keywords)
        return publicTutorActivity(item,tutorNumber(state,"teach_back_attempts")+1,feedback: feedback)
    }
    if (stage == "near_transfer" || stage == "far_transfer") {
        if (stage == "near_transfer" && !(tutorObject(state,"near_confirmation").getFields().isEmpty())) {
            return publicTutorActivity(tutorObject(state,"near_confirmation"),1,feedback: feedback)
        }
        let transfer = if (stage == "near_transfer") { "near" } else { "far" }
        let variant = ensureTutorVariant(db,session,snapshot,transfer); let options = tutorArray(state,transfer+"_variant_options")
        let question = (snapshot["question"] as JsonObject).getOrThrow()
        let policyType = tutorText(tutorObject(state,"teaching_policy"),"question_type")
        let kind = if (policyType.isEmpty()) { jsonText(question,"question_type") } else { policyType }
        let activityType = if (!options.getItems().isEmpty()) { if (kind == "multiple_choice") { "multiple_choice" } else { "single_choice" } } else if (kind == "fill_blank") { "short_answer" } else { "variant" }
        let publicOptions = JsonArray()
        for (value in options.getItems()) {
            if (let Some(option) <- (value as JsonObject)) {
                let label = tutorText(option,"label"); let text = tutorText(option,"text"); let item = JsonObject()
                item.put("value",JsonString(label)); item.put("label",JsonString(if (label.isEmpty()) { text } else if (text.isEmpty()) { label } else { label+"  "+text })); publicOptions.add(item)
            }
        }
        let item = tutorActivity(transfer+"-variant-"+jsonText(variant,"id"),if (transfer == "near") { "相似题练习" } else { "换个场景试一试" },jsonText(variant,"question_text"),[],[],"",tutorText(state,"transfer_guidance"))
        item.put("type",JsonString(activityType)); item.put("variant_id",variant["id"]); item.put("options",publicOptions)
        item.put("input_mode",JsonString(if (activityType == "multiple_choice") { "multiple_choice" } else if (activityType == "single_choice") { "choice" } else { kind }))
        if (!tutorText(state,"transfer_guidance").isEmpty()) { item.put("teaching_title",JsonString("我们一步一步写")) }
        return publicTutorActivity(item,tutorNumber(state,transfer+"_attempts")+1,feedback: feedback)
    }
    return JsonNull()
}

func tutorSessionPayload(db: Database, accounts: Accounts, session: JsonObject, snapshot: JsonObject): JsonObject {
    let state = (session["state"] as JsonObject).getOrThrow(); let question = (snapshot["question"] as JsonObject).getOrThrow()
    let result = (JsonValue.fromStr(session.toString()) as JsonObject).getOrThrow()
    let stage = jsonText(session,"stage")
    result.put("state",publicTutorProgress(state)); result.put("stage_status",JsonString(if (stage == "finished") { "completed" } else if (stage == "understanding" && tutorFlag(state,"understanding_passed")) { "passed" } else { "active" }))
    result.put("activity",tutorActivityForSession(db,session,snapshot)); result.put("assisted",JsonBool(tutorFlag(state,"assisted")))
    result.put("teaching_policy",state.get("teaching_policy") ?? JsonValue.fromStr(##"{"mode":"full"}"##))
    result.put("answer_reveal",state.get("answer_reveal") ?? JsonNull()); result.put("completion_summary",JsonString(tutorText(state,"completion_summary")))
    let points = tutorKnowledge(snapshot); let title = StringBuilder()
    for (index in 0..points.size) { if (index >= 2) { break }; if (index > 0) { title.append(" · ") }; title.append(points[index]) }
    result.put("knowledge_title",JsonString(if (title.toString().isEmpty()) { jsonText(question,"title") } else { title.toString() }))
    result.put("visualization_available",JsonBool(!(tutorVisualization(jsonText(question,"subject"),jsonText(question,"question_type"),points) is JsonNull)))
    let publicQuestion = JsonObject(); publicQuestion.put("id",question["id"]); publicQuestion.put("text",question["question_text"])
    let figures = db.query("SELECT path FROM question_assets WHERE question_id = ? AND kind IN ('question_figure','crop') ORDER BY (kind = 'question_figure') DESC,created_at DESC,id DESC LIMIT 1",[Some(jsonText(question,"id"))]).rows
    publicQuestion.put("figure_url",if (figures.isEmpty()) { JsonNull() } else { JsonString(accounts.mediaUrl("/"+rowText(figures[0],"path"))) })
    result.put("question",publicQuestion); result.put("turns",queryArray(db,"tutor_turns","SELECT * FROM tutor_turns WHERE session_id = ? ORDER BY created_at,id",jsonText(session,"id")))
    for (value in tutorArray(result,"turns").getItems()) {
        let turn = (value as JsonObject).getOrThrow(); let metadata = tutorObject(turn,"metadata_json"); let path = tutorText(metadata,"handwriting_image_url")
        if (!path.isEmpty()) { metadata.put("handwriting_image_url",JsonString(accounts.mediaUrl(path))) }
    }
    return result
}

public func readTutor(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let parts = context.request.url.path.split("/"); let id = parts[parts.size-1]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let rows = tx.query("SELECT * FROM tutor_sessions WHERE id = ? AND user_id = ?",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"教学会话不存在或无权访问") }
            let session = rowJson("tutor_sessions",rows[0]); let questionId = jsonText(session,"question_id")
            let snapshot = tutorDataSnapshot(tx,questionId,user["id"])
            let state = tutorObject(session,"state"); session.put("state",state)
            session.put("stage",JsonString(canonicalTutorStage(jsonText(session,"stage"))))
            if (!state.getFields().contains("understanding_passed")) { state.put("understanding_passed",JsonBool(false)) }
            if (!state.getFields().contains("assisted")) { state.put("assisted",JsonBool(false)) }
            if (tutorText(tutorObject(state,"teaching_policy"),"mode") == "compressed" && !tutorObject(state,"teaching_brief").getFields().isEmpty()) {
                for (key in ["answer_reveal_acknowledged","targeted_check_pending"]) {
                    if (!state.getFields().contains(key)) { state.put(key,JsonBool(false)) }
                }
            } else if (tutorArray(state,"understanding_plan").getItems().isEmpty()) {
                let question = (snapshot["question"] as JsonObject).getOrThrow()
                state.put("understanding_plan",buildUnderstandingPlan(jsonText(question,"question_text"),jsonText(question,"subject"),jsonText(question,"question_type"),tutorKnowledge(snapshot),tutorRowTexts(snapshot["references"])))
                state.put("understanding_index",JsonInt(0)); state.put("activity_attempts",JsonObject())
            }
            tx.query("UPDATE tutor_sessions SET stage = ?,state = ? WHERE id = ?",[Some(jsonText(session,"stage")),Some(state.toString()),Some(id)])
            return tutorSessionPayload(tx,accounts,session,snapshot)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
