package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.json.*

func stripWhitespace(value: String): String {
    let characters = ArrayList<String>()
    for (rune in value.runes()) {
        let one = StringBuilder(); one.append(rune); characters.add(one.toString())
    }
    var start: Int64 = 0
    var end = characters.size
    while (start < end && pythonWhitespace.contains(characters[start])) { start++ }
    while (end > start && pythonWhitespace.contains(characters[end - 1])) { end-- }
    let result = StringBuilder()
    for (index in start..end) { result.append(characters[index]) }
    return result.toString()
}

func editText(value: JsonValue, limit: Int64, minimum!: Int64 = 0, trim!: Bool = false, nullable!: Bool = false): JsonValue {
    if (nullable && value is JsonNull) { return value }
    if (let Some(text) <- (value as JsonString)) {
        let raw = if (trim) { stripWhitespace(text.getValue()) } else { text.getValue() }
        let count = runeCount(raw)
        if (count >= minimum && count <= limit) { return JsonString(raw) }
    }
    throw ApiError(422, "输入文字格式或长度不正确")
}

func editNumber(value: JsonValue): Float64 {
    try {
        let number = if (let Some(text) <- (value as JsonString)) { Float64.parse(text.getValue()) }
            else if (let Some(flag) <- (value as JsonBool)) { if (flag.getValue()) { 1.0 } else { 0.0 } }
            else if (value is JsonInt || value is JsonFloat) { Float64.parse(value.toString()) }
            else { throw ApiError(422, "数字格式不正确") }
        if (number >= -1.7976931348623157e308 && number <= 1.7976931348623157e308) { return number }
    } catch (_: Exception) { throw ApiError(422, "数字格式不正确") }
    throw ApiError(422, "数字必须有限")
}

func editBool(value: JsonValue): JsonBool {
    if (let Some(flag) <- (value as JsonBool)) { return flag }
    if (value is JsonInt || value is JsonFloat) {
        let number = editNumber(value)
        if (number == 0.0 || number == 1.0) { return JsonBool(number == 1.0) }
    }
    if (let Some(text) <- (value as JsonString)) {
        let word = text.getValue().toAsciiLower()
        for (yes in ["1", "true", "t", "yes", "y", "on"]) { if (word == yes) { return JsonBool(true) } }
        for (no in ["0", "false", "f", "no", "n", "off"]) { if (word == no) { return JsonBool(false) } }
    }
    throw ApiError(422, "收藏状态格式不正确")
}

func validateEditSteps(array: JsonArray, teacher: Bool): Unit {
    for (item in array.getItems()) {
        if (item is JsonString) { editText(item, 12000); continue }
        if (let Some(object) <- (item as JsonObject)) {
            let texts = if (teacher) { ["comment"] } else { ["text", "raw_text", "normalized_text", "formula"] }
            for (key in texts) { if (let Some(value) <- object.get(key)) { editText(value, 12000) } }
            let small = if (teacher) { "mark_type" } else { "source" }
            if (let Some(value) <- object.get(small)) { editText(value, 50) }
            if (let Some(value) <- object.get("confidence")) {
                let number = editNumber(value)
                if (!(number >= 0.0 && number <= 1.0)) { throw ApiError(422, "置信度超出范围") }
            }
            if (let Some(value) <- object.get("bbox")) {
                if (let Some(box) <- (value as JsonArray)) {
                    if (box.getItems().size > 4) { throw ApiError(422, "坐标数量不正确") }
                    for (number in box.getItems()) { editNumber(number) }
                } else { throw ApiError(422, "坐标格式不正确") }
            }
        } else { throw ApiError(422, "步骤格式不正确") }
    }
}

public func validateQuestionEdit(body: JsonObject): JsonObject {
    let result = JsonObject()
    for ((key, value) in body.getFields()) {
        match (key) {
            case "question_text" => result.put(key, editText(value, 12000, minimum: 1, trim: true))
            case "student_answer" => result.put(key, editText(value, 12000, nullable: true))
            case "grade" => result.put(key, editText(value, 30, nullable: true))
            case "subject" => result.put(key, editText(value, 30, minimum: 1, trim: true))
            case "question_type" => result.put(key, editText(value, 50, minimum: 1))
            case "title" => result.put(key, editText(value, 255))
            case "favorite" => result.put(key, editBool(value))
            case "tags" | "formulas" | "knowledge_points" | "options" | "student_steps" | "teacher_marks" =>
                let max = if (key == "options") { 26 } else if (key == "tags" || key == "knowledge_points") { 50 } else { 100 }
                let array = manualArray(body, key, max)
                let clean = JsonArray()
                let optionLabels=HashSet<String>()
                if (key == "student_steps" || key == "teacher_marks") {
                    // The original PATCH validates these but changes work only via dedicated endpoints.
                    validateEditSteps(array, key == "teacher_marks")
                } else {
                    for (item in array.getItems()) {
                        if (key == "options") {
                            if (let Some(option) <- (item as JsonObject)) {
                                let entry = JsonObject()
                                let label = option.get("label") ?? JsonNull()
                                let text = option.get("text") ?? JsonNull()
                                entry.put("label", editText(label, 8, minimum: 1, trim: true))
                                let optionLabel=(entry["label"] as JsonString).getOrThrow().getValue()
                                if (optionLabels.contains(optionLabel)) { throw ApiError(422,"选项标记不能重复") }
                                optionLabels.add(optionLabel)
                                entry.put("text", editText(text, 12000))
                                clean.getItems().add(entry)
                            } else { throw ApiError(422, "选项格式不正确") }
                        } else if (key == "formulas") { clean.getItems().add(editText(item, 12000)) }
                        else { clean.getItems().add(editText(item, 30, minimum: 1, trim: true)) }
                    }
                    result.put(key, clean)
                }
            case _ => ()
        }
    }
    return result
}

func jsonEquivalent(left: JsonValue, right: JsonValue): Bool {
    if (let Some(a) <- (left as JsonObject)) {
        if (let Some(b) <- (right as JsonObject)) {
            if (a.getFields().size != b.getFields().size) { return false }
            for ((key, value) in a.getFields()) {
                if (let Some(other) <- b.get(key)) { if (!jsonEquivalent(value, other)) { return false } }
                else { return false }
            }
            return true
        }
        return false
    }
    if (let Some(a) <- (left as JsonArray)) {
        if (let Some(b) <- (right as JsonArray)) {
            if (a.getItems().size != b.getItems().size) { return false }
            for (i in 0..a.getItems().size) { if (!jsonEquivalent(a[i], b[i])) { return false } }
            return true
        }
        return false
    }
    return left.toString() == right.toString()
}
