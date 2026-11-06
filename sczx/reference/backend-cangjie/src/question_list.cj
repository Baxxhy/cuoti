package zhiwei

import std.collection.*
import std.convert.*
import std.fs.*
import std.unicode.UnicodeStringExtension
import stdx.encoding.json.*
import stdx.encoding.url.*
import stdx.net.http.*

let errorTaxonomy = (JsonValue.fromStr(String.fromUtf8(File.readFrom("schema/error_taxonomy.json"))) as JsonArray).getOrThrow()
let pythonWhitespace = " \t\n\r\u{b}\u{c}\u{1c}\u{1d}\u{1e}\u{1f}\u{85}\u{a0}\u{1680}\u{2000}\u{2001}\u{2002}\u{2003}\u{2004}\u{2005}\u{2006}\u{2007}\u{2008}\u{2009}\u{200a}\u{2028}\u{2029}\u{202f}\u{205f}\u{3000}"

func questionDisplayKey(text: String, id: String): String {
    let clean = StringBuilder()
    var hasContent = false
    for (rune in text.runes()) {
        let one = StringBuilder()
        one.append(rune)
        let character = one.toString()
        if (pythonWhitespace.contains(character)) { continue }
        hasContent = true
        if (!"，。？?：:".contains(character)) { clean.append(rune) }
    }
    return if (hasContent) { clean.toString().toLower() } else { "pending:${id}" }
}

func queryLast(form: Form, key: String): String {
    let values = form.getAll(key)
    return if (values.isEmpty()) { "" } else { values[values.size - 1] }
}

public func questionList(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context, "GET")
    let form = try { Form(context.request.url.rawQuery ?? "") }
        catch (_: Exception) { throw ApiError(422, "查询参数格式不正确") }
    let subject = queryLast(form, "subject")
    let search = queryLast(form, "search")
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        let sql = StringBuilder()
        let params = ArrayList<Option<String>>([user["id"]])
        sql.append("SELECT q.* FROM questions q WHERE q.user_id = ? AND q.status <> 'archived'")
        if (!subject.isEmpty()) { sql.append(" AND q.subject = ?"); params.add(Some(subject)) }
        if (!search.isEmpty()) {
            sql.append(" AND (q.question_text LIKE ? OR q.title LIKE ? OR CAST(q.knowledge_points AS CHAR) LIKE ? OR CAST(q.tags AS CHAR) LIKE ? OR EXISTS (SELECT 1 FROM diagnoses d WHERE d.question_id = q.id AND (d.root_misconception LIKE ? OR d.error_type LIKE ? OR d.first_error_text LIKE ?")
            for (_ in 0..7) { params.add(Some("%${search}%")) }
            let codes = HashSet<String>()
            for (item in errorTaxonomy.getItems()) {
                let pair = (item as JsonArray).getOrThrow().getItems()
                let code = (pair[0] as JsonString).getOrThrow().getValue()
                let label = (pair[1] as JsonString).getOrThrow().getValue()
                if ((search.contains(label) || label.contains(search)) && !codes.contains(code)) {
                    codes.add(code)
                    sql.append(" OR d.error_type = ?")
                    params.add(Some(code))
                }
            }
            sql.append(")))")
        }
        sql.append(" ORDER BY q.created_at DESC")
        return db.transaction<JsonValue>({ tx =>
            let result = JsonArray()
            let seen = HashSet<String>()
            for (row in tx.query(sql.toString(), params.toArray()).rows) {
                let id = rowText(row, "id")
                let key = questionDisplayKey(row["question_text"] ?? "", id)
                if (seen.contains(key)) { continue }
                seen.add(key)
                let item = rowJson("questions", row)
                let diagnosis = tx.query("SELECT root_misconception FROM diagnoses WHERE question_id = ? ORDER BY created_at DESC LIMIT 1", [Some(id)]).rows
                item.put("diagnosis_summary", JsonString(if (diagnosis.isEmpty()) { "等待完成错因诊断" } else { rowText(diagnosis[0], "root_misconception") }))
                let review = tx.query("SELECT due_at FROM review_plans WHERE question_id = ? AND user_id = ? AND status = 'pending' ORDER BY due_at LIMIT 1", [Some(id), user["id"]]).rows
                item.put("review_due_at", if (review.isEmpty()) { JsonNull() } else { rowJson("review_plans", review[0])["due_at"] })
                var knowledge = row["knowledge_points"] ?? "[]"
                if (knowledge == "null" || (JsonValue.fromStr(knowledge) as JsonArray).getOrThrow().getItems().isEmpty()) { knowledge = "[\"__none__\"]" }
                let mastery = tx.query("SELECT mastery_score FROM mastery_states WHERE user_id = ? AND subject = ? AND JSON_CONTAINS(?, JSON_QUOTE(knowledge_point)) ORDER BY updated_at DESC LIMIT 1", [user["id"], row["subject"], Some(knowledge)]).rows
                let score = if (mastery.isEmpty()) { 0.0 } else { Float64.parse(rowText(mastery[0], "mastery_score")) }
                item.put("mastery_score", JsonFloat(score))
                item.put("mastery_status", JsonString(if (score >= 0.75) { "基本稳定" } else if (score >= 0.5) { "继续巩固" } else { "需要巩固" }))
                let asset = tx.query("SELECT path FROM question_assets WHERE question_id = ? AND kind IN ('crop','original') ORDER BY created_at DESC LIMIT 1", [Some(id)]).rows
                item.put("thumbnail_url", if (asset.isEmpty()) { JsonNull() } else { JsonString(accounts.mediaUrl("/" + rowText(asset[0], "path"))) })
                let job = tx.query("SELECT id,status FROM processing_jobs WHERE question_id = ? ORDER BY created_at DESC LIMIT 1", [Some(id)]).rows
                item.put("latest_job_id", if (job.isEmpty()) { JsonNull() } else { JsonString(rowText(job[0], "id")) })
                item.put("latest_job_status", if (job.isEmpty()) { JsonNull() } else { JsonString(rowText(job[0], "status")) })
                result.getItems().add(item)
            }
            return result
        })
    }
    throw ApiError(503, "数据库暂时不可用")
}
