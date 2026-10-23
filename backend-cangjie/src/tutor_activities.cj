package zhiwei

import std.collection.*
import std.fs.*
import stdx.encoding.json.*

func teachingTemplates(): JsonObject {
    return (JsonValue.fromStr(String.fromUtf8(File.readFrom("schema/teaching_templates.json"))) as JsonObject).getOrThrow()
}

func tutorStringArray(values: Array<String>): JsonArray {
    let result = JsonArray()
    for (value in values) { result.add(JsonString(value)) }
    return result
}

func tutorOptions(values: Array<(String,String)>): JsonArray {
    let result = JsonArray()
    for ((value,label) in values) {
        let item = JsonObject(); item.put("value",JsonString(value)); item.put("label",JsonString(label)); result.add(item)
    }
    return result
}

func tutorActivity(id: String, title: String, question: String, options: Array<(String,String)>,
    answers: Array<String>, hint: String, teaching: String): JsonObject {
    let result = (teachingTemplates()["activity_defaults"] as JsonObject).getOrThrow()
    result.put("id",JsonString(id)); result.put("title",JsonString(title)); result.put("question",JsonString(question))
    result.put("options",tutorOptions(options)); result.put("correct_answers",tutorStringArray(answers))
    result.put("hint",JsonString(hint)); result.put("teaching",JsonString(teaching))
    return result
}

func tutorTopic(points: Array<String>, questionType: String): String {
    let raw = stripWhitespace(if (points.isEmpty()) { if (questionType.isEmpty()) { "错题学习" } else { questionType } } else { points[0] })
    let labels = (teachingTemplates()["question_type_labels"] as JsonObject).getOrThrow()
    if (let Some(value) <- labels.get(raw)) { return (value as JsonString).getOrThrow().getValue() }
    return if (raw.isEmpty()) { "错题学习" } else { raw }
}

func buildUnderstandingPlan(text: String, subject: String, questionType: String,
    knowledgePoints: Array<String>, referenceSteps: Array<String>): JsonArray {
    let points = ArrayList<String>(); let references = ArrayList<String>()
    let context = StringBuilder(); context.append(text)
    for (item in knowledgePoints) {
        if (!stripWhitespace(item).isEmpty()) { points.add(item); context.append(" "); context.append(item) }
    }
    for (item in referenceSteps) {
        if (!stripWhitespace(item).isEmpty()) { references.add(item); context.append(" "); context.append(item) }
    }
    let templates = teachingTemplates(); let combined = context.toString()
    if (combined.contains("正方体") && (combined.contains("展开图") || combined.contains("相对面"))) {
        return (templates["cube_plan"] as JsonArray).getOrThrow()
    }
    let prompts = (templates["guided_prompts"] as JsonObject).getOrThrow()
    let prompt = (prompts.get(subject).getOrDefault({ => prompts["数学"] }) as JsonString).getOrThrow().getValue()
    let topic = if (points.isEmpty()) { tutorTopic([],questionType) } else { points[0] }
    let reference = if (references.isEmpty()) { prompt } else { references[0] }
    let plan = JsonArray()
    plan.add(tutorActivity("understanding-1","先抓住${topic}","完成这道题时，第一步最应该关注什么？",
        [("key",topic),("answer","只记住最后答案"),("skip","跳过题目条件直接计算")], ["key"],
        "先回到题目条件，找到与${topic}直接相关的信息。","这道题先围绕“${topic}”判断，再继续后面的步骤。"))
    plan.add(tutorActivity("understanding-2","确认下一步做法","下面哪种做法更合适？",
        [("reference",academicSummary(reference,42)),("guess","不看条件，凭印象猜一个答案")], ["reference"],prompt,"关键做法是：${reference}"))
    return plan
}

func publicTutorActivity(activity: JsonObject, attempt: Int64, feedback!: String = "", teaching!: String = ""): JsonObject {
    let result = JsonObject()
    for (key in ["id","type","title","question"]) { result.put(key,activity[key]) }
    for (key in ["options","keywords"]) { result.put(key,activity.get(key).getOrDefault({ => JsonArray() })) }
    result.put("visual",activity.get("visual").getOrDefault({ => JsonObject() }))
    result.put("attempt",JsonInt(attempt)); result.put("max_attempts",JsonInt(2))
    result.put("feedback",JsonString(feedback))
    result.put("teaching",if (teaching.isEmpty()) { activity.get("teaching").getOrDefault({ => JsonString("") }) } else { JsonString(teaching) })
    for (key in ["teaching_title","sentence_starter","input_mode","variant_id"]) {
        if (let Some(value) <- activity.get(key)) { result.put(key,value) }
    }
    let filtered = JsonObject()
    for ((key,value) in result.getFields()) {
        if (key == "options" || key == "keywords" || key == "visual" ||
            (!(value is JsonNull) && !jsonEquivalent(value,JsonString("")))) { filtered.put(key,value) }
    }
    return filtered
}
