package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

func practicePayload(accounts: Accounts, question: JsonObject, mode: String, trace: JsonObject, points: JsonArray): JsonObject {
    let result=JsonObject(); result.put("question_id",question["id"])
    for (key in ["subject","grade","question_type"]) { result.put(key,question[key]) }
    result.put("stem",question["question_text"]); let images=JsonArray()
    for (index in 0..tutorArray(question,"image_paths").getItems().size) { images.add(JsonString(accounts.mediaUrl("/api/v1/practice/questions/${jsonText(question,"id")}/images/${index}"))) }
    result.put("images",images); let input=JsonObject(); input.put("operation",JsonString("normalize_options")); input.put("raw_options",question["options"])
    result.put("options",algorithmCompute(input)["options"]); result.put("knowledge_points",points)
    let names=tutorArray(trace,"knowledge_match"); let name=if (names.getItems().isEmpty()) { "关键方法" } else { tutorAnswerText(names[0]) }
    result.put("recommendation",JsonString("这道题会继续检查你需要加强的${name}。")); result.put("mode",JsonString(mode)); return result
}

func recommendPractice(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let owner=rowText(user,"id"); let body=readJson(context)
        let id=schoolText(body,"mistake_id","",100,nonempty: true); let mode=practiceMode(body)
        let debug=editBool(body.get("debug") ?? JsonBool(false)).getValue(); let force=editBool(body.get("force_new") ?? JsonBool(false)).getValue()
        let setup=db.transaction<JsonObject>({ tx =>
            let rows=tx.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived'",[Some(id),Some(owner)]).rows
            if (rows.isEmpty()) { throw ApiError(404,"没有找到这道错题") }
            let question=rowJson("questions",rows[0]); let fingerprint=learningSourceFingerprint(tx,question)
            let setup=JsonObject(); setup.put("question",question); setup.put("fingerprint",JsonString(fingerprint))
            let preparation=currentPracticePreparation(tx,question,mode)
            if (tutorText(preparation,"target_knowledge_id").isEmpty()) { throw ApiError(422,"请先分析这道题，确认需要练习的知识点") }
            setup.put("preparation",preparation)
            setup.put("source_version",JsonString(practiceSourceVersion(tx,question)))
            if (!force) {
                let previous=tx.query("SELECT * FROM practice_recommendations WHERE user_id=? AND mistake_id=? AND mode=? ORDER BY created_at DESC LIMIT 1",[Some(owner),Some(id),Some(mode)]).rows
                if (!previous.isEmpty()) {
                    let saved=rowJson("practice_recommendations",previous[0]); let trace=tutorObject(saved,"retrieval_trace"); let qid=jsonText(saved,"dataset_question_id")
                    let attempted=tx.query("SELECT id FROM dataset_practice_attempts WHERE user_id=? AND mistake_id=? AND dataset_question_id=? AND mode=? LIMIT 1",[Some(owner),Some(id),Some(qid),Some(mode)]).rows
                    let questions=tx.query("SELECT * FROM dataset_questions WHERE id=?",[Some(qid)]).rows
                    if (tutorText(trace,"source_question_fingerprint")==fingerprint && tutorText(trace,"target_knowledge_id")==tutorText(preparation,"target_knowledge_id") && attempted.isEmpty() && !questions.isEmpty() && usableRetrievalCandidate(question,rowJson("dataset_questions",questions[0]),"practice")) {
                        let selected=rowJson("dataset_questions",questions[0])
                        var valid=practiceProofValid(tx,question,preparation,selected,trace)
                        if (!valid) {
                            let checks=practiceAligned(tx,question,preparation,practiceCandidate(selected)); valid=practiceAdmitted(checks,qid)
                            if (valid) { savePracticeProof(tx,question,preparation,selected,trace,practiceAlignmentMethod(checks,qid)); tx.query("UPDATE practice_recommendations SET retrieval_trace=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(trace.toString()),sqlValue(saved["id"])]) }
                        }
                        if (valid) {
                            let result=practicePayload(accounts,selected,mode,trace,tutorArray(selected,"knowledge_points"))
                            if (debug) { result.put("debug",trace) }; setup.put("cached",result); return setup
                        }
                    }
                }
            }
            return setup
        })
        if (let Some(cached) <- setup.get("cached")) { return cached }
        let question=tutorObject(setup,"question"); let fingerprint=jsonText(setup,"fingerprint")
        let preparation=tutorObject(setup,"preparation")
        let excluded=JsonArray(); let seen=HashSet<String>()
        for (table in ["dataset_practice_attempts","practice_recommendations"]) {
            for (row in db.query("SELECT dataset_question_id FROM ${table} WHERE user_id=? AND mistake_id=?",[Some(owner),Some(id)]).rows) {
                let qid=rowText(row,"dataset_question_id"); if (!seen.contains(qid)) { seen.add(qid); excluded.add(JsonString(qid)) }
            }
        }
        let ranked=tutorArray(retrievalCandidates(db,question,preparation,excluded,"practice",mode),"ranked")
        let checks=practiceAligned(db,question,preparation,ranked)
        let admitted=JsonArray()
        for (value in ranked.getItems()) { let row=(value as JsonObject).getOrThrow(); if (practiceAdmitted(checks,jsonText(tutorObject(row,"question"),"id"))) { admitted.add(row) } }
        if (admitted.getItems().isEmpty()) { throw ApiError(404,"暂时没有找到能够确认匹配当前知识点的未做题目") }
        return db.transaction<JsonValue>({ tx =>
            let current=tx.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived' FOR UPDATE",[Some(id),Some(owner)]).rows
            if (current.isEmpty() || learningSourceFingerprint(tx,rowJson("questions",current[0]))!=fingerprint) { throw ApiError(409,"题目已修改，请重新获取推荐题") }
            if (practiceSourceVersion(tx,rowJson("questions",current[0]))!=jsonText(setup,"source_version")) { throw ApiError(409,"题目分析或诊断已更新，请重新获取练习") }
            let candidate=(admitted[0] as JsonObject).getOrThrow(); let selected=tutorObject(candidate,"question"); let trace=JsonObject()
            if (tutorText(currentPracticePreparation(tx,rowJson("questions",current[0]),mode),"target_knowledge_id")!=tutorText(preparation,"target_knowledge_id")) { throw ApiError(409,"学习目标已更新，请重新获取练习") }
            let fresh=tx.query("SELECT * FROM dataset_questions WHERE id=? AND subject=? AND usable_for_practice=1",[sqlValue(selected["id"]),sqlValue(question["subject"])]).rows
            if (fresh.isEmpty() || !usableRetrievalCandidate(question,rowJson("dataset_questions",fresh[0]),"practice") || !jsonEquivalent(rowJson("dataset_questions",fresh[0]),selected)) { throw ApiError(409,"推荐题已更新，请重新获取") }
            for (table in ["practice_recommendations","dataset_practice_attempts"]) {
                if (!tx.query("SELECT id FROM ${table} WHERE user_id=? AND mistake_id=? AND dataset_question_id=? LIMIT 1",[Some(owner),Some(id),sqlValue(selected["id"])]).rows.isEmpty()) { throw ApiError(409,"推荐已变化，请重新获取练习题") }
            }
            trace.put("source_question_fingerprint",JsonString(fingerprint))
            trace.put("alignment_method",JsonString(practiceAlignmentMethod(checks,jsonText(selected,"id"))))
            for (key in ["knowledge_match","target_knowledge_id","target_knowledge_name","target_skill","error_match"]) { trace.put(key,preparation[key]) }
            let difficulty=tutorText(selected,"difficulty"); trace.put("difficulty_match",JsonString(if (difficulty.isEmpty()) { "同年级" } else { difficulty }))
            trace.put("question_type_difference",JsonBool(jsonText(selected,"question_type")!=jsonText(question,"question_type")))
            for (key in ["dense_rank","sparse_rank","fusion_rank"]) { trace.put(key,candidate[key]) }
            for (key in ["structure_similarity","reranker_score","mode_score"]) { trace.put(key,tutorObject(candidate,"score_trace")[key]) }
            savePracticeProof(tx,question,preparation,selected,trace,practiceAlignmentMethod(checks,jsonText(selected,"id")))
            tx.query("INSERT INTO practice_recommendations (id,user_id,mistake_id,dataset_question_id,mode,retrieval_rank,retrieval_trace,created_at,updated_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(owner),Some(id),sqlValue(selected["id"]),Some(mode),sqlValue(candidate["fusion_rank"]),Some(trace.toString())])
            let result=practicePayload(accounts,selected,mode,trace,tutorArray(candidate,"knowledge_points")); if (debug) { result.put("debug",trace) }; return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
