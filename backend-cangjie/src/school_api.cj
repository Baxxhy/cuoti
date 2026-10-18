package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

func teacherClasses(context: HttpContext, accounts: Accounts): JsonValue {
    if (context.request.method!="GET" && context.request.method!="POST") { context.responseBuilder.header("Allow","GET, POST"); throw ApiError(405,"请求方法不支持") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user)
            if (context.request.method=="GET") {
                let result=JsonArray()
                for (row in tx.query("SELECT * FROM teacher_classes WHERE teacher_id=? ORDER BY id",[Some(scope.actor)]).rows) {
                    let item=rowJson("teacher_classes",row)
                    item.put("student_count",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM teacher_class_students WHERE class_id=?",[row["id"]]))); result.getItems().add(item)
                }
                return result
            }
            let body=readJson(context); let name=stripWhitespace(schoolText(body,"name","",100,nonempty:true)); let grade=schoolText(body,"grade","",30); let reason=schoolText(body,"reason","创建班级",12000)
            let id=newId()
            tx.query("INSERT INTO teacher_classes (id,teacher_id,name,grade,created_at,updated_at) VALUES (?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(id),Some(scope.actor),Some(name),Some(grade)])
            let result=scope.classroom(id); scope.audit(SchoolAction.CreateClass,id,JsonObject(),result,reason)
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func teacherClassDetail(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let parts=context.request.url.path.split("/"); let id=parts[parts.size-1]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user); let result=scope.classroom(id); let students=JsonArray()
            for (row in tx.query("SELECT u.* FROM users u JOIN teacher_class_students l ON l.student_id=u.id WHERE l.class_id=? ORDER BY l.id",[Some(id)]).rows) {
                let item=userJson(row); let studentId=rowText(row,"id")
                item.put("average_mastery",JsonFloat(schoolAverage(tx,studentId)))
                item.put("active_misconceptions",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM misconception_states WHERE user_id=? AND status<>'resolved'",[Some(studentId)]))); students.getItems().add(item)
            }
            result.put("students",students); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func addClassStudent(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    let parts=context.request.url.path.split("/"); let classId=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user); scope.classroom(classId,lock:true)
            let body=readJson(context); let email=stripWhitespace(schoolText(body,"email","",190)).toAsciiLower(); let reason=schoolText(body,"reason","加入班级",12000)
            let rows=tx.query("SELECT * FROM users WHERE email=? AND role='student'",[Some(email)]).rows
            if (rows.isEmpty()) { throw ApiError(404,"未找到该学生账号") }
            let student=rows[0]; let id=rowText(student,"id")
            if (tx.query("SELECT id FROM teacher_class_students WHERE class_id=? AND student_id=?",[Some(classId),Some(id)]).rows.isEmpty()) {
                tx.query("INSERT INTO teacher_class_students (id,class_id,student_id,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(classId),Some(id)])
                let after=JsonObject(); after.put("student_id",JsonString(id)); scope.audit(SchoolAction.AddStudent,classId,JsonObject(),after,reason)
            }
            let result=JsonObject(); for (key in ["id","name","email"]) { result.put(key,JsonString(rowText(student,key))) }; return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func removeClassStudent(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"DELETE")
    let parts=context.request.url.path.split("/"); let classId=parts[parts.size-3]; let studentId=parts[parts.size-1]
    let form=insightQuery(context)
    if (form.getAll("reason").isEmpty()) { throw ApiError(422,"缺少移除原因") }
    let reason=queryLast(form,"reason")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user); scope.student(classId,studentId)
            tx.query("DELETE FROM teacher_class_students WHERE class_id=? AND student_id=?",[Some(classId),Some(studentId)])
            let before=JsonObject(); before.put("student_id",JsonString(studentId)); scope.audit(SchoolAction.RemoveStudent,classId,before,JsonObject(),reason)
            let result=JsonObject(); result.put("removed",JsonBool(true)); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func guardianStudents(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        if (rowText(user,"role")!="guardian") { throw ApiError(403,"请使用家长账号登录") }
        return db.transaction<JsonValue>({ tx =>
            let result=JsonArray()
            for (row in tx.query("SELECT u.* FROM guardian_student_links l JOIN users u ON u.id=l.student_id WHERE l.guardian_id=? ORDER BY l.id",[user["id"]]).rows) {
                let item=userJson(row); let id=rowText(row,"id")
                item.put("pending_reviews",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM review_plans WHERE user_id=? AND status='pending'",[Some(id)])))
                item.put("average_mastery",JsonFloat(schoolAverage(tx,id))); result.getItems().add(item)
            }
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func schoolStudentReport(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let parts=context.request.url.path.split("/"); let studentId=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let role=rowText(user,"role"); var allowed: Int64=0
            if (role=="guardian") {
                allowed=schoolCount(tx,"SELECT COUNT(*) AS count FROM guardian_student_links WHERE guardian_id=? AND student_id=?",[user["id"],Some(studentId)])
            } else if (role=="teacher") {
                allowed=schoolCount(tx,"SELECT COUNT(*) AS count FROM teacher_class_students l JOIN teacher_classes c ON c.id=l.class_id WHERE c.teacher_id=? AND l.student_id=?",[user["id"],Some(studentId)])
            } else { throw ApiError(403,"请使用家长或教师账号登录") }
            if (allowed==0) { throw ApiError(403,"该学生未关联到当前账号") }
            let students=tx.query("SELECT * FROM users WHERE id=?",[Some(studentId)]).rows
            if (students.isEmpty()) { throw ApiError(404,"学生不存在") }
            let mastery=queryArray(tx,"mastery_states","SELECT * FROM mastery_states WHERE user_id=? ORDER BY id",studentId)
            let mistakes=queryArray(tx,"misconception_states","SELECT * FROM misconception_states WHERE user_id=? ORDER BY id",studentId)
            let recent=queryArray(tx,"cognitive_updates","SELECT * FROM cognitive_updates WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 10",studentId)
            let weak=tx.query("SELECT knowledge_point FROM mastery_states WHERE user_id=? ORDER BY mastery_score,id LIMIT 1",[Some(studentId)]).rows
            let summary=JsonObject()
            summary.put("questions",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM questions WHERE user_id=?",[Some(studentId)])))
            summary.put("completed_sessions",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM tutor_sessions WHERE user_id=? AND status='completed'",[Some(studentId)])))
            summary.put("review_records",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM review_records r JOIN review_plans p ON p.id=r.plan_id WHERE p.user_id=?",[Some(studentId)])))
            let result=JsonObject(); result.put("student",userJson(students[0])); result.put("mastery",mastery); result.put("misconceptions",mistakes); result.put("summary",summary); result.put("recent_updates",recent)
            result.put("suggestion",JsonString(if (weak.isEmpty()) { "先完成一道错题学习，系统会给出更具体的建议。" } else { "建议先巩固"+rowText(weak[0],"knowledge_point")+"，再用自己的话讲一遍解题方法。" })); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func teacherStudentPlans(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let parts=context.request.url.path.split("/"); let studentId=parts[parts.size-2]; let form=insightQuery(context)
    if (form.getAll("class_id").isEmpty()) { throw ApiError(422,"缺少班级") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user); scope.student(queryLast(form,"class_id"),studentId)
            return queryArray(tx,"review_plans","SELECT * FROM review_plans WHERE user_id=? ORDER BY due_at,id",studentId)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func teacherUpdatePlan(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"PATCH")
    let parts=context.request.url.path.split("/"); let id=parts[parts.size-1]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user); let body=readJson(context)
            let rows=tx.query("SELECT * FROM review_plans WHERE id=? FOR UPDATE",[Some(id)]).rows
            if (rows.isEmpty()) { throw ApiError(404,"学习计划不存在") }
            let before=rowJson("review_plans",rows[0]); let classId=schoolText(body,"class_id","",36)
            scope.student(classId,rowText(rows[0],"user_id"))
            let reason=stripWhitespace(schoolText(body,"reason","",12000,nonempty:true))
            if (body.get("due_at").isSome()) {
                let seconds=schoolDeadline(schoolText(body,"due_at","",100))
                tx.query("UPDATE review_plans SET due_at=TIMESTAMPADD(SECOND,?,'1970-01-01 00:00:00') WHERE id=?",[Some(seconds),Some(id)])
            }
            if (let Some(value) <- body.get("status")) {
                if (let Some(status) <- (value as JsonString)) {
                    let text=status.getValue()
                    if (text=="pending" || text=="paused" || text=="cancelled") { tx.query("UPDATE review_plans SET status=? WHERE id=?",[Some(text),Some(id)]) }
                }
            }
            if (body.get("task_reason").isSome()) { tx.query("UPDATE review_plans SET reason=? WHERE id=?",[Some(schoolText(body,"task_reason","",12000)),Some(id)]) }
            tx.query("UPDATE review_plans SET updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(id)])
            let after=rowJson("review_plans",tx.query("SELECT * FROM review_plans WHERE id=?",[Some(id)]).rows[0])
            scope.audit(SchoolAction.UpdatePlan,id,before,after,reason); return after
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func teacherAuditLogs(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    try (db=Database.fromEnvironment()) {
        let scope=TeacherScope(db,accounts.currentUser(context,db))
        return queryArray(db,"teacher_audit_logs","SELECT * FROM teacher_audit_logs WHERE teacher_id=? ORDER BY created_at DESC,id DESC LIMIT 200",scope.actor)
    }
    throw ApiError(503,"数据库暂时不可用")
}
