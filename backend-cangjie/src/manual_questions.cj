package zhiwei

import std.collection.*
import std.convert.*
import stdx.net.http.*
import stdx.encoding.json.*

func runeCount(value: String): Int64 {
    var count: Int64 = 0
    for (_ in value.runes()) { count++ }
    return count
}

func optionalAnswer(body: JsonObject): String {
    if (let Some(value) <- body.get("student_answer")) {
        if (let Some(text) <- (value as JsonString)) {
            if (runeCount(text.getValue()) <= 6000) { return stripWhitespace(text.getValue()) }
        }
        throw ApiError(422, "作答必须为不超过 6000 字的文字")
    }
    return ""
}

func manualArray(body: JsonObject, key: String, limit: Int64): JsonArray {
    if (let Some(value) <- body.get(key)) {
        if (let Some(array) <- (value as JsonArray)) {
            if (array.getItems().size <= limit) { return array }
        }
        throw ApiError(422, "${key} 格式或数量不正确")
    }
    return JsonArray()
}

public func createManualQuestion(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context, "POST")
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        if (rowText(user, "role") != "student") { throw ApiError(403, "请使用学生账号记录错题") }
        let body = readJson(context, maxBytes: 8 * 1024 * 1024)
        let text = textField(body, "question_text", 12000)
        let subject = textField(body, "subject", 30, fallback: Some("数学"))
        let kind = textField(body, "question_type", 50, fallback: Some("综合题"))
        if (kind != "综合题" && kind != "单选题" && kind != "多选题") { throw ApiError(422, "题目类型不正确") }
        var grade: Option<String> = None
        if (let Some(value) <- body.get("grade")) {
            if (let Some(item) <- (value as JsonString)) {
                if (runeCount(item.getValue()) > 30) { throw ApiError(422, "年级过长") }
                grade = Some(item.getValue())
            } else if (!(value is JsonNull)) { throw ApiError(422, "年级格式不正确") }
        }
        let answer = optionalAnswer(body)
        let options = manualArray(body, "options", 8)
        if ((kind == "综合题" && !options.getItems().isEmpty()) ||
            (kind != "综合题" && options.getItems().size < 2)) {
            throw ApiError(422, "题目类型和选项数量不匹配")
        }
        let labels = HashSet<String>()
        let validatedOptions = JsonArray()
        for (item in options.getItems()) {
            if (let Some(option) <- (item as JsonObject)) {
                let label = textField(option, "label", 1, trim: false)
                if (!"ABCDEFGH".contains(label) || labels.contains(label)) { throw ApiError(422, "选项标记无效或重复") }
                labels.add(label)
                let clean = JsonObject()
                clean.put("label", JsonString(label))
                clean.put("text", JsonString(textField(option, "text", 12000)))
                validatedOptions.getItems().add(clean)
            } else { throw ApiError(422, "选项格式不正确") }
        }
        let steps = ArrayList<String>()
        for (item in manualArray(body, "student_steps", 30).getItems()) {
            if (let Some(value) <- (item as JsonString)) {
                let clean = stripWhitespace(value.getValue())
                if (clean.isEmpty() || runeCount(clean) > 12000) { throw ApiError(422, "步骤文字长度不正确") }
                steps.add(clean)
            } else { throw ApiError(422, "步骤必须为文字") }
        }
        let title = StringBuilder()
        var count: Int64 = 0
        for (rune in text.runes()) {
            if (count >= 80) { break }
            title.append(rune)
            count++
        }
        let id = newId()
        let workId = newId()
        let studentGrade = grade
        db.transaction<Unit>({ tx =>
            tx.query("INSERT INTO questions (id,user_id,subject,grade,title,question_text,student_answer,status,confirmed,favorite,tags,formulas,options,question_type,knowledge_points,created_at,updated_at) VALUES (?,?,?,?,?,?,?,'confirmed',1,0,JSON_ARRAY(),JSON_ARRAY(),?,?,JSON_ARRAY(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                [Some(id), user["id"], Some(subject), studentGrade, Some(title.toString()), Some(text),
                 if (answer.isEmpty()) { None } else { Some(answer) }, Some(validatedOptions.toString()), Some(kind)])
            tx.query("INSERT INTO student_works (id,question_id,user_id,answer,explanation,created_at,updated_at) VALUES (?,?,?,?,'',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",
                [Some(workId), Some(id), user["id"], Some(answer)])
            for (index in 0..steps.size) {
                let step = steps[index]
                tx.query("INSERT INTO student_steps (id,work_id,step_index,text,bbox,raw_text,normalized_text,formula,confidence,source,user_confirmed,created_at,updated_at) VALUES (?,?,?,?,JSON_ARRAY(),?,?,?,1,'user',1,UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                    [Some(newId()), Some(workId), Some(index.toString()), Some(step), Some(step), Some(step),
                     Some(if (step.contains("=")) { step } else { "" })])
            }
            ()
        })
        let result = JsonObject()
        result.put("id", JsonString(id))
        result.put("status", JsonString("confirmed"))
        return result
    }
    throw ApiError(503, "数据库暂时不可用")
}
