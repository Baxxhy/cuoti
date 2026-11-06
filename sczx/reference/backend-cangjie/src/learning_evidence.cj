package zhiwei

import stdx.encoding.json.*

func learningKnowledgePoint(db: Database, question: JsonObject, preferred!: String = "", includeAnalysis!: Bool = true): String {
    var point=stripWhitespace(preferred)
    if (point.isEmpty()) { point=cognitionFirstLabel(question["knowledge_points"]) }
    if (point.isEmpty() && includeAnalysis) {
        let analyses=db.query("SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1",[Some(jsonText(question,"id"))]).rows
        if (!analyses.isEmpty()) { point=cognitionFirstLabel(rowJson("problem_analyses",analyses[0])["knowledge_points"]) }
    }
    if (point.isEmpty()) { point=stripWhitespace(tutorText(question,"title")) }
    if (point.isEmpty()) { point=stripWhitespace(tutorText(question,"subject"))+"·"+tutorText(question,"question_type") }
    return point
}

// Python computes unchanged arithmetic; Cangjie alone reads and writes business data.
func applyLearningEvidence(db: Database, owner: String, question: JsonObject, evidence: JsonObject, preferred!: String = "", includeAnalysis!: Bool = true, computeTimeoutSeconds!: Int64 = 200): JsonObject {
    let questionId=jsonText(question,"id"); let subject=stripWhitespace(jsonText(question,"subject"))
    let point=learningKnowledgePoint(db,question,preferred: preferred,includeAnalysis: includeAnalysis)
    let diagnoses=db.query("SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",[Some(questionId)]).rows
    let diagnosis=if (diagnoses.isEmpty()) { JsonObject() } else { rowJson("diagnoses",diagnoses[0]) }
    let rawCode=stripWhitespace(tutorText(diagnosis,"error_type")); let code=if (rawCode.isEmpty() || ["exact","equivalent","branch_solution"].contains(rawCode)) { "unclassified" } else { rawCode }
    let rawLabel=stripWhitespace(tutorText(diagnosis,"root_misconception")); let label=if (rawLabel.isEmpty()) { code } else { rawLabel }
    let oldMastery=db.query("SELECT * FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? ORDER BY updated_at DESC,id DESC LIMIT 1",[Some(owner),Some(subject),Some(point)]).rows
    let oldMistake=db.query("SELECT * FROM misconception_states WHERE user_id=? AND subject=? AND code=? ORDER BY updated_at DESC,id DESC LIMIT 1",[Some(owner),Some(subject),Some(code)]).rows
    let beforeMastery: JsonValue=if (oldMastery.isEmpty()) { JsonNull() } else { rowJson("mastery_states",oldMastery[0]) }
    let beforeMistake: JsonValue=if (oldMistake.isEmpty()) { JsonNull() } else { rowJson("misconception_states",oldMistake[0]) }
    let mastery=JsonObject(); let mistake=JsonObject()
    for ((key,fallback) in [("mastery_score",0.0),("evidence_count",0.0),("confidence",0.0),("near_transfer_rate",0.0),("far_transfer_rate",0.0),("forgetting_risk",0.5)]) {
        mastery.put(key,if (beforeMastery is JsonObject) { (beforeMastery as JsonObject).getOrThrow()[key] } else { if (key=="evidence_count") { JsonInt(0) } else { JsonFloat(fallback) } })
    }
    mastery.put("update_reason",JsonString(""))
    for ((key,fallback) in [("probability",0.5),("evidence_count",1.0),("related_question_count",1.0)]) {
        mistake.put(key,if (beforeMistake is JsonObject) { (beforeMistake as JsonObject).getOrThrow()[key] } else { if (key=="probability") { JsonFloat(fallback) } else { JsonInt(1) } })
    }
    for (key in ["label","status","successful_strategy","failed_strategy"]) { mistake.put(key,if (beforeMistake is JsonObject) { (beforeMistake as JsonObject).getOrThrow()[key] } else { JsonString(if (key=="label") { label } else if (key=="status") { "active" } else { "" }) }) }
    let input=JsonObject(); input.put("operation",JsonString("cognition_update")); input.put("mastery_values",mastery); input.put("misconception_values",mistake); input.put("learning_evidence",evidence); input.put("misconception_label",JsonString(label))
    let computed=algorithmCompute(input,timeoutSeconds:computeTimeoutSeconds); let nextMastery=tutorObject(computed,"mastery"); let nextMistake=tutorObject(computed,"misconception")
    let masteryId=if (oldMastery.isEmpty()) { newId() } else { rowText(oldMastery[0],"id") }
    let mistakeId=if (oldMistake.isEmpty()) { newId() } else { rowText(oldMistake[0],"id") }
    if (oldMastery.isEmpty()) { db.query("INSERT INTO mastery_states (id,user_id,subject,knowledge_point,mastery_score,confidence,evidence_count,near_transfer_rate,far_transfer_rate,forgetting_risk,update_reason,created_at,updated_at) VALUES (?,?,?,?,0,0,0,0,0,0.5,'',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(masteryId),Some(owner),Some(subject),Some(point)]) }
    if (oldMistake.isEmpty()) { db.query("INSERT INTO misconception_states (id,user_id,subject,code,label,probability,evidence_count,status,related_question_count,successful_strategy,failed_strategy,first_seen_at,created_at,updated_at) VALUES (?,?,?,?,?,0.5,1,'active',1,'','',UTC_TIMESTAMP(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(mistakeId),Some(owner),Some(subject),Some(code),Some(label)]) }
    db.query("UPDATE mastery_states SET mastery_score=?,confidence=?,evidence_count=?,near_transfer_rate=?,far_transfer_rate=?,forgetting_risk=?,update_reason=?,last_evidence_at=UTC_TIMESTAMP(),updated_at=UTC_TIMESTAMP() WHERE id=?",[sqlValue(nextMastery["mastery_score"]),sqlValue(nextMastery["confidence"]),sqlValue(nextMastery["evidence_count"]),sqlValue(nextMastery["near_transfer_rate"]),sqlValue(nextMastery["far_transfer_rate"]),sqlValue(nextMastery["forgetting_risk"]),sqlValue(nextMastery["update_reason"]),Some(masteryId)])
    db.query("UPDATE misconception_states SET probability=?,evidence_count=?,related_question_count=?,label=?,status=?,successful_strategy=?,failed_strategy=?,last_seen_at=UTC_TIMESTAMP(),updated_at=UTC_TIMESTAMP() WHERE id=?",[sqlValue(nextMistake["probability"]),sqlValue(nextMistake["evidence_count"]),sqlValue(nextMistake["related_question_count"]),sqlValue(nextMistake["label"]),sqlValue(nextMistake["status"]),sqlValue(nextMistake["successful_strategy"]),sqlValue(nextMistake["failed_strategy"]),Some(mistakeId)])
    evidence.put("memory_source",memoryEvidenceSource(db,question,evidence,masteryId,mistakeId))
    for ((kind,key,oldValue,newValue) in [("mastery",point,mastery["mastery_score"],nextMastery["mastery_score"]),("misconception",code,mistake["probability"],nextMistake["probability"])]) { db.query("INSERT INTO cognitive_updates (id,user_id,question_id,entity_type,entity_key,old_value,new_value,evidence,reason,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(owner),Some(questionId),Some(kind),Some(key),sqlValue(oldValue),sqlValue(newValue),Some(evidence.toString()),sqlValue(nextMastery["update_reason"])]) }
    let result=JsonObject(); result.put("mastery_before",beforeMastery); result.put("misconception_before",beforeMistake); result.put("mastery_after",rowJson("mastery_states",db.query("SELECT * FROM mastery_states WHERE id=?",[Some(masteryId)]).rows[0])); result.put("misconception_after",rowJson("misconception_states",db.query("SELECT * FROM misconception_states WHERE id=?",[Some(mistakeId)]).rows[0])); return result
}
