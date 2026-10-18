package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.json.*
import stdx.net.http.*

func teacherDashboard(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let scope=TeacherScope(tx,user); let params=[Some(scope.actor)]
            let students="SELECT l.student_id FROM teacher_class_students l JOIN teacher_classes c ON c.id=l.class_id WHERE c.teacher_id=?"
            let classes="SELECT id FROM teacher_classes WHERE teacher_id=?"
            let result=JsonObject()
            result.put("pending_reviews",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM teacher_review_tasks WHERE class_id IN ("+classes+") AND status='pending'",params)))
            result.put("today_mistakes",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM questions WHERE user_id IN ("+students+") AND DATE(created_at)=DATE(UTC_TIMESTAMP())",params)))
            result.put("overdue_students",JsonInt(schoolCount(tx,"SELECT COUNT(DISTINCT user_id) AS count FROM review_plans WHERE user_id IN ("+students+") AND status='pending' AND due_at<UTC_TIMESTAMP(6)",params)))
            result.put("unfinished_assignments",JsonInt(schoolCount(tx,"SELECT COUNT(*) AS count FROM assignment_students s JOIN question_assignments a ON a.id=s.assignment_id WHERE a.teacher_id=? AND s.status='pending'",params)))
            let masteries=tx.query("SELECT mastery_score,knowledge_point FROM mastery_states WHERE user_id IN ("+students+") ORDER BY mastery_score,id",params).rows
            var total=0.0; let weak=JsonArray()
            for (row in masteries) {
                let score=Float64.parse(rowText(row,"mastery_score")); total+=score
                if (weak.getItems().size<5) { let item=JsonObject(); item.put("name",JsonString(rowText(row,"knowledge_point"))); item.put("score",JsonFloat(score)); weak.getItems().add(item) }
            }
            result.put("average_mastery",JsonFloat(if (masteries.isEmpty()) { 0.0 } else { schoolRound(total/Float64(masteries.size),1000.0) })); result.put("weak_points",weak)
            let errors=JsonArray()
            for (row in tx.query("SELECT label,probability FROM misconception_states WHERE user_id IN ("+students+") AND status<>'resolved' ORDER BY probability DESC,id LIMIT 5",params).rows) {
                let item=JsonObject(); item.put("name",JsonString(rowText(row,"label"))); item.put("probability",JsonFloat(Float64.parse(rowText(row,"probability")))); errors.getItems().add(item)
            }
            result.put("frequent_errors",errors); let attention=JsonArray()
            for (row in tx.query("SELECT u.id,u.name,COUNT(t.id) AS count FROM users u JOIN teacher_review_tasks t ON t.student_id=u.id WHERE t.class_id IN ("+classes+") AND t.status='pending' GROUP BY u.id,u.name ORDER BY count DESC,u.id LIMIT 5",params).rows) {
                let item=JsonObject(); item.put("id",JsonString(rowText(row,"id"))); item.put("name",JsonString(rowText(row,"name"))); item.put("pending_reviews",JsonInt(Int64.parse(rowText(row,"count")))); attention.getItems().add(item)
            }
            result.put("attention_students",attention); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
