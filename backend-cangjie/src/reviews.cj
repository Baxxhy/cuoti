package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

func reviewQuestion(db: Database, plan: JsonObject, owner: String): JsonObject {
    let rows = db.query("SELECT * FROM questions WHERE id=? AND user_id=?",[sqlValue(plan["question_id"]),Some(owner)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"题目不存在") }
    return rowJson("questions",rows[0])
}

func reviewAttemptReceipt(record: JsonObject, accounts: Accounts): JsonObject {
    let details=tutorObject(record,"grading_details"); let result=JsonObject(); let grading=JsonObject()
    result.put("attempt_id",record["id"]); result.put("request_id",JsonString(tutorText(details,"review_request_id")))
    result.put("correct",if (tutorFlag(details,"can_update_learning")) { record["correct"] } else { JsonNull() })
    for (name in ["score","feedback","matched_points","can_update_learning"]) { result.put(name,details[name]) }
    for (name in ["verdict","correct","score","feedback","matched_points","can_update_learning"]) { grading.put(name,details[name]) }
    let raw=tutorText(details,"handwriting_image_url"); let path=if (raw.isEmpty()) { "" } else { raw.split("?",2)[0] }
    result.put("grading",grading); result.put("expected_answer",record["expected_answer"])
    result.put("student_answer",record["student_answer"])
    result.put("handwriting_image_url",JsonString(accounts.mediaUrl(path))); result.put("handwriting_recognition",details["handwriting_recognition"])
    return result
}

public func listReviews(context: HttpContext, accounts: Accounts, history: Bool): JsonValue {
    requireMethod(context,"GET")
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db); let result = JsonArray()
        if (history) {
            for (row in db.query("SELECT r.* FROM review_records r JOIN review_plans p ON p.id=r.plan_id WHERE p.user_id=? AND r.grade<>'pending' ORDER BY r.created_at DESC,r.id DESC",[user["id"]]).rows) {
                let record = rowJson("review_records",row); let plan = rowJson("review_plans",db.query("SELECT * FROM review_plans WHERE id=?",[row["plan_id"]]).rows[0])
                let questions = db.query("SELECT * FROM questions WHERE id=? AND user_id=?",[sqlValue(plan["question_id"]),user["id"]]).rows
                let details = tutorObject(record,"grading_details"); let rawPath = tutorText(details,"handwriting_image_url"); let path = if (rawPath.isEmpty()) { "" } else { rawPath.split("?",2)[0] }
                if (!path.isEmpty()) { details.put("handwriting_image_url",JsonString(accounts.mediaUrl(path))) }
                record.put("plan",plan); record.put("question",if (questions.isEmpty()) { JsonNull() } else { rowJson("questions",questions[0]) }); result.add(record)
            }
        } else {
            let seen = HashSet<String>()
            for (row in db.query("SELECT * FROM review_plans WHERE user_id=? AND status='pending' AND due_at<TIMESTAMPADD(HOUR,16,DATE(TIMESTAMPADD(HOUR,8,UTC_TIMESTAMP()))) ORDER BY due_at,id",[user["id"]]).rows) {
                let plan = rowJson("review_plans",row); let question = reviewQuestion(db,plan,rowText(user,"id"))
                if (jsonText(question,"status") == "archived") { continue }
                let key = questionDisplayKey(jsonText(question,"question_text"),jsonText(question,"id")); if (seen.contains(key)) { continue }; seen.add(key)
                let visible = JsonObject(); for ((name,value) in question.getFields()) { if (name != "student_answer") { visible.put(name,value) } }
                let figures = queryArray(db,"question_assets","SELECT * FROM question_assets WHERE question_id=? AND kind='question_figure' ORDER BY created_at,id",jsonText(question,"id"))
                for (value in figures.getItems()) { let figure = (value as JsonObject).getOrThrow(); figure.put("url",JsonString(accounts.mediaUrl("/"+jsonText(figure,"path")))) }
                visible.put("question_figures",figures); plan.put("question",visible)
                let version=memoryQuestionVersion(db,question); plan.put("source_version",JsonString(version)); plan.put("pending_attempt",JsonNull())
                let pending=db.query("SELECT * FROM review_records WHERE plan_id=? AND grade='pending' AND COALESCE(JSON_UNQUOTE(JSON_EXTRACT(grading_details,'$.review_record_state')),'current')<>'superseded' ORDER BY created_at DESC,id DESC LIMIT 1",[row["id"]]).rows
                if (!pending.isEmpty()) {
                    let record=rowJson("review_records",pending[0])
                    if (tutorText(tutorObject(record,"grading_details"),"memory_question_version")==version) { plan.put("pending_attempt",reviewAttemptReceipt(record,accounts)) }
                }
                if (tutorText(plan,"reason").toAsciiLower().contains("again")) { plan.put("reason",JsonString("本次作答需要重做，安排 1 天后再次复习")) }
                result.add(plan)
            }
        }
        return result
    }
    throw ApiError(503,"数据库暂时不可用")
}

public func attemptReview(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts = context.request.url.path.split("/"); let id = parts[parts.size-2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db); let body = readJson(context); let answer = editText(body.get("answer") ?? JsonString(""),12000,trim: true)
        return db.transaction<JsonValue>({ tx =>
            let rows = tx.query("SELECT * FROM review_plans WHERE id=? AND user_id=? AND status='pending' FOR UPDATE",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"待复习题不存在") }
            let plan = rowJson("review_plans",rows[0]); let question = reviewQuestion(tx,plan,rowText(user,"id"))
            if (jsonText(question,"status") == "archived") { throw ApiError(409,"题目已归档") }
            let version=memoryQuestionVersion(tx,question); let suppliedVersion=tutorText(body,"source_version")
            if (!suppliedVersion.isEmpty() && suppliedVersion!=version) { throw ApiError(409,"原题或参考已更新，请刷新后核对答案") }
            let requestId=if (body.get("request_id").isSome()) { textField(body,"request_id",80) } else { "" }
            let payload=JsonArray(); for (key in ["answer","handwriting_image_url","handwriting_recognition"]) { payload.add(body.get(key) ?? JsonNull()) }; let digest=sha256(payload.toString().toArray())
            if (!requestId.isEmpty()) {
                let previous=tx.query("SELECT * FROM review_records WHERE plan_id=? AND JSON_UNQUOTE(JSON_EXTRACT(grading_details,'$.review_request_id'))=? LIMIT 1",[Some(id),Some(requestId)]).rows
                if (!previous.isEmpty()) {
                    let record=rowJson("review_records",previous[0]); let details=tutorObject(record,"grading_details")
                    if (tutorText(details,"review_record_state")=="superseded") { throw ApiError(409,"已有更新的复习作答，请刷新查看当前判题") }
                    if (tutorText(details,"review_request_digest")!=digest || tutorText(details,"memory_question_version")!=version) { throw ApiError(409,"提交编号对应的作答或原题已变化，请核对后重新提交") }
                    return reviewAttemptReceipt(record,accounts)
                }
            }
            let analyses = tx.query("SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1",[sqlValue(plan["question_id"])]).rows
            if (analyses.isEmpty() || rowText(analyses[0],"final_answer").isEmpty()) { throw ApiError(422,"这道题还没有标准答案，请先在题目详情中完成分析") }
            let analysis = rowJson("problem_analyses",analyses[0]); let handwriting = validateTutorHandwriting(body,rowText(user,"id"),id,kind: "review")
            let input = JsonObject(); input.put("operation",JsonString("grade_answer")); input.put("text",question["question_text"]); input.put("answer",answer); input.put("expected",analysis["final_answer"])
            input.put("subject",question["subject"]); input.put("question_type",question["question_type"]); input.put("options",question["options"])
            input.put("reference_solution",tutorStringArray(tutorRowTexts(queryArray(tx,"reference_steps","SELECT * FROM reference_steps WHERE analysis_id=? ORDER BY step_index",jsonText(analysis,"id")))))
            let grading = algorithmCompute(input); let details = (JsonValue.fromStr(grading.toString()) as JsonObject).getOrThrow()
            details.put("memory_question_version",JsonString(version)); details.put("review_request_id",JsonString(requestId)); details.put("review_request_digest",JsonString(digest))
            details.put("handwriting_image_url",handwriting["image_url"]); details.put("handwriting_recognition",handwriting["recognition"])
            tx.query("UPDATE review_records SET grading_details=JSON_SET(grading_details,'$.review_record_state','superseded') WHERE plan_id=? AND grade='pending'",[Some(id)])
            let recordId = newId()
            tx.query("INSERT INTO review_records (id,plan_id,grade,correct,student_answer,expected_answer,feedback,score,grading_details,created_at,updated_at) VALUES (?,?,'pending',?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(recordId),Some(id),sqlValue(grading["correct"]),sqlValue(answer),sqlValue(analysis["final_answer"]),sqlValue(grading["feedback"]),sqlValue(grading["score"]),Some(details.toString())])
            return reviewAttemptReceipt(rowJson("review_records",tx.query("SELECT * FROM review_records WHERE id=?",[Some(recordId)]).rows[0]),accounts)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

public func gradeReview(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts = context.request.url.path.split("/"); let id = parts[parts.size-2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db); let body = readJson(context)
        return db.transaction<JsonValue>({ tx =>
            let rows = tx.query("SELECT * FROM review_plans WHERE id=? AND user_id=? FOR UPDATE",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"复习计划不存在") }
            let plan = rowJson("review_plans",rows[0]); if (jsonText(plan,"status") != "pending") { throw ApiError(409,"这次复习已完成，请刷新复习列表") }
            let records = tx.query("SELECT * FROM review_records WHERE id=? AND plan_id=? AND grade='pending'",[Some(tutorText(body,"attempt_id")),Some(id)]).rows
            if (records.isEmpty()) { throw ApiError(422,"请先提交答案并完成系统判定") }
            let record = rowJson("review_records",records[0]); let details = tutorObject(record,"grading_details")
            if (tutorText(details,"review_record_state")=="superseded") { throw ApiError(409,"已有更新的复习作答，请刷新查看当前判题") }
            if ((details.get("can_update_learning") ?? JsonBool(true)).toString() != "true") { throw ApiError(409,"这次判题仍需核对，不能据此更新复习计划") }
            let currentQuestion=reviewQuestion(tx,plan,rowText(user,"id")); let sourceVersion=tutorText(details,"memory_question_version")
            if (jsonText(currentQuestion,"status")=="archived" || (!sourceVersion.isEmpty() && sourceVersion!=memoryQuestionVersion(tx,currentQuestion))) { throw ApiError(409,"原题或参考已更新，请重新提交作答再评价复习") }
            let grade = tutorText(body,"grade"); let actualGrade = if (body.get("grade").isNone()) { "good" } else { grade }
            let correct = tutorFlag(record,"correct"); var days: Int64 = 1; var label = "还没想起来"
            match (actualGrade) {
                case "again" => ()
                case "hard" => days = if (correct) { 2 } else { 1 }; label = "有点困难"
                case "good" => days = if (correct) { 7 } else { 2 }; label = "已经掌握"
                case "easy" => days = if (correct) { 15 } else { 4 }; label = "很轻松"
                case _ => throw ApiError(422,"请选择有效的复习反馈")
            }
            tx.query("UPDATE review_plans SET status='completed',updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(id)])
            tx.query("UPDATE review_records SET grade=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(actualGrade),sqlValue(record["id"])])
            let nextId = newId(); let reason = "上次作答${if (correct) { "正确" } else { "有误" }}，随后选择了“${label}”"
            tx.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,TIMESTAMPADD(DAY,?,UTC_TIMESTAMP()),?,?,'pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(nextId),user["id"],sqlValue(plan["question_id"]),Some(days.toString()),Some(days.toString()),Some(reason)])
            let saved = rowJson("review_records",tx.query("SELECT * FROM review_records WHERE id=?",[sqlValue(record["id"])]).rows[0])
            let savedDetails = tutorObject(saved,"grading_details"); let rawImagePath = tutorText(savedDetails,"handwriting_image_url"); let imagePath = if (rawImagePath.isEmpty()) { "" } else { rawImagePath.split("?",2)[0] }
            if (!imagePath.isEmpty()) { savedDetails.put("handwriting_image_url",JsonString(accounts.mediaUrl(imagePath))) }
            let result = JsonObject(); result.put("record",saved); result.put("next_plan",rowJson("review_plans",tx.query("SELECT * FROM review_plans WHERE id=?",[Some(nextId)]).rows[0])); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
