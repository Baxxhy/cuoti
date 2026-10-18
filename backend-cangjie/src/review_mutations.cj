package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

enum ReviewChange {
    Revoke | Regrade | Transfer
    func action(): SchoolAction {
        match (this) {
            case Revoke => SchoolAction.ReviewRevoke
            case Regrade => SchoolAction.ReviewRegrade
            case Transfer => SchoolAction.ReviewTransfer
        }
    }
}

// Reversal is conditional business persistence. The original Python grading and
// cognition formulas remain in the algorithm service.
func reverseReviewLearning(db: Database,task: JsonObject,result: JsonObject,reason: String): Unit {
    let snapshot=tutorObject(result,"learning_snapshot")
    if (!tutorFlag(task,"learning_applied") || snapshot.getFields().isEmpty()) { return }
    for ((table,kind,value,initial) in [("mastery_states","mastery","mastery_score",0.0),("misconception_states","misconception","probability",0.5)]) {
        let after=tutorObject(snapshot,kind+"_after"); let before=tutorObject(snapshot,kind+"_before")
        if (after.getFields().isEmpty()) { continue }
        // Match the original decoded-value comparison. MySQL FLOAT promoted in
        // a SQL predicate can differ from the value returned by its text protocol.
        let current=db.query("SELECT * FROM ${table} WHERE id=? AND user_id=? FOR UPDATE",[sqlValue(after["id"]),sqlValue(task["student_id"])]).rows
        if (current.isEmpty() || editNumber(rowJson(table,current[0])[value])!=editNumber(after[value])) { continue }
        let previous=before.get(value) ?? JsonFloat(initial)
        db.query("UPDATE ${table} SET ${value}=?,evidence_count=GREATEST(0,evidence_count-1),updated_at=UTC_TIMESTAMP() WHERE id=? AND user_id=?",[sqlValue(previous),sqlValue(after["id"]),sqlValue(task["student_id"])])
    }
    let evidence=JsonObject(); evidence.put("revoked_review_id",result["id"])
    db.query("INSERT INTO cognitive_updates (id,user_id,question_id,entity_type,entity_key,old_value,new_value,evidence,reason,created_at,updated_at) VALUES (?,?,?,'teacher_review_reversal',?,1,0,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),sqlValue(task["student_id"]),sqlValue(task["question_id"]),sqlValue(result["id"]),Some(evidence.toString()),Some(reason)])
}

func revokeTeacherReview(db: Database,scope: TeacherScope,task: JsonObject,body: JsonObject): JsonValue {
    let reason=stripWhitespace(schoolText(body,"reason","",12000,nonempty:true)); let id=jsonText(task,"id")
    let rows=db.query("SELECT * FROM teacher_review_results WHERE task_id=? AND revoked_at IS NULL ORDER BY created_at DESC,id DESC LIMIT 1 FOR UPDATE",[Some(id)]).rows
    if (rows.isEmpty()) { throw ApiError(409,"没有可撤销的人工结论") }
    let result=rowJson("teacher_review_results",rows[0]); reverseReviewLearning(db,task,result,reason)
    db.query("UPDATE teacher_review_results SET revoked_at=UTC_TIMESTAMP(),updated_at=UTC_TIMESTAMP() WHERE id=?",[sqlValue(result["id"])])
    db.query("UPDATE teacher_review_tasks SET status='pending',learning_applied=0,version=version+1,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(id)])
    let attempts=db.query("SELECT * FROM assignment_attempts WHERE id=? AND student_id=? AND question_id=?",[sqlValue(task["source_id"]),sqlValue(task["student_id"]),sqlValue(task["question_id"])]).rows
    if (!attempts.isEmpty()) {
        let attempt=attempts[0]
        let links=db.query("SELECT s.id FROM assignment_students s JOIN question_assignments a ON a.id=s.assignment_id WHERE s.id=? FOR UPDATE",[attempt["assignment_student_id"]]).rows
        if (!links.isEmpty()) {
            db.query("UPDATE assignment_attempts SET status='review_pending',updated_at=UTC_TIMESTAMP() WHERE id=?",[attempt["id"]])
            db.query("UPDATE assignment_students SET status='review_pending',updated_at=UTC_TIMESTAMP() WHERE id=? AND latest_attempt_id=?",[attempt["assignment_student_id"],attempt["id"]])
        }
    }
    let saved=schoolRow(db,SchoolTable.ReviewTask,id)
    scope.audit(ReviewChange.Revoke.action(),id,schoolRow(db,SchoolTable.ReviewResult,jsonText(result,"id")),saved,reason); return saved
}

func regradeTeacherReview(db: Database,scope: TeacherScope,task: JsonObject,body: JsonObject): JsonValue {
    let id=jsonText(task,"id")
    if (tutorNumber(task,"version")!=tutorNumber(body,"version") || jsonText(task,"status")!="pending") { throw ApiError(409,"任务已发生变化，请刷新后重试") }
    let reason=stripWhitespace(schoolText(body,"reason","",12000,nonempty:true))
    let questions=db.query("SELECT * FROM questions WHERE id=?",[sqlValue(task["question_id"])]).rows
    if (questions.isEmpty()) { throw ApiError(409,"题目已不存在") }
    let question=rowJson("questions",questions[0])
    let attempts=db.query("SELECT * FROM assignment_attempts WHERE id=?",[sqlValue(task["source_id"])]).rows
    let metas=db.query("SELECT * FROM teacher_questions WHERE question_id=?",[sqlValue(question["id"])]).rows
    if (attempts.isEmpty() || metas.isEmpty()) { throw ApiError(409,"原始作答证据不可用") }
    let attempt=rowJson("assignment_attempts",attempts[0]); let meta=rowJson("teacher_questions",metas[0])
    let answer=stripWhitespace(schoolText(body,"ocr_text",tutorText(attempt,"answer"),12000)); let expected=stripWhitespace(schoolText(body,"standard_answer",tutorText(meta,"standard_answer"),12000))
    let references=if (body.get("reference_steps").isSome()) { manualArray(body,"reference_steps",100) } else { tutorArray(meta,"reference_steps") }
    let input=JsonObject(); input.put("operation",JsonString("grade_answer")); input.put("text",question["question_text"]); input.put("answer",JsonString(answer)); input.put("expected",JsonString(expected)); input.put("reference_solution",references)
    for (key in ["subject","question_type","options"]) { input.put(key,question[key]) }
    let grading=algorithmCompute(input); let details=(JsonValue.fromStr(grading.toString()) as JsonObject).getOrThrow()
    details.put("student_answer",JsonString(answer)); details.put("original_grading",attempt["grading_details"])
    let revision=JsonObject(); revision.put("ocr_text",body.get("ocr_text") ?? JsonNull()); revision.put("standard_answer",body.get("standard_answer") ?? JsonNull()); revision.put("reason",JsonString(reason)); details.put("teacher_revision",revision)
    db.query("UPDATE assignment_attempts SET grading_details=?,verdict=?,version=version+1,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(details.toString()),sqlValue(grading["verdict"]),sqlValue(attempt["id"])])
    let reasons=JsonArray(); let verdict=tutorText(grading,"verdict")
    if (verdict=="probably_correct" || verdict=="review_required") { reasons.add(JsonString(verdict)) }
    if (tutorFlag(grading,"conflict")) { reasons.add(JsonString("rule_llm_conflict")) }
    if (expected.isEmpty() || references.getItems().isEmpty()) { reasons.add(JsonString("incomplete_reference")) }
    if (reasons.getItems().isEmpty()) { reasons.add(JsonString("teacher_regrade_confirmation")) }
    let ai=(JsonValue.fromStr(grading.toString()) as JsonObject).getOrThrow(); ai.put("student_answer",JsonString(answer)); let rule=JsonObject()
    for (key in ["method","correct","score","evidence"]) { rule.put(key,grading.get(key) ?? JsonNull()) }
    db.query("UPDATE teacher_review_tasks SET ai_result=?,rule_result=?,confidence=?,has_conflict=?,reason_codes=?,version=version+1,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(ai.toString()),Some(rule.toString()),sqlValue(grading.get("confidence") ?? JsonFloat(0.0)),sqlValue(grading.get("conflict") ?? JsonBool(false)),Some(reasons.toString()),Some(id)])
    let saved=schoolRow(db,SchoolTable.ReviewTask,id); let before=JsonObject(); before.put("task",task); before.put("attempt",attempt)
    let result=JsonObject(); result.put("task",saved); result.put("grading",grading)
    scope.audit(ReviewChange.Regrade.action(),id,before,result,reason); return result
}

func transferTeacherReview(db: Database,scope: TeacherScope,task: JsonObject,body: JsonObject): JsonValue {
    let classroom=scope.classroom(jsonText(task,"class_id"),lock:true)
    let teacher=schoolText(body,"teacher_id","",36); let reason=stripWhitespace(schoolText(body,"reason","",12000))
    if (reason.isEmpty() || db.query("SELECT id FROM users WHERE id=? AND role='teacher'",[Some(teacher)]).rows.isEmpty()) { throw ApiError(422,"请选择教师并填写转交原因") }
    if (teacher!=jsonText(classroom,"teacher_id")) { throw ApiError(403,"目标教师不是该班级管理员") }
    let id=jsonText(task,"id")
    db.query("UPDATE teacher_review_tasks SET assigned_teacher_id=?,version=version+1,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(teacher),Some(id)])
    let saved=schoolRow(db,SchoolTable.ReviewTask,id); scope.audit(ReviewChange.Transfer.action(),id,task,saved,reason); return saved
}

func changeTeacherReview(context: HttpContext,accounts: Accounts,change: ReviewChange): JsonValue {
    requireMethod(context,"POST"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let body=readJson(context)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user)
            let rows=tx.query("SELECT * FROM teacher_review_tasks WHERE id=? FOR UPDATE",[Some(id)]).rows
            if (rows.isEmpty()) { throw ApiError(404,"复核任务不存在") }
            let task=rowJson("teacher_review_tasks",rows[0])
            match (change) {
                case Transfer => return transferTeacherReview(tx,scope,task,body)
                case Revoke => scope.student(jsonText(task,"class_id"),jsonText(task,"student_id")); return revokeTeacherReview(tx,scope,task,body)
                case Regrade => scope.student(jsonText(task,"class_id"),jsonText(task,"student_id")); return regradeTeacherReview(tx,scope,task,body)
            }
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
