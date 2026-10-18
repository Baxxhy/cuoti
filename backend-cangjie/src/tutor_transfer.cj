package zhiwei

import stdx.encoding.json.*

func answerTutorTransfer(db: Database, session: JsonObject, snapshot: JsonObject, answer: JsonValue, unknown: Bool, elapsed: Int64): JsonObject {
    let state = tutorObject(session,"state"); let stage = jsonText(session,"stage"); let near = stage == "near_transfer"
    let kind = if (near) { "near" } else { "far" }; let result = JsonObject(); var passed = false; var feedback = ""
    let skipFar = tutorFlag(tutorObject(state,"teaching_policy"),"skip_far_transfer")
    if (near && (state.get("near_confirmation") ?? JsonNull()) is JsonObject) {
        state.put("near_confirmation",JsonNull()); state.put("near_transfer",JsonBool(false)); state.put("assisted",JsonBool(true)); passed = true
        if (skipFar) { completeTutorLearning(db,session,snapshot,true); feedback = "本轮练习完成。" }
        else { session.put("stage",JsonString("far_transfer")); state.put("next_goal",JsonString("换个场景再试一次")); ensureTutorVariant(db,session,snapshot,"far"); feedback = "继续换个场景练习。" }
    } else {
        let rows = db.query("SELECT * FROM variant_questions WHERE id = ? AND session_id = ?",[Some(tutorText(state,"${kind}_variant_id")),Some(jsonText(session,"id"))]).rows
        if (rows.isEmpty()) { throw ApiError(409,"练习已变化，请刷新后继续") }
        let variant = rowJson("variant_questions",rows[0]); var help = unknown
        for (phrase in ["不会写","不知道怎么写","没有思路","没思路","教我写","请教我","不会做"]) { if (tutorAnswerText(answer).contains(phrase)) { help = true } }
        if (help) {
            let guidance = StringBuilder(); guidance.append("可以按这个顺序写："); var count: Int64 = 0
            for (step in tutorArray(variant,"reference_solution").getItems()) { if (count >= 6) { break }; let text = stripWhitespace(tutorAnswerText(step)); if (!text.isEmpty()) { count++; guidance.append("\n${count}. ${text}") } }
            if (count == 0) { count++; guidance.append("\n1. ${if (tutorText(variant,"explanation").isEmpty()) { "先找出已知条件，再列出关系式。" } else { tutorText(variant,"explanation") }}") }
            let expected = tutorAnswerText(variant["answer"])
            if (!expected.isEmpty() && !guidance.toString().contains(expected)) { guidance.append("\n${count+1}. 得到结论：${expected}") }
            state.put("transfer_guidance",JsonString(guidance.toString())); state.put("assisted",JsonBool(true))
            result.put("assistant_content",JsonString(guidance.toString())); result.put("attempt_consumed",JsonBool(false)); result.put("unknown",JsonBool(true))
            feedback = "不会写没关系，先按提示一步步写，这次不计作答次数。"
        } else {
            state.put("transfer_guidance",JsonNull())
            let question = (snapshot["question"] as JsonObject).getOrThrow(); let input = JsonObject()
            input.put("operation",JsonString("grade_answer")); input.put("text",variant["question_text"]); input.put("answer",answer); input.put("expected",variant["answer"])
            input.put("reference_solution",tutorArray(variant,"reference_solution")); input.put("subject",question["subject"]); input.put("question_type",question["question_type"])
            input.put("options",tutorArray(state,"${kind}_variant_options"))
            let grade = algorithmCompute(input); result.put("grading",grade); feedback = tutorText(grade,"feedback")
            if (!tutorFlag(grade,"can_update_learning")) { state.put("last_grading",grade); result.put("attempt_consumed",JsonBool(false)) }
            else {
                passed = tutorFlag(grade,"correct"); let count = tutorNumber(state,"${kind}_attempts")+1; state.put("${kind}_attempts",JsonInt(count)); result.put("attempt_consumed",JsonBool(true))
                db.query("INSERT INTO variant_attempts (id,variant_id,user_id,answer,correct,elapsed_seconds,hint_level,created_at,updated_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(jsonText(variant,"id")),Some(jsonText(session,"user_id")),Some(tutorAnswerText(answer)),Some(if (passed) { "1" } else { "0" }),Some(elapsed.toString()),Some(tutorNumber(session,"hint_level").toString())])
                if (passed) {
                    state.put(stage,JsonBool(true))
                    if (near && !skipFar) { session.put("stage",JsonString("far_transfer")); state.put("next_goal",JsonString("换个场景再试一次")); ensureTutorVariant(db,session,snapshot,"far"); feedback = "相似题做对了，换个场景再试一次。" }
                    else { completeTutorLearning(db,session,snapshot,false); feedback = "练习完成，本轮学习结束。" }
                } else if (count >= 2) {
                    state.put(stage,JsonBool(false)); state.put("assisted",JsonBool(true))
                    if (near && !skipFar) {
                        let confirmation = tutorActivity("near-remediation-${jsonText(variant,"id")}","看懂这一步就继续","根据刚才的讲解，这道题的参考结论是什么？",[("expected",tutorAnswerText(variant["answer"])),("unsure","我还不能确定")],["expected"],"",tutorText(variant,"explanation"))
                        state.put("near_confirmation",confirmation); feedback = "先看简短讲解，确认后继续。"
                    } else { state.put("transfer_insufficient",JsonBool(true)); completeTutorLearning(db,session,snapshot,true); feedback = "本轮学习结束，已安排近期复习。" }
                }
            }
        }
    }
    result.put("passed",JsonBool(passed)); result.put("feedback",JsonString(feedback)); return result
}
