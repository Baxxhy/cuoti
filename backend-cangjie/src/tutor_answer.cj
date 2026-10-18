package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

func tutorMicroPassed(source: JsonObject, answer: JsonValue, question: JsonObject): Bool {
    let expected = tutorArray(source,"correct_answers"); let input = JsonObject()
    input.put("operation",JsonString("grade_answer")); input.put("text",JsonString(if (tutorText(source,"question").isEmpty()) { jsonText(question,"question_text") } else { tutorText(source,"question") }))
    input.put("answer",answer); input.put("expected",if (tutorText(source,"type") == "multiple_choice") { expected } else if (expected.getItems().isEmpty()) { JsonString("") } else { expected[0] })
    input.put("subject",question["subject"]); input.put("question_type",source["type"]); input.put("options",tutorArray(source,"options"))
    let grade = algorithmCompute(input)
    return tutorFlag(grade,"correct") && tutorFlag(grade,"can_update_learning")
}

func tutorAnswerLabel(activity: JsonObject, answer: JsonValue): String {
    let values = if (let Some(items) <- (answer as JsonArray)) { items } else { let array = JsonArray(); array.add(answer); array }
    let text = StringBuilder(); var first = true
    for (value in values.getItems()) {
        let raw = tutorAnswerText(value); var label = raw
        for (option in tutorArray(activity,"options").getItems()) {
            let item = (option as JsonObject).getOrThrow()
            if (tutorText(item,"value") == raw) { label = tutorText(item,"label"); break }
        }
        if (!first) { text.append("、") }; first = false; text.append(label)
    }
    return text.toString()
}

public func answerTutorActivity(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts = context.request.url.path.split("/"); let id = parts[parts.size-3]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db); let body = readJson(context,maxBytes: 2 * 1024 * 1024)
        let answer = body.get("answer") ?? JsonString("")
        if (let Some(items) <- (answer as JsonArray)) {
            if (items.getItems().size > 100) { throw ApiError(422,"选项数量过多") }
            for (item in items.getItems()) { editText(item,12000) }
        } else { editText(answer,12000) }
        let working = (editText(body.get("working") ?? JsonString(""),12000,trim: true) as JsonString).getOrThrow().getValue()
        let elapsedNumber = editNumber(body.get("elapsed_seconds") ?? JsonInt(0))
        if (elapsedNumber < 0.0 || elapsedNumber > 2147483647.0) { throw ApiError(422,"作答时长无效") }
        let elapsed = Int64(elapsedNumber)
        let unknown = editBool(body.get("unknown") ?? JsonBool(false)).toString() == "true" || tutorAnswerText(answer) == "__unknown__"
        return db.transaction<JsonValue>({ tx =>
            let rows = tx.query("SELECT * FROM tutor_sessions WHERE id = ? AND user_id = ?",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"教学会话不存在或无权访问") }
            let session = rowJson("tutor_sessions",rows[0]); let state = tutorObject(session,"state"); session.put("state",state)
            let stage = canonicalTutorStage(jsonText(session,"stage")); session.put("stage",JsonString(stage))
            if (stage != "understanding" && stage != "teach_back" && stage != "near_transfer" && stage != "far_transfer") { throw ApiError(409,"当前阶段不能继续作答") }
            let snapshot = tutorDataSnapshot(tx,jsonText(session,"question_id"),user["id"]); let question = (snapshot["question"] as JsonObject).getOrThrow()
            if (tutorFlag(state,"question_changed") || jsonText(question,"status") == "archived") { throw ApiError(409,"题目已变化或归档，请重新开始学习") }
            let current = tutorActivityForSession(tx,session,snapshot)
            if (!(current is JsonObject)) { throw ApiError(409,"当前小任务已经变化，请刷新后继续") }
            let activity = (current as JsonObject).getOrThrow()
            if (tutorText(body,"activity_id") != jsonText(activity,"id")) { throw ApiError(409,"当前小任务已经变化，请刷新后继续") }
            let handwriting = validateTutorHandwriting(body,rowText(user,"id"),id)
            var passed = false; var feedback = ""; var transfer = JsonObject()
            let compressed = tutorText(tutorObject(state,"teaching_policy"),"mode") == "compressed"
            if (stage == "near_transfer" || stage == "far_transfer") {
                transfer = answerTutorTransfer(tx,session,snapshot,answer,unknown,elapsed); passed = tutorFlag(transfer,"passed"); feedback = tutorText(transfer,"feedback")
            } else if (stage == "teach_back") {
                let assessment = evaluateTutorTeachBack(stripWhitespace(tutorAnswerText(answer)),question,tutorStringArray(tutorKnowledge(snapshot)),tutorStringArray(tutorRowTexts(snapshot["references"])))
                passed = tutorFlag(assessment,"passed"); let count = tutorNumber(state,"teach_back_attempts")+1; state.put("teach_back_attempts",JsonInt(count))
                if (passed || count >= 2) {
                    state.put("teach_back",JsonBool(passed)); state.put("teach_back_passed",JsonBool(passed))
                    if (!passed) { state.put("assisted",JsonBool(true)) }
                    session.put("stage",JsonString("near_transfer")); state.put("next_goal",JsonString("完成一道相似题"))
                    feedback = if (passed) { "讲清楚了，接着做一道相似题。" } else { "这次还少一个关键点，我先记录下来，我们继续练一道相似题。" }
                } else { feedback = jsonText(assessment,"feedback") }
            } else if (compressed && tutorText(activity,"type") == "explanation") {
                state.put("answer_reveal_acknowledged",JsonBool(true)); passed = true
                if (tutorAnswerText(answer) == "need_help") { state.put("targeted_check_pending",JsonBool(true)); feedback = "只确认一个易错点。" }
                else {
                    state.put("understanding_passed",JsonBool(true)); state.put("understood",JsonBool(true)); state.put("near_transfer",JsonNull())
                    session.put("stage",JsonString("near_transfer")); state.put("next_goal",JsonString("做一道相似题")); feedback = "好，直接练一道。"
                }
            } else if (compressed && tutorFlag(state,"targeted_check_pending")) {
                let source = tutorObject(tutorObject(state,"teaching_brief"),"check")
                passed = !unknown && tutorMicroPassed(source,answer,question)
                let attempts = tutorObject(state,"activity_attempts"); let key = tutorText(source,"id"); let count = tutorNumber(attempts,key)+1
                attempts.put(key,JsonInt(count)); state.put("activity_attempts",attempts)
                if (passed || count >= 2 || unknown) {
                    if (!passed) { state.put("assisted",JsonBool(true)) }
                    state.put("targeted_check_pending",JsonBool(false)); state.put("understanding_passed",JsonBool(true)); state.put("understood",JsonBool(true))
                    state.put("near_transfer",JsonNull()); session.put("stage",JsonString("near_transfer")); state.put("next_goal",JsonString("做一道相似题"))
                    feedback = if (passed) { "答对了，练一道类似的。" } else { "记住这个条件，我们直接练一道。" }
                } else { let hint = tutorText(source,"hint"); feedback = shortTitle(if (hint.isEmpty()) { "再用刚才的关键条件判断一次。" } else { hint },70) }
            } else {
                let plan = tutorArray(state,"understanding_plan"); let index = tutorNumber(state,"understanding_index")
                if (index < 0 || index >= plan.getItems().size) { throw ApiError(409,"活动计划已变化，请刷新") }
                let source = (plan[index] as JsonObject).getOrThrow()
                if (tutorFlag(state,"understanding_confirmation")) {
                    state.put("assisted",JsonBool(true)); state.put("understanding_confirmation",JsonBool(false)); state.put("understanding_index",JsonInt(index+1)); passed = true
                    feedback = "记住这个判断方法，我们继续下一个小问题。"
                } else {
                    passed = !unknown && tutorMicroPassed(source,answer,question)
                    let attempts = tutorObject(state,"activity_attempts"); let key = jsonText(source,"id"); let count = tutorNumber(attempts,key)+1
                    attempts.put(key,JsonInt(count)); state.put("activity_attempts",attempts)
                    if (passed) { state.put("understanding_index",JsonInt(index+1)); feedback = "答对了，我们继续。" }
                    else if (unknown || count >= 2) { state.put("understanding_confirmation",JsonBool(true)); state.put("assisted",JsonBool(true)); feedback = "先看一个最短讲解，再确认一次就继续。" }
                    else { feedback = tutorText(source,"hint"); if (!feedback.isEmpty()) { feedback = shortTitle(feedback,70) } }
                }
                if (tutorNumber(state,"understanding_index") >= plan.getItems().size) {
                    state.put("understanding_passed",JsonBool(true)); state.put("understood",JsonBool(true)); state.put("next_goal",JsonString("用自己的话说一遍")); feedback = "已经抓住这个关键点。"
                }
            }
            if (jsonText(session,"stage") == "near_transfer") { ensureTutorVariant(tx,session,snapshot,"near") }
            state.put("activity_feedback",JsonString(feedback)); state.put("branch",JsonString("activity_${jsonText(session,"stage")}_${if (passed) { "pass" } else { "continue" }}"))
            tx.query("UPDATE tutor_sessions SET stage = ?,state = ?,turn_count = turn_count+1,updated_at = UTC_TIMESTAMP() WHERE id = ?",[Some(jsonText(session,"stage")),Some(state.toString()),Some(id)])
            let userMeta = JsonObject(); userMeta.put("activity_id",activity["id"]); userMeta.put("activity_type",activity["type"])
            userMeta.put("working",JsonString(if (working.isEmpty()) { "" } else { shortTitle(working,500) })); userMeta.put("handwriting_image_url",handwriting["image_url"]); userMeta.put("handwriting_recognition",handwriting["recognition"]); userMeta.put("grading",tutorObject(transfer,"grading"))
            if (let Some(consumed) <- transfer.get("attempt_consumed")) { userMeta.put("attempt_consumed",consumed) }; if (tutorFlag(transfer,"unknown")) { userMeta.put("unknown",JsonBool(true)) }
            let assistantMeta = JsonObject(); assistantMeta.put("activity_id",activity["id"]); assistantMeta.put("passed",JsonBool(passed)); assistantMeta.put("assisted",JsonBool(tutorFlag(state,"assisted")))
            for ((role,content,metadata) in [("user",tutorAnswerLabel(activity,answer),userMeta),("assistant",if (tutorText(transfer,"assistant_content").isEmpty()) { feedback } else { tutorText(transfer,"assistant_content") },assistantMeta)]) {
                tx.query("INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(id),Some(role),Some(content),Some(jsonText(session,"stage")),Some(metadata.toString())])
            }
            let saved = rowJson("tutor_sessions",tx.query("SELECT * FROM tutor_sessions WHERE id = ?",[Some(id)]).rows[0])
            return tutorSessionPayload(tx,accounts,saved,snapshot)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
