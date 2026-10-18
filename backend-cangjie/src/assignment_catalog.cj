package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

func teacherQuestions(context: HttpContext, accounts: Accounts): JsonValue {
    if (context.request.method!="GET" && context.request.method!="POST") { context.responseBuilder.header("Allow","GET, POST"); throw ApiError(405,"请求方法不支持") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user)
            if (context.request.method=="GET") {
                let result=JsonArray()
                for (row in tx.query("SELECT * FROM teacher_questions WHERE teacher_id=? ORDER BY created_at DESC,id DESC",[Some(scope.actor)]).rows) {
                    let item=JsonObject(); item.put("teacher_question",rowJson("teacher_questions",row)); item.put("question",schoolRow(tx,SchoolTable.Question,rowText(row,"question_id"))); result.add(item)
                }
                return result
            }
            let body=readJson(context,maxBytes:8*1024*1024); let record=SchoolRecord(SchoolTable.Question)
            let text=stripWhitespace(schoolText(body,"question_text","",12000,nonempty:true))
            record.put("user_id",JsonString(scope.actor)); record.put("question_text",JsonString(text)); record.put("title",JsonString(schoolText(body,"title",shortTitle(text,40),255)))
            record.put("subject",JsonString(schoolText(body,"subject","数学",30,nonempty:true))); record.put("question_type",JsonString(schoolText(body,"question_type","综合题",50)))
            record.put("grade",body.get("grade") ?? JsonNull()); record.put("status",JsonString("confirmed")); record.put("confirmed",JsonBool(true))
            record.put("options",manualArray(body,"options",26)); record.put("knowledge_points",manualArray(body,"knowledge_points",100))
            let question=record.save(tx); let metadata=SchoolRecord(SchoolTable.TeacherQuestion)
            metadata.put("teacher_id",JsonString(scope.actor)); metadata.put("question_id",question["id"]); metadata.put("status",JsonString("published"))
            for ((field,fallback,limit) in [("source_type","manual",30),("standard_answer","",12000),("difficulty","",30)]) { metadata.put(field,JsonString(schoolText(body,field,fallback,limit))) }
            for (field in ["reference_steps","scoring_points"]) { metadata.put(field,manualArray(body,field,100)) }
            for ((field,fallback) in [("allow_auto_grade",true),("require_handwriting",false)]) { metadata.put(field,body.get(field) ?? JsonBool(fallback)) }
            let result=JsonObject(); result.put("question",question); result.put("teacher_question",metadata.save(tx))
            scope.audit(SchoolAction.CreateQuestion,record.id,JsonObject(),result,schoolText(body,"reason","录入题目",12000)); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func teacherAssignments(context: HttpContext, accounts: Accounts): JsonValue {
    if (context.request.method!="GET" && context.request.method!="POST") { context.responseBuilder.header("Allow","GET, POST"); throw ApiError(405,"请求方法不支持") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user)
            if (context.request.method=="GET") {
                let result=JsonArray()
                for (row in tx.query("SELECT * FROM question_assignments WHERE teacher_id=? ORDER BY created_at DESC,id DESC",[Some(scope.actor)]).rows) {
                    let item=rowJson("question_assignments",row)
                    item.put("student_count",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM assignment_students WHERE assignment_id=?",[row["id"]])))
                    item.put("completed_count",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM assignment_students WHERE assignment_id=? AND status='completed'",[row["id"]]))); result.add(item)
                }
                return result
            }
            let body=readJson(context); let classId=schoolText(body,"class_id","",36); scope.classroom(classId,lock:true)
            let questionId=schoolText(body,"question_id","",36)
            if (tx.query("SELECT id FROM teacher_questions WHERE teacher_id=? AND question_id=?",[Some(scope.actor),Some(questionId)]).rows.isEmpty()) { throw ApiError(404,"题目不存在或无权布置") }
            let requested=HashSet<String>(); for (value in manualArray(body,"student_ids",10000).getItems()) {
                if (let Some(text) <- (value as JsonString)) { requested.add(text.getValue()) } else { throw ApiError(422,"学生编号格式不正确") }
            }
            let targets=JsonArray(); let found=HashSet<String>()
            for (row in tx.query("SELECT student_id FROM teacher_class_students WHERE class_id=? ORDER BY id",[Some(classId)]).rows) {
                let id=rowText(row,"student_id"); if (requested.isEmpty() || requested.contains(id)) { targets.add(JsonString(id)); found.add(id) }
            }
            for (id in requested) { if (!found.contains(id)) { throw ApiError(403,"包含不属于该班级的学生") } }
            if (targets.getItems().isEmpty()) { throw ApiError(422,"班级中没有可布置的学生") }
            let record=SchoolRecord(SchoolTable.Assignment); record.put("teacher_id",JsonString(scope.actor)); record.put("class_id",JsonString(classId)); record.put("question_id",JsonString(questionId)); record.put("title",JsonString(schoolText(body,"title","练习任务",255)))
            record.put("settings",if (let Some(value) <- body.get("settings")) { if (value is JsonObject) { value } else { throw ApiError(422,"任务设置格式不正确") } } else { JsonObject() })
            let due=body.get("due_at") ?? JsonNull()
            if (!(due is JsonNull) && !tutorAnswerText(due).isEmpty()) { let seconds=schoolDeadline(schoolText(body,"due_at","",100)); record.put("due_at",JsonString(rowText(tx.query("SELECT TIMESTAMPADD(SECOND,?,'1970-01-01 00:00:00') AS due_at",[Some(seconds)]).rows[0],"due_at"))) }
            let result=record.save(tx)
            for (student in targets.getItems()) { let link=SchoolRecord(SchoolTable.StudentAssignment); link.put("assignment_id",JsonString(record.id)); link.put("student_id",student); link.save(tx) }
            let after=(JsonValue.fromStr(result.toString()) as JsonObject).getOrThrow(); after.put("student_ids",targets)
            scope.audit(SchoolAction.CreateAssignment,record.id,JsonObject(),after,schoolText(body,"reason","布置练习",12000)); result.put("student_count",JsonInt(targets.getItems().size)); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
