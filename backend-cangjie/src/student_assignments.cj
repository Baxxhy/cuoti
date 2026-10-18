package zhiwei

import std.collection.*
import std.unicode.UnicodeStringExtension
import stdx.encoding.json.*
import stdx.net.http.*

enum AssignmentOutcome {
    AwaitingTeacher | Graded
    func attemptStatus(): String { match (this) { case AwaitingTeacher => "review_pending"; case Graded => "graded" } }
    func taskStatus(): String { match (this) { case AwaitingTeacher => "review_pending"; case Graded => "completed" } }
}

func requireStudent(user: HashMap<String,Option<String>>): String {
    if (rowText(user,"role")!="student") { throw ApiError(403,"当前账号不是学生") }; return rowText(user,"id")
}

func listStudentAssignments(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    try (db=Database.fromEnvironment()) {
        let owner=requireStudent(accounts.currentUser(context,db))
        return db.transaction<JsonValue>({ tx =>
            let result=JsonArray()
            for (row in tx.query("SELECT s.* FROM assignment_students s JOIN question_assignments a ON a.id=s.assignment_id WHERE s.student_id=? ORDER BY a.due_at,a.id,s.id",[Some(owner)]).rows) {
                let link=rowJson("assignment_students",row); let assignment=schoolRow(tx,SchoolTable.Assignment,rowText(row,"assignment_id")); let question=schoolRow(tx,SchoolTable.Question,jsonText(assignment,"question_id"))
                let attemptRows=tx.query("SELECT * FROM assignment_attempts WHERE id=? AND student_id=?",[row["latest_attempt_id"],Some(owner)]).rows
                let feedbackRows=tx.query("SELECT r.* FROM teacher_review_results r JOIN teacher_review_tasks t ON t.id=r.task_id WHERE t.student_id=? AND t.source_type='assignment_attempt' AND t.source_id=? AND r.revoked_at IS NULL ORDER BY r.created_at DESC,r.id DESC LIMIT 1",[Some(owner),row["latest_attempt_id"]]).rows
                let item=JsonObject(); var feedback: JsonValue=JsonNull()
                if (!feedbackRows.isEmpty()) {
                    let full=rowJson("teacher_review_results",feedbackRows[0]); let visible=JsonObject()
                    for (field in ["conclusion","score","first_key_error","student_hint","next_task"]) { visible.put(field,full[field]) }; feedback=visible
                    if (jsonText(full,"conclusion")=="question_issue") { link.put("status",JsonString("question_issue")) }
                }
                var latest: JsonValue=JsonNull(); var gradingFeedback=""
                if (!attemptRows.isEmpty()) {
                    let attempt=rowJson("assignment_attempts",attemptRows[0]); let visible=JsonObject(); visible.put("answer",attempt["answer"]); visible.put("steps",attempt["steps"]); latest=visible
                    if (jsonText(link,"status")=="completed" && feedback is JsonNull) { gradingFeedback=tutorText(tutorObject(attempt,"grading_details"),"feedback") }
                }
                item.put("student_assignment",link); item.put("assignment",assignment); item.put("question",question); item.put("latest_attempt",latest); item.put("teacher_feedback",feedback); item.put("grading_feedback",JsonString(gradingFeedback))
                item.put("require_handwriting",JsonBool(!tx.query("SELECT id FROM teacher_questions WHERE question_id=? AND require_handwriting=1",[sqlValue(question["id"])]).rows.isEmpty())); result.add(item)
            }
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func assignmentReviewReasons(grading: JsonObject, meta: JsonObject, settings: JsonObject, recognition: JsonObject, questionType: String): JsonArray {
    let reasons=JsonArray(); let verdict=tutorText(grading,"verdict")
    if (verdict=="probably_correct" || verdict=="review_required") { reasons.add(JsonString(verdict)) }
    if (tutorFlag(grading,"conflict")) { reasons.add(JsonString("rule_llm_conflict")) }
    if (let Some(value) <- recognition.get("confidence")) { if (!(value is JsonNull) && editNumber(value)<0.65) { reasons.add(JsonString("low_ocr_confidence")) } }
    var process=false; for (marker in ["综合","解答","证明","计算","主观","材料","proof","subjective","calculation"]) { if (questionType.toLower().contains(marker)) { process=true } }
    if (tutorText(meta,"standard_answer").isEmpty() || (process && tutorArray(meta,"reference_steps").getItems().isEmpty())) { reasons.add(JsonString("incomplete_reference")) }
    if (tutorFlag(settings,"require_teacher_review")) { reasons.add(JsonString("teacher_required")) }
    if (!tutorFlag(meta,"allow_auto_grade") || (settings.get("allow_auto_grade").isSome() && !tutorFlag(settings,"allow_auto_grade"))) { reasons.add(JsonString("auto_grade_disabled")) }
    return reasons
}

func submitStudentAssignment(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let owner=requireStudent(accounts.currentUser(context,db)); let body=readJson(context,maxBytes:8*1024*1024)
        return db.transaction<JsonValue>({ tx =>
            let snapshot=assignmentContext(tx,id,owner,lock:true); requireAssignmentPending(snapshot)
            let assignment=tutorObject(snapshot,"assignment"); let question=tutorObject(snapshot,"question"); let meta=tutorObject(snapshot,"meta"); let settings=tutorObject(assignment,"settings")
            if (tutorText(body,"handwriting_image_url").isEmpty()) { body.put("handwriting_image_url",body.get("handwriting_asset_ref") ?? JsonString("")) }
            let handwriting=validateTutorHandwriting(body,owner,id,kind:"assignment")
            if (tutorFlag(meta,"require_handwriting") && jsonText(handwriting,"image_url").isEmpty()) { throw ApiError(422,"该任务需要上传手写作答照片") }
            let answer=stripWhitespace(schoolText(body,"answer","",12000,nonempty:true)); let steps=manualArray(body,"steps",100); var grading=JsonObject()
            let automatic=tutorFlag(meta,"allow_auto_grade") && (settings.get("allow_auto_grade").isNone() || tutorFlag(settings,"allow_auto_grade"))
            if (automatic) {
                let input=JsonObject(); input.put("operation",JsonString("grade_answer")); input.put("text",question["question_text"]); input.put("answer",JsonString(answer)); input.put("expected",meta["standard_answer"]); input.put("reference_solution",meta["reference_steps"])
                for (field in ["subject","question_type","options"]) { input.put(field,question[field]) }; grading=algorithmCompute(input)
            } else {
                grading=(JsonValue.fromStr(##"{"correct":null,"score":null,"verdict":"review_required","decisive":false,"can_update_learning":false,"confidence":0,"method":"teacher_pending","grader":"teacher_pending","conflict":false,"feedback":"该任务由教师批改，作答已保存并提交核对。","evidence":[]}"##) as JsonObject).getOrThrow()
            }
            let recognition=tutorObject(handwriting,"recognition"); let reasons=assignmentReviewReasons(grading,meta,settings,recognition,jsonText(question,"question_type")); let waiting=!reasons.getItems().isEmpty()
            let outcome=if (waiting) { AssignmentOutcome.AwaitingTeacher } else { AssignmentOutcome.Graded }
            let details=(JsonValue.fromStr(grading.toString()) as JsonObject).getOrThrow(); details.put("student_answer",JsonString(answer)); details.put("handwriting_recognition",recognition)
            let attempt=SchoolRecord(SchoolTable.Attempt); attempt.put("assignment_student_id",JsonString(id)); attempt.put("student_id",JsonString(owner)); attempt.put("question_id",question["id"]); attempt.put("answer",JsonString(answer)); attempt.put("steps",steps)
            let image=jsonText(handwriting,"image_url"); attempt.put("handwriting_asset_ref",if (image.isEmpty()) { JsonNull() } else { JsonString(image) }); attempt.put("grading_details",details); attempt.put("verdict",grading["verdict"]); attempt.put("status",JsonString(outcome.attemptStatus())); let saved=attempt.save(tx)
            tx.query("UPDATE assignment_students SET latest_attempt_id=?,status=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(attempt.id),Some(outcome.taskStatus()),Some(id)])
            if (waiting) {
                let task=SchoolRecord(SchoolTable.ReviewTask); task.put("class_id",assignment["class_id"]); task.put("student_id",JsonString(owner)); task.put("question_id",question["id"]); task.put("source_id",JsonString(attempt.id)); task.put("reason_codes",reasons)
                let ai=(JsonValue.fromStr(grading.toString()) as JsonObject).getOrThrow(); ai.put("student_answer",JsonString(answer)); task.put("ai_result",ai)
                let rule=JsonObject(); for (field in ["method","correct","score","evidence"]) { rule.put(field,grading.get(field) ?? JsonNull()) }; task.put("rule_result",rule); task.put("confidence",grading.get("confidence") ?? JsonFloat(0.0)); task.put("has_conflict",grading.get("conflict") ?? JsonBool(false)); task.put("assigned_teacher_id",assignment["teacher_id"]); task.save(tx)
            } else if ((tutorText(grading,"verdict")=="confirmed_correct" || tutorText(grading,"verdict")=="confirmed_incorrect") && (settings.get("count_mastery").isNone() || tutorFlag(settings,"count_mastery"))) {
                applyAssignmentLearning(tx,owner,question,tutorText(grading,"verdict")=="confirmed_correct",attempt.id)
            }
            let result=JsonObject(); result.put("attempt",saved); result.put("grading",grading); result.put("entered_review_queue",JsonBool(waiting)); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func studentTeacherFeedback(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    try (db=Database.fromEnvironment()) {
        let owner=requireStudent(accounts.currentUser(context,db)); let result=JsonArray()
        for (row in db.query("SELECT r.* FROM teacher_review_results r JOIN teacher_review_tasks t ON t.id=r.task_id WHERE t.student_id=? AND r.revoked_at IS NULL ORDER BY r.created_at DESC,r.id DESC LIMIT 20",[Some(owner)]).rows) {
            let item=JsonObject(); item.put("result",rowJson("teacher_review_results",row)); item.put("task",schoolRow(db,SchoolTable.ReviewTask,rowText(row,"task_id"))); result.add(item)
        }
        return result
    }
    throw ApiError(503,"数据库暂时不可用")
}
