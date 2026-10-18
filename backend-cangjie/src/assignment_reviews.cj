package zhiwei

import std.collection.*
import std.time.*
import stdx.encoding.json.*
import stdx.net.http.*

enum ReviewConclusion {
    Correct | Incorrect | Partial | Resubmit | QuestionIssue
    static func parse(value: String): ReviewConclusion {
        match (value) {
            case "confirmed_correct" => Correct
            case "confirmed_incorrect" => Incorrect
            case "partially_correct" => Partial
            case "resubmit" => Resubmit
            case "question_issue" => QuestionIssue
            case _ => throw ApiError(422,"人工结论无效")
        }
    }
    func confirmed(): Bool { match (this) { case Correct | Incorrect => true; case _ => false } }
    func correct(): Bool { match (this) { case Correct => true; case _ => false } }
    func taskStatus(): String { match (this) { case Resubmit => "resubmit"; case QuestionIssue => "question_issue"; case _ => "resolved" } }
    func studentStatus(): String { match (this) { case Resubmit => "pending"; case QuestionIssue => "question_issue"; case _ => "completed" } }
    func attemptStatus(): String { match (this) { case Resubmit => "resubmit"; case QuestionIssue => "question_issue"; case _ => "graded" } }
}

func teacherReviewQueue(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET"); let form=insightQuery(context)
    try (db=Database.fromEnvironment()) {
        let scope=TeacherScope(db,accounts.currentUser(context,db)); let classId=queryLast(form,"class_id")
        if (!classId.isEmpty()) { scope.classroom(classId) }
        let sql=StringBuilder(); sql.append("SELECT t.* FROM teacher_review_tasks t JOIN teacher_classes c ON c.id=t.class_id JOIN questions q ON q.id=t.question_id WHERE c.teacher_id=? AND t.status='pending'")
        let params=ArrayList<Option<String>>([Some(scope.actor)])
        for ((field,column) in [("class_id","t.class_id"),("student_id","t.student_id"),("subject","q.subject"),("verdict","JSON_UNQUOTE(JSON_EXTRACT(t.ai_result,'$.verdict'))")]) { let value=queryLast(form,field); if (!value.isEmpty()) { sql.append(" AND ${column}=?"); params.add(Some(value)) } }
        if (!form.getAll("conflict").isEmpty()) {
            let value=queryLast(form,"conflict").toAsciiLower(); var flag=""
            if (value=="true" || value=="1" || value=="yes" || value=="on") { flag="1" } else if (value=="false" || value=="0" || value=="no" || value=="off") { flag="0" } else { throw ApiError(422,"conflict 必须是布尔值") }
            sql.append(" AND t.has_conflict=?"); params.add(Some(flag))
        }
        sql.append(" ORDER BY t.created_at,t.id"); let result=JsonArray()
        for (row in db.query(sql.toString(),params.toArray()).rows) {
            let task=rowJson("teacher_review_tasks",row); let question=schoolRow(db,SchoolTable.Question,rowText(row,"question_id")); let users=db.query("SELECT name FROM users WHERE id=?",[row["student_id"]]).rows
            if (users.isEmpty()) { continue }
            task.put("student_name",JsonString(rowText(users[0],"name"))); task.put("question_title",question["title"]); task.put("question_summary",JsonString(shortTitle(tutorText(question,"question_text"),100)))
            task.put("student_answer",tutorObject(task,"ai_result").get("student_answer") ?? JsonString("")); task.put("subject",question["subject"]); task.put("question_type",question["question_type"]); task.put("verdict",tutorObject(task,"ai_result").get("verdict") ?? JsonNull())
            let elapsed=(unixNow()-DateTime.parse(rowText(row,"created_at").replace(" ","T")+"Z").toUnixTimeStamp().toSeconds())/60
            task.put("waiting_minutes",JsonInt(if (elapsed<0) { 0 } else { elapsed })); result.add(task)
        }
        return result
    }
    throw ApiError(503,"数据库暂时不可用")
}

func managedReview(db: Database, scope: TeacherScope, id: String, lock!: Bool=false): JsonObject {
    let rows=db.query("SELECT * FROM teacher_review_tasks WHERE id=?"+if (lock) { " FOR UPDATE" } else { "" },[Some(id)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"复核任务不存在") }
    scope.student(rowText(rows[0],"class_id"),rowText(rows[0],"student_id")); return rowJson("teacher_review_tasks",rows[0])
}

func teacherReviewDetail(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-1]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user); let task=managedReview(tx,scope,id); let questionId=jsonText(task,"question_id"); let question=schoolRow(tx,SchoolTable.Question,questionId)
            let result=JsonObject(); result.put("task",task); result.put("question",question)
            result.put("teacher_question",firstJson(queryArray(tx,"teacher_questions","SELECT * FROM teacher_questions WHERE question_id=?",questionId)))
            var attempt: JsonValue=JsonNull()
            if (jsonText(task,"source_type")=="assignment_attempt") {
                let rows=tx.query("SELECT * FROM assignment_attempts WHERE id=?",[sqlValue(task["source_id"])]).rows
                if (!rows.isEmpty()) { let item=rowJson("assignment_attempts",rows[0]); let image=tutorText(item,"handwriting_asset_ref"); item.put("handwriting_image_url",JsonString(if (image.isEmpty()) { "" } else { accounts.mediaUrl(image) })); attempt=item }
            }
            result.put("attempt",attempt)
            let analysis=firstJson(queryArray(tx,"problem_analyses","SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1",questionId)); result.put("analysis",analysis)
            result.put("reference_steps",if (analysis is JsonObject) { queryArray(tx,"reference_steps","SELECT * FROM reference_steps WHERE analysis_id=? ORDER BY step_index,id",jsonText((analysis as JsonObject).getOrThrow(),"id")) } else { JsonArray() })
            result.put("ocr",firstJson(queryArray(tx,"ocr_runs","SELECT * FROM ocr_runs WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",questionId)))
            let assets=queryArray(tx,"question_assets","SELECT * FROM question_assets WHERE question_id=? ORDER BY id",questionId)
            for (value in assets.getItems()) { let item=(value as JsonObject).getOrThrow(); item.put("url",JsonString(accounts.mediaUrl("/"+jsonText(item,"path")))) }; result.put("assets",assets)
            let mastery=JsonArray(); for (row in tx.query("SELECT * FROM mastery_states WHERE user_id=? AND subject=? ORDER BY id",[sqlValue(task["student_id"]),sqlValue(question["subject"])]).rows) { mastery.add(rowJson("mastery_states",row)) }; result.put("mastery",mastery)
            result.put("history",queryArray(tx,"teacher_review_results","SELECT * FROM teacher_review_results WHERE task_id=? ORDER BY created_at,id",id)); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func decideTeacherReview(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let body=readJson(context)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user); let task=managedReview(tx,scope,id,lock:true)
            if (tutorNumber(task,"version")!=tutorNumber(body,"version") || jsonText(task,"status")!="pending") { throw ApiError(409,"任务已被处理或作答已更新，请刷新后重试") }
            let conclusionText=tutorText(body,"conclusion"); let conclusion=ReviewConclusion.parse(conclusionText); let reason=stripWhitespace(schoolText(body,"reason","",12000,nonempty:true))
            var assignment: Option<JsonObject>=None; var attempt: Option<JsonObject>=None; var link: Option<JsonObject>=None
            let attempts=tx.query("SELECT * FROM assignment_attempts WHERE id=? AND student_id=? AND question_id=?",[sqlValue(task["source_id"]),sqlValue(task["student_id"]),sqlValue(task["question_id"])]).rows
            if (!attempts.isEmpty()) {
                let item=rowJson("assignment_attempts",attempts[0]); let links=tx.query("SELECT * FROM assignment_students WHERE id=? FOR UPDATE",[sqlValue(item["assignment_student_id"])]).rows
                if (!links.isEmpty()) { attempt=Some(item); link=Some(rowJson("assignment_students",links[0])); assignment=Some(schoolRow(tx,SchoolTable.Assignment,rowText(links[0],"assignment_id"))) }
            }
            let countMastery=if (let Some(item) <- assignment) { let settings=tutorObject(item,"settings"); settings.get("count_mastery").isNone() || tutorFlag(settings,"count_mastery") } else { true }
            let allowed=conclusion.confirmed() && countMastery && (body.get("allow_learning_update").isNone() || tutorFlag(body,"allow_learning_update"))
            let record=SchoolRecord(SchoolTable.ReviewResult); record.put("task_id",JsonString(id)); record.put("teacher_id",JsonString(scope.actor)); record.put("conclusion",JsonString(conclusionText)); record.put("reason",JsonString(reason)); record.put("score",body.get("score") ?? JsonNull())
            for ((field,limit) in [("first_key_error",12000),("error_type",80),("student_hint",12000),("next_task",12000)]) { record.put(field,JsonString(schoolText(body,field,"",limit))) }
            record.put("propagated_error",body.get("propagated_error") ?? JsonBool(false)); record.put("mastered_steps",manualArray(body,"mastered_steps",100)); record.put("allow_learning_update",JsonBool(allowed))
            let evidence=JsonObject(); evidence.put("ai",task["ai_result"]); evidence.put("rule",task["rule_result"]); evidence.put("task_version",task["version"]); record.put("evidence_snapshot",evidence)
            var applied=tutorFlag(task,"learning_applied")
            if (allowed && !applied) { let question=schoolRow(tx,SchoolTable.Question,jsonText(task,"question_id")); record.put("learning_snapshot",applyAssignmentLearning(tx,jsonText(task,"student_id"),question,conclusion.correct(),record.id)); applied=true }
            let saved=record.save(tx)
            tx.query("UPDATE teacher_review_tasks SET status=?,learning_applied=?,version=version+1,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(conclusion.taskStatus()),Some(if (applied) { "1" } else { "0" }),Some(id)])
            if (let Some(item) <- attempt) {
                tx.query("UPDATE assignment_attempts SET status=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(conclusion.attemptStatus()),sqlValue(item["id"])])
                if (let Some(current) <- link) { tx.query("UPDATE assignment_students SET status=?,updated_at=UTC_TIMESTAMP() WHERE id=? AND latest_attempt_id=?",[Some(conclusion.studentStatus()),sqlValue(current["id"]),sqlValue(item["id"])]) }
            }
            scope.audit(SchoolAction.ReviewDecision,id,task,saved,reason)
            let result=JsonObject(); result.put("task",schoolRow(tx,SchoolTable.ReviewTask,id)); result.put("result",saved); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
