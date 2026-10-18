package zhiwei

import stdx.encoding.json.*

// Educational source stamp. Display metadata and progress status are excluded;
// archive/confirmation are checked separately when a memory is read.
func memoryQuestionVersion(db: Database, question: JsonObject): String {
    let data=JsonArray()
    for (key in ["id","user_id","subject","grade","question_type","question_text","student_answer","options","knowledge_points"]) { data.add(question[key]) }
    let id=jsonText(question,"id")
    data.add(firstJson(queryArray(db,"student_works","SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",id)))
    data.add(queryArray(db,"student_steps","SELECT * FROM student_steps WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id",id))
    data.add(queryArray(db,"question_assets","SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id",id))
    data.add(firstJson(queryArray(db,"problem_analyses","SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1",id)))
    data.add(queryArray(db,"reference_steps","SELECT r.* FROM reference_steps r JOIN problem_analyses a ON a.id=r.analysis_id WHERE a.question_id=? ORDER BY r.step_index,r.id",id))
    data.add(queryArray(db,"teacher_questions","SELECT * FROM teacher_questions WHERE question_id=? ORDER BY id",id))
    return sha256(data.toString().toArray())
}

func memoryDatasetVersion(db: Database, id: String): String {
    let rows=db.query("SELECT * FROM dataset_questions WHERE id=? AND usable_for_auto_grade=1",[Some(id)]).rows
    if (rows.isEmpty()) { return "" }
    return sha256(rowJson("dataset_questions",rows[0]).toString().toArray())
}

func memoryEvidenceSource(db: Database, question: JsonObject, evidence: JsonObject, masteryId: String, mistakeId: String): JsonObject {
    let result=JsonObject(); result.put("rule_version",JsonString("learning-memory-v1")); result.put("question_version",JsonString(memoryQuestionVersion(db,question)))
    result.put("mastery_id",JsonString(masteryId)); result.put("misconception_id",JsonString(mistakeId))
    let dataset=tutorText(evidence,"dataset_question_id")
    result.put("dataset_version",JsonString(if (dataset.isEmpty()) { "" } else { memoryDatasetVersion(db,dataset) }))
    return result
}

func memoryQuestion(db: Database, id: String, subject: String): JsonObject {
    let rows=db.query("SELECT * FROM questions WHERE id=? AND subject=? AND status<>'archived' AND confirmed=1",[Some(id),Some(subject)]).rows
    return if (rows.isEmpty()) { JsonObject() } else { rowJson("questions",rows[0]) }
}

func memoryUpdateValid(db: Database, update: JsonObject, owner: String, subject: String): Bool {
    if (tutorText(update,"user_id")!=owner) { return false }
    let evidence=tutorObject(update,"evidence"); let source=tutorObject(evidence,"memory_source")
    if (tutorText(source,"rule_version")!="learning-memory-v1") { return false }
    let question=memoryQuestion(db,tutorText(update,"question_id"),subject)
    if (question.getFields().isEmpty() || tutorText(source,"question_version")!=memoryQuestionVersion(db,question)) { return false }
    let strategy=tutorText(evidence,"strategy")
    if (strategy=="teacher_review") {
        return !db.query("SELECT r.id FROM teacher_review_results r JOIN teacher_review_tasks t ON t.id=r.task_id WHERE r.id=? AND t.student_id=? AND t.question_id=? AND r.revoked_at IS NULL AND r.allow_learning_update=1 AND t.learning_applied=1",[Some(tutorText(evidence,"teacher_review_id")),Some(owner),sqlValue(question["id"])]).rows.isEmpty()
    }
    if (tutorText(question,"user_id")!=owner) { return false }
    if (strategy=="verified_condition_contrast") {
        let rows=db.query("SELECT * FROM learning_tasks WHERE id=? AND user_id=? AND question_id=? AND status='completed' AND learning_applied=1",[Some(tutorText(evidence,"learning_task_id")),Some(owner),sqlValue(question["id"])]).rows
        if (rows.isEmpty()) { return false }
        return rowText(rows[0],"input_fingerprint")==taskFingerprint(taskSnapshot(db,jsonText(question,"id"),owner,lock:false))
    }
    if (strategy=="independent_dataset_practice") {
        let dataset=tutorText(evidence,"dataset_question_id"); let version=memoryDatasetVersion(db,dataset)
        if (version.isEmpty() || version!=tutorText(source,"dataset_version")) { return false }
        let rows=db.query("SELECT * FROM dataset_practice_attempts WHERE id=? AND user_id=? AND mistake_id=? AND dataset_question_id=?",[Some(tutorText(evidence,"practice_attempt_id")),Some(owner),sqlValue(question["id"]),Some(dataset)]).rows
        if (rows.isEmpty()) { return false }
        let attempt=rowJson("dataset_practice_attempts",rows[0]); let details=tutorObject(attempt,"grading_details")
        let preparation=JsonObject(); preparation.put("target_knowledge_id",attempt["knowledge_id"])
        let trace=JsonObject(); trace.put("alignment_proof",tutorObject(details,"alignment_proof"))
        let candidates=db.query("SELECT * FROM dataset_questions WHERE id=?",[Some(dataset)]).rows
        return !candidates.isEmpty() && tutorFlag(details,"can_update_learning") && practiceProofValid(db,question,preparation,rowJson("dataset_questions",candidates[0]),trace)
    }
    if (["micro_activity","assisted_progression"].contains(strategy)) {
        return !db.query("SELECT id FROM tutor_sessions WHERE id=? AND user_id=? AND question_id=? AND status='completed'",[Some(tutorText(evidence,"tutor_session_id")),Some(owner),sqlValue(question["id"])]).rows.isEmpty()
    }
    return false
}
