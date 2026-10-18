package zhiwei

import stdx.encoding.json.*

// The same admission check is used for new, cached and submitted practice.
func practiceAligned(db: Database, source: JsonObject, preparation: JsonObject, candidates: JsonArray): JsonArray {
    let target=tutorText(preparation,"target_knowledge_id")
    let rows=db.query("SELECT * FROM knowledge_points WHERE id=? AND subject=?",[Some(target),sqlValue(source["subject"])]).rows
    if (rows.isEmpty()) { return JsonArray() }
    let input=JsonObject(); input.put("operation",JsonString("practice_alignment")); input.put("retrieval_source",source)
    input.put("retrieval_target",rowJson("knowledge_points",rows[0])); input.put("retrieval_candidates",candidates)
    return tutorArray(algorithmCompute(input),"checks")
}

func practiceCandidate(question: JsonObject): JsonArray {
    let row=JsonObject(); row.put("question",question); let rows=JsonArray(); rows.add(row); return rows
}

func practiceAdmitted(checks: JsonArray, id: String): Bool {
    for (entry in checks.getItems()) {
        let check=(entry as JsonObject).getOrThrow()
        if (tutorText(check,"id")==id && tutorFlag(check,"aligned")) { return true }
    }
    return false
}

func practiceAlignmentMethod(checks: JsonArray, id: String): String {
    for (entry in checks.getItems()) {
        let check=(entry as JsonObject).getOrThrow()
        if (tutorText(check,"id")==id && tutorFlag(check,"aligned")) { return tutorText(check,"method") }
    }
    return ""
}

func practiceSourceVersion(db: Database, question: JsonObject): String {
    let value=JsonObject(); let id=jsonText(question,"id")
    value.put("question",JsonString(learningSourceFingerprint(db,question)))
    value.put("analysis",firstJson(queryArray(db,"problem_analyses","SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",id)))
    value.put("diagnosis",firstJson(queryArray(db,"diagnoses","SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",id)))
    return sha256(learningFingerprintJson(value).toArray())
}

func practiceProofContext(db: Database, source: JsonObject, preparation: JsonObject, candidate: JsonObject): JsonObject {
    let value=JsonObject(); value.put("policy",JsonInt(1)); value.put("source",JsonString(practiceSourceVersion(db,source)))
    value.put("candidate",JsonString(sha256(learningFingerprintJson(candidate).toArray())))
    let cards=db.query("SELECT * FROM knowledge_points WHERE id=? AND subject=?",[sqlValue(preparation["target_knowledge_id"]),sqlValue(source["subject"])]).rows
    value.put("target",JsonString(if (cards.isEmpty()) { "" } else { sha256(learningFingerprintJson(rowJson("knowledge_points",cards[0])).toArray()) }))
    return value
}

func practiceProofValid(db: Database, source: JsonObject, preparation: JsonObject, candidate: JsonObject, trace: JsonObject): Bool {
    let proof=tutorObject(trace,"alignment_proof"); let method=tutorText(proof,"method")
    return (method=="symbolic_linear" || method=="qwen_grounded_concept") && jsonEquivalent(proof.get("context") ?? JsonNull(),practiceProofContext(db,source,preparation,candidate))
}

func savePracticeProof(db: Database, source: JsonObject, preparation: JsonObject, candidate: JsonObject, trace: JsonObject, method: String): Unit {
    let proof=JsonObject(); proof.put("method",JsonString(method)); proof.put("context",practiceProofContext(db,source,preparation,candidate))
    trace.put("alignment_proof",proof); trace.put("alignment_method",JsonString(method))
}

func currentPracticePreparation(db: Database, question: JsonObject, mode: String): JsonObject {
    let analyses=queryArray(db,"problem_analyses","SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",jsonText(question,"id"))
    return retrievalPreparation(db,question,firstJson(analyses),"practice",mode)
}
