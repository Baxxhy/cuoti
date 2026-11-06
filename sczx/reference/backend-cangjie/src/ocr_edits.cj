package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

func stepObject(item: JsonValue, teacher: Bool): JsonObject {
    if (let Some(object) <- (item as JsonObject)) { return object }
    let result = JsonObject()
    result.put(if (teacher) { "comment" } else { "text" }, item)
    return result
}

func editedBbox(object: JsonObject): JsonArray {
    let result = JsonArray()
    let source = (object.get("bbox") ?? JsonArray()) as JsonArray
    for (value in source.getOrThrow().getItems()) { result.getItems().add(JsonFloat(editNumber(value))) }
    return result
}

func stepText(item: JsonValue): String {
    let object = stepObject(item, false)
    return ((object.get("text") ?? object.get("raw_text") ?? JsonString("")) as JsonString).getOrThrow().getValue()
}

func choiceStepAnswer(steps: JsonArray, options: JsonValue): Option<String> {
    let texts = ArrayList<String>()
    for (item in steps.getItems()) {
        let text = stripWhitespace(stepText(item))
        if (!text.isEmpty()) { texts.add(text.toAsciiUpper()) }
    }
    if (texts.size != 1) { return None }
    let known = HashSet<String>()
    if (let Some(array) <- (options as JsonArray)) {
        for (item in array.getItems()) {
            if (let Some(object) <- (item as JsonObject)) {
                let value = object.get("label") ?? object.get("key") ?? JsonString("")
                if (let Some(text) <- (value as JsonString)) { known.add(text.getValue().toAsciiUpper()) }
            }
        }
    }
    let labels = ArrayList<String>()
    var expectLabel = true
    for (rune in texts[0].runes()) {
        let builder = StringBuilder(); builder.append(rune); let one = builder.toString()
        if (pythonWhitespace.contains(one)) { continue }
        if (expectLabel) {
            if (!"ABCDEFGHIJKLMNOPQRSTUVWXYZ".contains(one) || (!known.isEmpty() && !known.contains(one))) { return None }
            if (!labels.contains(one)) { labels.add(one) }
        } else if (!(one == "、" || one == "," || one == "，")) { return None }
        expectLabel = !expectLabel
    }
    if (expectLabel || labels.isEmpty()) { return None }
    return Some(String.join(labels.toArray(), delimiter: "、"))
}

public func saveOcrEdits(context: HttpContext, accounts: Accounts, confirm: Bool): JsonValue {
    requireMethod(context, "POST")
    let parts = context.request.url.path.split("/")
    let id = parts[parts.size - 2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        let body = readJson(context, maxBytes: 8 * 1024 * 1024, defaultEmpty: true)
        let validated = validateQuestionEdit(body)
        db.transaction<Unit>({ tx =>
            let rows = tx.query("SELECT * FROM questions WHERE id = ? AND user_id = ? FOR UPDATE", [Some(id), user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404, "题目不存在或无权访问") }
            if (rowText(rows[0], "status") == "archived") { throw ApiError(409, "题目已归档，不能修改") }
            let existing = rowJson("questions", rows[0])
            let edits = JsonObject()
            for (key in ["question_text","subject","formulas","options","question_type","knowledge_points"]) {
                if (let Some(value) <- validated.get(key)) { edits.put(key, value) }
            }
            let steps = manualArray(body, "student_steps", 100)
            var answer = ""
            if (let Some(value) <- validated.get("student_answer")) {
                if (let Some(text) <- (value as JsonString)) { answer = stripWhitespace(text.getValue()) }
            }
            let typeName = ((edits.get("question_type") ?? existing["question_type"]) as JsonString).getOrThrow().getValue()
            var normalizedSteps = steps
            if (answer.isEmpty() && (typeName.contains("选择") || typeName.toAsciiLower().contains("choice") || typeName.toAsciiLower().contains("multiple"))) {
                if (let Some(inferred) <- choiceStepAnswer(steps, edits.get("options") ?? existing["options"])) {
                    answer = inferred; normalizedSteps = JsonArray()
                }
            }
            if (validated.get("student_answer").isSome()) { edits.put("student_answer", if (answer.isEmpty()) { JsonNull() } else { JsonString(answer) }) }
            if (let Some(value) <- validated.get("grade")) {
                edits.put("grade", if (let Some(text) <- (value as JsonString)) { if (text.getValue().isEmpty()) { JsonNull() } else { JsonString(stripWhitespace(text.getValue())) } } else { JsonNull() })
            }
            var changed = false
            for ((key,value) in edits.getFields()) { if (!jsonEquivalent(existing[key],value)) { changed = true } }
            if (body.get("student_steps").isSome()) {
                let previous = tx.query("SELECT s.text FROM student_steps s WHERE s.work_id = (SELECT id FROM student_works WHERE question_id = ? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY s.step_index", [Some(id)]).rows
                if (previous.size != normalizedSteps.getItems().size) { changed = true }
                else { for (index in 0..previous.size) { if (rowText(previous[index],"text") != stepText(normalizedSteps[index])) { changed = true } } }
                let work = newId()
                let currentAnswer = edits.get("student_answer") ?? existing["student_answer"]
                tx.query("INSERT INTO student_works (id,question_id,user_id,answer,explanation,created_at,updated_at) VALUES (?,?,?,?,'',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))", [Some(work),Some(id),user["id"],Some(if (let Some(text) <- (currentAnswer as JsonString)) { text.getValue() } else { "" })])
                for (index in 0..normalizedSteps.getItems().size) {
                    let object = stepObject(normalizedSteps[index],false)
                    let text = stepText(object)
                    let raw = ((object.get("raw_text") ?? JsonString(text)) as JsonString).getOrThrow().getValue()
                    let bbox = editedBbox(object)
                    let confidence = editNumber(object.get("confidence") ?? JsonInt(1))
                    let source = ((object.get("source") ?? JsonString("user")) as JsonString).getOrThrow().getValue()
                    tx.query("INSERT INTO student_steps (id,work_id,step_index,text,bbox,raw_text,normalized_text,formula,confidence,source,user_confirmed,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,1,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))", [Some(newId()),Some(work),Some(index.toString()),Some(text),Some(bbox.toString()),Some(raw),Some(collapseWhitespace(text)),Some(if (text.contains("=")) { text } else { "" }),Some(confidence.toString()),Some(source)])
                }
            }
            if (body.get("teacher_marks").isSome()) {
                tx.query("DELETE FROM teacher_marks WHERE question_id = ?", [Some(id)])
                for (item in manualArray(body,"teacher_marks",100).getItems()) {
                    let object = stepObject(item,true)
                    tx.query("INSERT INTO teacher_marks (id,question_id,mark_type,comment,bbox,confidence,source,created_at,updated_at) VALUES (?,?,?,?,?,?,'user',UTC_TIMESTAMP(),UTC_TIMESTAMP())", [Some(newId()),Some(id),Some(((object.get("mark_type") ?? JsonString("comment")) as JsonString).getOrThrow().getValue()),Some(((object.get("comment") ?? JsonString("")) as JsonString).getOrThrow().getValue()),Some(editedBbox(object).toString()),Some(editNumber(object.get("confidence") ?? JsonInt(1)).toString())])
                }
            }
            let text = ((edits.get("question_text") ?? existing["question_text"]) as JsonString).getOrThrow().getValue()
            if (confirm && stripWhitespace(text).isEmpty()) { throw ApiError(422, "请先补充题目文字再确认") }
            tx.query("UPDATE processing_jobs SET status = 'cancelled',error = '题目已人工核对，旧识别结果未应用',updated_at = UTC_TIMESTAMP() WHERE question_id = ? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running')", [Some(id)])
            if (changed) { invalidateQuestionLearning(tx,id) }
            let sql = StringBuilder(); let params = ArrayList<Option<String>>()
            sql.append("UPDATE questions SET updated_at = UTC_TIMESTAMP(),status = ?")
            params.add(Some(if (confirm) { "confirmed" } else { "ocr_draft" }))
            if (confirm) { sql.append(",confirmed = 1") }
            for ((key,value) in edits.getFields()) {
                sql.append(", `${key}` = ?")
                params.add(if (value is JsonNull) { None } else if (let Some(textValue) <- (value as JsonString)) { Some(textValue.getValue()) } else { Some(value.toString()) })
            }
            sql.append(" WHERE id = ?"); params.add(Some(id)); tx.query(sql.toString(),params.toArray())
            ()
        })
        return questionDetail(context,accounts,id)
    }
    throw ApiError(503,"数据库暂时不可用")
}
