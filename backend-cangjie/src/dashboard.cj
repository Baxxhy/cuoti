package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.json.*
import stdx.net.http.*

func dashboardNextStep(stage: String): String {
    match (stage) {
        case "understanding" => "理解错误原因"
        case "teach_back" => "用自己的话讲清思路"
        case "teach_back_retry" => "补充说明关键理由"
        case "near_transfer" => "完成一道相似题"
        case "near_remediation" => "再巩固一次"
        case "far_transfer" => "完成综合应用"
        case "transfer_insufficient" => "回顾方法后再练习"
        case _ => "继续完成本次学习"
    }
}

func learningDashboard(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let questions=tx.query("SELECT id,question_text FROM questions WHERE user_id=? AND status<>'archived'",[user["id"]]).rows
            let uniqueQuestions=HashSet<String>()
            for (row in questions) { uniqueQuestions.add(questionDisplayKey(row["question_text"] ?? "",rowText(row,"id"))) }
            let reviewCount=Int64.parse(rowText(tx.query("SELECT COUNT(*) AS count FROM review_plans WHERE user_id=? AND status='pending' AND due_at<TIMESTAMP(DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR))+INTERVAL 16 HOUR",[user["id"]]).rows[0],"count"))
            let mastery=JsonArray(); let mistakes=JsonArray(); let discoveries=JsonArray()
            let seenPoints=HashSet<String>(); let seenMistakes=HashSet<String>(); var mastered: Int64=0
            for (row in tx.query("SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at DESC,id DESC LIMIT 8",[user["id"]]).rows) {
                let key=insightPair(rowText(row,"subject"),rowText(row,"knowledge_point"))
                if (seenPoints.contains(key)) { continue }; seenPoints.add(key)
                let item=rowJson("mastery_states",row); mastery.getItems().add(item)
                if (editNumber(item["mastery_score"])>=0.7) { mastered++ }
            }
            for (row in tx.query("SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id LIMIT 8",[user["id"]]).rows) {
                let label=canonicalMistakeLabel(rowText(row,"label")); let key=insightPair(rowText(row,"subject"),label)
                if (seenMistakes.contains(key)) { continue }; seenMistakes.add(key)
                let item=rowJson("misconception_states",row); item.put("label",JsonString(label)); mistakes.getItems().add(item)
                if (discoveries.getItems().size<2) {
                    let discovery=JsonObject(); discovery.put("kind",JsonString("attention")); discovery.put("title",JsonString(label)); discovery.put("detail",JsonString("这是目前最需要优先巩固的错误原因")); discovery.put("value",JsonInt(cognitionPercent(editNumber(item["probability"])))); discoveries.getItems().add(discovery)
                }
            }
            for (index in 0..mastery.getItems().size) {
                if (index>=2) { break }
                let item=(mastery.getItems()[index] as JsonObject).getOrThrow(); let stable=editNumber(item["mastery_score"])>=0.75
                let discovery=JsonObject(); discovery.put("kind",JsonString(if (stable) { "stable" } else { "progress" })); discovery.put("title",item["knowledge_point"]); discovery.put("detail",JsonString(if (stable) { "掌握状态已经比较稳定" } else { "继续完成相似题会更牢固" })); discovery.put("value",JsonInt(cognitionPercent(editNumber(item["mastery_score"])))); discoveries.getItems().add(discovery)
            }
            let sessions=tx.query("SELECT * FROM tutor_sessions WHERE user_id=? AND status='active' ORDER BY updated_at DESC,id DESC LIMIT 1",[user["id"]]).rows
            var continuation: JsonValue=JsonNull()
            if (!sessions.isEmpty()) {
                let session=rowJson("tutor_sessions",sessions[0])
                let active=tx.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived'",[sessions[0]["question_id"],user["id"]]).rows
                if (!active.isEmpty() && !tutorFlag(tutorObject(session,"state"),"question_changed")) {
                    let item=JsonObject(); item.put("session_id",session["id"]); item.put("question_id",session["question_id"]); item.put("stage",session["stage"])
                    item.put("knowledge_point",JsonString(graphTopic(rowJson("questions",active[0])))); item.put("next_step",JsonString(dashboardNextStep(jsonText(session,"stage")))); continuation=item
                }
            }
            var streak: Int64=0; var expected: Int64 = -1
            let days=tx.query("SELECT DISTINCT DATEDIFF(DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR),DATE(created_at+INTERVAL 8 HOUR)) AS day_offset FROM questions WHERE user_id=? AND status<>'archived' AND created_at IS NOT NULL ORDER BY day_offset",[user["id"]]).rows
            for (row in days) {
                let day=Int64.parse(rowText(row,"day_offset"))
                if (streak==0) { if (day!=0 && day!=1) { break }; expected=day }
                if (day!=expected) { break }; streak++; expected++
            }
            let profiles=tx.query("SELECT grade FROM student_profiles WHERE user_id=? LIMIT 1",[user["id"]]).rows
            let grade: JsonValue=if (profiles.isEmpty()) { JsonString("初二") } else if (let Some(value) <- profiles[0]["grade"]) { JsonString(value) } else { JsonNull() }
            let assignments=Int64.parse(rowText(tx.query("SELECT COUNT(*) AS count FROM assignment_students WHERE student_id=? AND status='pending'",[user["id"]]).rows[0],"count"))
            let feedbacks=tx.query("SELECT r.*,t.question_id FROM teacher_review_results r JOIN teacher_review_tasks t ON t.id=r.task_id WHERE t.student_id=? AND r.revoked_at IS NULL ORDER BY r.created_at DESC,r.id DESC LIMIT 1",[user["id"]]).rows
            var feedback: JsonValue=JsonNull()
            if (!feedbacks.isEmpty()) {
                let row=feedbacks[0]; let item=JsonObject()
                for (key in ["conclusion","reason","student_hint","next_task","question_id"]) { item.put(key,if (let Some(value) <- row[key]) { JsonString(value) } else { JsonNull() }) }
                item.put("handled_at",JsonString(rowText(row,"created_at").replace(" ","T"))); feedback=item
            }
            let hasData=!questions.isEmpty() || reviewCount>0 || !mastery.getItems().isEmpty() || !mistakes.getItems().isEmpty() || !(continuation is JsonNull)
            var minutes: Int64=0
            if (hasData) { minutes=reviewCount+if (continuation is JsonNull) { 2 } else { 5 }; if (minutes<3) { minutes=3 } }
            let result=JsonObject(); result.put("today_reviews",JsonInt(reviewCount)); result.put("weekly_questions",JsonInt(uniqueQuestions.size)); result.put("mastered_points",JsonInt(mastered)); result.put("streak_days",JsonInt(streak)); result.put("grade",grade); result.put("estimated_minutes",JsonInt(minutes))
            result.put("continue_learning",continuation); result.put("discoveries",discoveries); result.put("teacher_assignment_count",JsonInt(assignments)); result.put("teacher_feedback",feedback); result.put("mastery",mastery); result.put("misconceptions",mistakes)
            result.put("ai_suggestion",JsonString(if (hasData) { "先弄懂最常出错的一步，再完成一道相似题。" } else { "拍下第一道错题，我会从你的解题步骤开始分析。" }))
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
