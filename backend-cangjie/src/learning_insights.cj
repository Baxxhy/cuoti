package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.json.*
import stdx.encoding.url.*
import stdx.net.http.*

// JSON encoding makes compound keys unambiguous even when labels contain separators.
func insightPair(subject: String, label: String): String {
    let pair = JsonArray(); pair.getItems().add(JsonString(subject)); pair.getItems().add(JsonString(label)); return pair.toString()
}

func insightQuery(context: HttpContext): Form {
    try { return Form(context.request.url.rawQuery ?? "") }
    catch (_: Exception) { throw ApiError(422,"查询参数格式不正确") }
}

func insightDays(form: Form, fallback: Int64, maximum: Int64): Int64 {
    let raw = queryLast(form,"days")
    if (form.getAll("days").isEmpty()) { return fallback }
    let value = try { Int64.parse(stripWhitespace(raw)) } catch (_: Exception) { throw ApiError(422,"days 必须是整数") }
    if (value < 1 || value > maximum) { throw ApiError(422,"days 超出允许范围") }
    return value
}

func canonicalMistakeLabel(value: String): String {
    if (value.contains("移项") && (value.contains("符号") || value.contains("变号"))) { return "移项符号" }
    return value
}

func learningMethodLabel(value: String): String {
    match (value) {
        case "socratic" => "逐步提问"
        case "micro_activity" => "小步练习"
        case "assisted_progression" => "分步辅助练习"
        case "independent_dataset_practice" => "独立完成题库练习"
        case "teacher_review" => "教师复核指导"
        case "incremental_hint" => "分层提示"
        case "understanding_check_prompt" => "理解检查"
        case "preserve_correct_part" => "保留正确部分再提示"
        case "visual_counterexample" => "图形演示和反例"
        case "prerequisite_example" => "补充基础例子"
        case "temporary_rediagnosis" => "重新分析题目"
        case "answer_with_explanation" => "结合答案讲解"
        case "targeted_remediation" => "针对错误讲解"
        case "guided" => "逐步引导"
        case "" => "尚未确定"
        case _ => value
    }
}

func insightLearnerText(value: String): String {
    let text = if (value.isEmpty()) { "根据最近的学习情况更新" } else { value }
    return text.replace("教回","讲解思路").replace("近迁移","相似题").replace("远迁移","综合题").replace("提示等级","使用提示")
}

func learningAnalytics(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let days = insightDays(insightQuery(context),14,365)
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let mastery = JsonArray(); let mistakes = JsonArray(); let trend = JsonArray()
            let seenPoints = HashSet<String>()
            for (row in tx.query("SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at DESC,id DESC",[user["id"]]).rows) {
                let key = insightPair(rowText(row,"subject"),rowText(row,"knowledge_point"))
                if (seenPoints.contains(key)) { continue }; seenPoints.add(key)
                mastery.getItems().add(rowJson("mastery_states",row))
            }
            let seenMistakes = HashSet<String>()
            for (row in tx.query("SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id",[user["id"]]).rows) {
                let label = canonicalMistakeLabel(rowText(row,"label")); let key = insightPair(rowText(row,"subject"),label)
                if (seenMistakes.contains(key)) { continue }; seenMistakes.add(key)
                let item = rowJson("misconception_states",row); item.put("label",JsonString(label))
                for (field in ["successful_strategy","failed_strategy"]) {
                    let raw = tutorText(item,field)
                    item.put(field,JsonString(if (raw.isEmpty()) { "" } else { learningMethodLabel(raw) }))
                }
                mistakes.getItems().add(item)
            }
            // Keep the original rolling UTC window and group by UTC date, not local midnight.
            let rows = tx.query("SELECT DATE(created_at) AS day,AVG(new_value) AS average,COUNT(*) AS count FROM cognitive_updates WHERE user_id=? AND entity_type='mastery' AND created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) GROUP BY DATE(created_at) ORDER BY day",[user["id"],Some((1-days).toString())]).rows
            var evidenceCount: Int64 = 0
            for (row in rows) {
                let count = Int64.parse(rowText(row,"count")); evidenceCount += count
                let average = Float64.parse(rowText(row,"average"))
                let item = JsonObject(); item.put("date",JsonString(rowText(row,"day")))
                item.put("score",JsonFloat(Float64(Int64(average*1000.0+0.5))/10.0)); item.put("evidence_count",JsonInt(count)); trend.getItems().add(item)
            }
            let summary = JsonObject(); summary.put("knowledge_count",JsonInt(mastery.getItems().size)); summary.put("misconception_count",JsonInt(mistakes.getItems().size)); summary.put("evidence_count",JsonInt(evidenceCount))
            let result = JsonObject(); result.put("mastery",mastery); result.put("misconceptions",mistakes); result.put("trend",trend); result.put("summary",summary)
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func knowledgeCards(context: HttpContext): JsonValue {
    requireMethod(context,"GET")
    let form = insightQuery(context); let subject = queryLast(form,"subject"); let grade = queryLast(form,"grade"); let misconception = queryLast(form,"misconception")
    let words = ArrayList<String>(); let word = StringBuilder()
    // Match Python Unicode split, including Chinese separators.
    for (rune in queryLast(form,"q").runes()) {
        let one = StringBuilder(); one.append(rune); let character = one.toString()
        if (pythonWhitespace.contains(character) || character == "，" || character == "、") {
            if (runeCount(word.toString()) >= 2 && words.size < 5) { words.add(word.toString()) }; word.reset()
        } else { word.append(rune) }
    }
    if (runeCount(word.toString()) >= 2 && words.size < 5) { words.add(word.toString()) }
    let sql = StringBuilder(); sql.append("SELECT * FROM knowledge_points WHERE 1=1")
    let params = ArrayList<Option<String>>()
    if (!subject.isEmpty()) { sql.append(" AND subject=?"); params.add(Some(subject)) }
    if (!words.isEmpty()) {
        sql.append(" AND (")
        for (index in 0..words.size) {
            if (index > 0) { sql.append(" OR ") }
            sql.append("(name LIKE ? OR code LIKE ? OR CAST(content AS CHAR) LIKE ?)")
            for (_ in 0..3) { params.add(Some("%"+words[index]+"%")) }
        }
        sql.append(")")
    }
    if (!grade.isEmpty()) { sql.append(" AND LOCATE(?,JSON_UNQUOTE(JSON_EXTRACT(content,'$.grade'))) > 0"); params.add(Some(grade)) }
    if (!misconception.isEmpty()) { sql.append(" AND LOCATE(?,JSON_UNQUOTE(JSON_EXTRACT(content,'$.common_misconceptions'))) > 0"); params.add(Some(misconception)) }
    sql.append(" ORDER BY subject,code LIMIT 50")
    try (db = Database.fromEnvironment()) {
        let result = JsonArray()
        for (row in db.query(sql.toString(),params.toArray()).rows) {
            let item = rowJson("knowledge_points",row); let content = tutorObject(item,"content")
            if (!grade.isEmpty() && !tutorAnswerText(content.get("grade") ?? JsonString("")).contains(grade)) { continue }
            if (!misconception.isEmpty()) {
                let labels = StringBuilder()
                if (let Some(array) <- ((content.get("common_misconceptions") ?? JsonArray()) as JsonArray)) {
                    for (label in array.getItems()) { if (!labels.toString().isEmpty()) { labels.append(" ") }; labels.append(tutorAnswerText(label)) }
                }
                if (!labels.toString().contains(misconception)) { continue }
            }
            result.getItems().add(item)
        }
        return result
    }
    throw ApiError(503,"数据库暂时不可用")
}

func readKnowledgeCard(context: HttpContext): JsonValue {
    requireMethod(context,"GET")
    let parts = context.request.url.path.split("/")
    let code = parts[parts.size-1]
    try (db = Database.fromEnvironment()) {
        return db.transaction<JsonValue>({ tx =>
            let rows = tx.query("SELECT * FROM knowledge_points WHERE code=? LIMIT 1",[Some(code)]).rows
            if (rows.isEmpty()) { throw ApiError(404,"知识卡不存在") }
            let result = rowJson("knowledge_points",rows[0]); let id = rows[0]["id"]
            for ((key,sql) in [("prerequisites","SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON k.id=r.target_id WHERE r.source_id=?"),("next_knowledge","SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON k.id=r.source_id WHERE r.target_id=?")]) {
                let values = JsonArray()
                for (row in tx.query(sql,[id]).rows) { values.getItems().add(rowJson("knowledge_points",row)) }
                result.put(key,values)
            }
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
