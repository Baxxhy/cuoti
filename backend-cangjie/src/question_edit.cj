package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

func invalidateQuestionLearning(db: Database, id: String): Unit {
    for (sql in [
        "DELETE e FROM diagnosis_evidence e JOIN diagnoses d ON e.diagnosis_id = d.id WHERE d.question_id = ?",
        "DELETE FROM diagnoses WHERE question_id = ?",
        "DELETE s FROM reference_steps s JOIN problem_analyses a ON s.analysis_id = a.id WHERE a.question_id = ?",
        "DELETE FROM problem_analyses WHERE question_id = ?",
        "DELETE FROM user_question_knowledge_links WHERE question_id = ?",
        "DELETE FROM practice_recommendations WHERE mistake_id = ?",
        "UPDATE tutor_sessions SET state = JSON_SET(IF(JSON_TYPE(state) = 'OBJECT', state, JSON_OBJECT()), '$.question_changed', CAST('true' AS JSON)), updated_at = UTC_TIMESTAMP() WHERE question_id = ?",
        "UPDATE review_plans SET status = 'cancelled', updated_at = UTC_TIMESTAMP() WHERE question_id = ? AND status = 'pending'",
        "UPDATE dataset_practice_attempts SET grading_details = JSON_SET(IF(JSON_TYPE(grading_details) = 'OBJECT', grading_details, JSON_OBJECT()), '$.question_changed', CAST('true' AS JSON)), updated_at = UTC_TIMESTAMP() WHERE mistake_id = ?",
        "UPDATE review_records r JOIN review_plans p ON r.plan_id = p.id SET r.grading_details = JSON_SET(IF(JSON_TYPE(r.grading_details) = 'OBJECT', r.grading_details, JSON_OBJECT()), '$.question_changed', CAST('true' AS JSON)), r.updated_at = UTC_TIMESTAMP() WHERE p.question_id = ?"
    ]) { db.query(sql, [Some(id)]) }
}

public func questionEdit(context: HttpContext, accounts: Accounts, id: String): JsonValue {
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        let body = readJson(context, maxBytes: 8 * 1024 * 1024)
        return db.transaction<JsonValue>({ tx =>
            let rows = tx.query("SELECT * FROM questions WHERE id = ? AND user_id = ? FOR UPDATE", [Some(id), user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404, "内容不存在或无权访问") }
            if (rowText(rows[0], "status") == "archived") { throw ApiError(409, "题目已归档，不能修改") }
            let edits = validateQuestionEdit(body)
            let existing = rowJson("questions", rows[0])
            if (edits.get("options").isSome() || edits.get("question_type").isSome()) {
                let kind=((edits.get("question_type") ?? existing["question_type"]) as JsonString).getOrThrow().getValue()
                let options=((edits.get("options") ?? existing["options"]) as JsonArray).getOrThrow()
                if ((kind=="单选题" || kind=="多选题") && options.getItems().size<2) { throw ApiError(422,"选择题至少需要两个不同选项") }
            }
            var changed = false
            var anyChanged = false
            for ((key, value) in edits.getFields()) {
                if (!jsonEquivalent(existing[key], value)) { anyChanged = true }
            }
            for (key in ["question_text", "student_answer", "subject", "grade", "formulas", "options", "question_type", "knowledge_points"]) {
                if (let Some(value) <- edits.get(key)) {
                    if (!jsonEquivalent(existing[key], value)) { changed = true }
                }
            }
            if (changed) { invalidateQuestionLearning(tx, id) }
            let sql = StringBuilder()
            let params = ArrayList<Option<String>>()
            sql.append("UPDATE questions SET updated_at = UTC_TIMESTAMP()")
            // Column names come only from validateQuestionEdit's fixed whitelist.
            for ((key, value) in edits.getFields()) {
                sql.append(", `${key}` = ?")
                if (value is JsonNull) { params.add(None) }
                else if (let Some(text) <- (value as JsonString)) { params.add(Some(text.getValue())) }
                else if (let Some(flag) <- (value as JsonBool)) { params.add(Some(if (flag.getValue()) { "1" } else { "0" })) }
                else { params.add(Some(value.toString())) }
            }
            if (changed) { sql.append(", status = IF(confirmed, 'confirmed', 'needs_confirmation')") }
            sql.append(" WHERE id = ?")
            params.add(Some(id))
            if (anyChanged) { tx.query(sql.toString(), params.toArray()) }
            return rowJson("questions", tx.query("SELECT * FROM questions WHERE id = ?", [Some(id)]).rows[0])
        })
    }
    throw ApiError(503, "数据库暂时不可用")
}
