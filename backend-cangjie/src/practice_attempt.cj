package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

func practiceMode(body: JsonObject): String {
    let mode=schoolText(body,"mode","",30)
    if (mode!="reinforce" && mode!="variation") { throw ApiError(422,"请选择有效的练习模式") }
    return mode
}

func attemptPractice(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let body=readJson(context)
        let owner=rowText(user,"id"); let mistakeId=schoolText(body,"mistake_id","",100); let id=schoolText(body,"question_id","",100); let mode=practiceMode(body)
        let answer=body.get("student_answer") ?? { => throw ApiError(422,"请提交作答") }()
        let duration=paperInteger(body.get("duration_seconds") ?? JsonInt(0),0,7200)
        return db.transaction<JsonValue>({ tx =>
            let mistakes=tx.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived' FOR UPDATE",[Some(mistakeId),Some(owner)]).rows
            if (mistakes.isEmpty()) { throw ApiError(404,"没有找到这道错题") }
            let mistake=rowJson("questions",mistakes[0]); let questions=tx.query("SELECT * FROM dataset_questions WHERE id=? FOR UPDATE",[Some(id)]).rows
            if (questions.isEmpty() || rowText(questions[0],"usable_for_auto_grade")!="1") { throw ApiError(422,"这道题不能自动判分") }
            let question=rowJson("dataset_questions",questions[0])
            if (!tx.query("SELECT id FROM dataset_practice_attempts WHERE user_id=? AND mistake_id=? AND dataset_question_id=? AND mode=? FOR UPDATE",[Some(owner),Some(mistakeId),Some(id),Some(mode)]).rows.isEmpty()) { throw ApiError(409,"这道练习已经完成，请换一道题继续练习") }
            let handwriting=validateTutorHandwriting(body,owner,id,kind: "practice")
            let served=practiceServed(tx,owner,mistake,id,mode); let trace=tutorObject(served,"retrieval_trace")
            let preparation=currentPracticePreparation(tx,mistake,mode)
            if (!usableRetrievalCandidate(mistake,question,"practice") || tutorText(trace,"target_knowledge_id").isEmpty() || tutorText(trace,"target_knowledge_id")!=tutorText(preparation,"target_knowledge_id")) { throw ApiError(409,"学习目标或题目资格已变化，请重新获取练习") }
            if (!practiceProofValid(tx,mistake,preparation,question,trace)) {
                let checks=practiceAligned(tx,mistake,preparation,practiceCandidate(question))
                if (!practiceAdmitted(checks,id)) { throw ApiError(409,"这道练习与当前学习目标不匹配，请重新获取练习；本次未更新学习记录") }
                savePracticeProof(tx,mistake,preparation,question,trace,practiceAlignmentMethod(checks,id))
            }
            let input=JsonObject(); input.put("operation",JsonString("grade_answer")); input.put("text",question["question_text"]); input.put("answer",answer); input.put("expected",question["answer"])
            input.put("subject",question["subject"]); input.put("question_type",question["question_type"]); input.put("options",question["options"])
            let solution=JsonArray(); for (line in jsonText(question,"solution").split("\n")) { let clean=stripWhitespace(line); if (!clean.isEmpty()) { solution.add(JsonString(clean)) } }; input.put("reference_solution",solution)
            let grading=algorithmCompute(input); let decisive=tutorFlag(grading,"can_update_learning")
            let target=tutorText(trace,"target_knowledge_id")
            let knowledgeRows=tx.query("SELECT * FROM knowledge_points WHERE id=? AND subject=? FOR UPDATE",[Some(target),sqlValue(mistake["subject"])]).rows
            if (knowledgeRows.isEmpty() || rowText(knowledgeRows[0],"name")!=tutorText(preparation,"target_knowledge_name")) { throw ApiError(409,"练习知识点已变化，请重新获取练习") }
            let knowledge=if (knowledgeRows.isEmpty()) { JsonObject() } else { rowJson("knowledge_points",knowledgeRows[0]) }
            let preferred=tutorText(knowledge,"name"); let point=learningKnowledgePoint(tx,mistake,preferred: preferred,includeAnalysis: false)
            let old=tx.query("SELECT mastery_score FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? LIMIT 1",[Some(owner),Some(stripWhitespace(jsonText(mistake,"subject"))),Some(point)]).rows
            let before: JsonValue=if (old.isEmpty()) { JsonFloat(0.0) } else { rowJson("mastery_states",old[0])["mastery_score"] }
            var mastery: JsonValue=JsonNull()
            if (decisive) {
                let sources=tx.query("SELECT `key` FROM dataset_sources WHERE id=?",[sqlValue(question["dataset_source_id"])]).rows
                let source=if (sources.isEmpty()) { "unknown" } else { rowText(sources[0],"key") }
                let details=(JsonValue.fromStr(grading.toString()) as JsonObject).getOrThrow(); details.put("independent_answer",JsonBool(true)); details.put("handwriting_image_url",JsonString(accounts.mediaUrl(jsonText(handwriting,"image_url")))); details.put("handwriting_recognition",handwriting["recognition"])
                details.put("alignment_method",tutorObject(trace,"alignment_proof")["method"]); details.put("target_knowledge_name",preparation["target_knowledge_name"])
                details.put("alignment_proof",trace["alignment_proof"])
                let practiceAttemptId=newId()
                tx.query("INSERT INTO dataset_practice_attempts (id,user_id,mistake_id,dataset_question_id,source_dataset,knowledge_id,mode,student_answer,correct,duration_seconds,grading_details,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(practiceAttemptId),Some(owner),Some(mistakeId),Some(id),Some(source),if (knowledgeRows.isEmpty()) { None } else { sqlValue(knowledge["id"]) },Some(mode),Some(answer.toString()),sqlValue(grading["correct"]),Some(duration.toString()),Some(details.toString())])
                let evidence=JsonObject(); evidence.put(if (mode=="reinforce") { "near_transfer" } else { "far_transfer" },grading["correct"]); evidence.put("hint_level",JsonInt(0)); evidence.put("strategy",JsonString("independent_dataset_practice")); evidence.put("dataset_question_id",JsonString(id)); evidence.put("practice_attempt_id",JsonString(practiceAttemptId))
                let learning=applyLearningEvidence(tx,owner,mistake,evidence,preferred: preferred,includeAnalysis: false); mastery=tutorObject(learning,"mastery_after")["mastery_score"]
            }
            let result=JsonObject(); result.put("correct",if (decisive) { grading["correct"] } else { JsonNull() })
            for (key in ["verdict","can_update_learning","confidence","evidence","feedback"]) { result.put(key,grading[key]) }
            result.put("answer",question["answer"]); result.put("solution",question["solution"]); result.put("mastery_before",before); result.put("mastery",mastery); result.put("grading_method",grading["method"]); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
