package zhiwei

import stdx.encoding.json.*

func paperInteger(value: JsonValue, minimum: Int64, maximum: Int64): Int64 {
    let number=editNumber(value)
    if (number<Float64(minimum) || number>Float64(maximum)) { throw ApiError(422,"整数超出允许范围") }
    let integer=Int64(number)
    if (number!=Float64(integer) || integer<minimum || integer>maximum) { throw ApiError(422,"整数超出允许范围") }
    return integer
}

func paperFilters(value: JsonValue): JsonObject {
    if (!(value is JsonObject)) { throw ApiError(422,"筛选条件格式不正确") }
    let source=(value as JsonObject).getOrThrow(); let result=JsonObject()
    for ((name,limit) in [("subject",30),("knowledge_point",100),("error_type",100)]) {
        if (let Some(item) <- source.get(name)) { result.put(name,editText(item,limit)) }
    }
    let low=editNumber(source.get("mastery_min") ?? JsonInt(0)); let high=editNumber(source.get("mastery_max") ?? JsonInt(1))
    if (low<0.0 || high>1.0 || low>high) { throw ApiError(422,"掌握度范围无效") }
    if (let Some(item) <- source.get("mastery_min")) { result.put("mastery_min",JsonFloat(low)) }
    if (let Some(item) <- source.get("mastery_max")) { result.put("mastery_max",JsonFloat(high)) }
    if (let Some(item) <- source.get("due_review")) { result.put("due_review",editBool(item)) }
    return result
}

func paperItems(value: JsonValue): JsonArray {
    if (!(value is JsonArray)) { throw ApiError(422,"试卷题目格式不正确") }
    let result=JsonArray(); let values=(value as JsonArray).getOrThrow()
    if (values.getItems().size>200) { throw ApiError(422,"试卷不能超过 200 题") }
    for (raw in values.getItems()) {
        if (!(raw is JsonObject)) { throw ApiError(422,"试卷题目格式不正确") }
        let item=(raw as JsonObject).getOrThrow(); let clean=JsonObject()
        clean.put("question_id",editText(item.get("question_id") ?? JsonNull(),36,minimum:1,trim:true))
        clean.put("score",JsonInt(paperInteger(item.get("score") ?? JsonInt(10),1,100))); result.add(clean)
    }
    return result
}

func paperPayload(body: JsonObject, creating: Bool): JsonObject {
    let result=JsonObject()
    if (let Some(title) <- body.get("title")) { result.put("title",editText(title,255,minimum:1,trim:true)) }
    if (let Some(filters) <- body.get("filters")) { result.put("filters",paperFilters(filters)) }
    if (let Some(items) <- body.get("items")) { result.put("items",paperItems(items)) }
    if (creating) {
        result.put("limit",JsonInt(paperInteger(body.get("limit") ?? JsonInt(10),1,200)))
        result.put("default_score",JsonInt(paperInteger(body.get("default_score") ?? JsonInt(10),1,100)))
        let ids=body.get("question_ids") ?? JsonArray()
        if (!(ids is JsonArray)) { throw ApiError(422,"题目编号格式不正确") }
        let clean=JsonArray(); let values=(ids as JsonArray).getOrThrow()
        if (values.getItems().size>200) { throw ApiError(422,"试卷不能超过 200 题") }
        for (value in values.getItems()) { clean.add(editText(value,36,minimum:1,trim:true)) }; result.put("question_ids",clean)
    }
    return result
}
