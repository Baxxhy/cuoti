package zhiwei

import stdx.encoding.json.*
import std.unicode.UnicodeStringExtension

func adminSanitize(value: JsonValue): JsonValue {
    if (let Some(object) <- (value as JsonObject)) {
        let result=JsonObject()
        for ((key,item) in object.getFields()) {
            var sensitive=false; let lower=key.toLower()
            for (part in ["credential","password","secret","api_key","apikey","access_token","refresh_token","authorization","chain_of_thought","reasoning_content","raw_prompt","system_prompt"]) { if (lower.contains(part)) { sensitive=true } }
            if (!sensitive) { result.put(key,adminSanitize(item)) }
        }
        return result
    }
    if (let Some(array) <- (value as JsonArray)) { let result=JsonArray(); for (item in array.getItems()) { result.add(adminSanitize(item)) }; return result }
    return value
}

func adminTimestamp(value: JsonValue): JsonValue {
    if (let Some(text) <- (value as JsonString)) {
        var raw=text.getValue()
        if (raw.endsWith("+00:00")) { raw=raw[..raw.size-6] }
        if (raw.endsWith(".000000")) { raw=raw[..raw.size-7] }
        return JsonString(raw)
    }
    return value
}

func adminFields(source: JsonObject, keys: Array<String>): JsonObject {
    let result=JsonObject(); for (key in keys) { result.put(key,if (key=="created_at" || key=="updated_at" || key=="due_at") { adminTimestamp(source.get(key) ?? JsonNull()) } else { source.get(key) ?? JsonNull() }) }; return result
}

func adminLabel(kind: String, key: String): String {
    let labels=(JsonValue.fromStr(##"{"agent":{"mindtrace_tutor":"教学决策智能体","diagnosis":"错因诊断智能体","cognition":"认知建模智能体"},"branch":{"guided_question":"引导式提问","direct_explanation":"直接讲解","worked_example":"例题示范","visualization":"可视化讲解","teach_back":"学生复述","near_transfer":"近迁移检验","far_transfer":"远迁移检验","review_schedule":"安排复习"},"tool":{"knowledge_search":"知识检索","step_alignment":"步骤对齐","visualization":"生成教学图示","rediagnose":"动态再诊断","answer_reveal":"答案与步骤核对","answer_check":"数学结论验证","variant_generator":"生成迁移题","cognition_update":"更新认知状态","review_scheduler":"生成复习计划"}}"##) as JsonObject).getOrThrow()
    let value=tutorObject(labels,kind).get(key) ?? JsonString(key); return (value as JsonString).getOrThrow().getValue()
}

func adminTrace(db: Database, sessionId: String): JsonArray {
    let trace=JsonArray()
    for (row in db.query("SELECT * FROM agent_runs WHERE session_id=? ORDER BY created_at,id",[Some(sessionId)]).rows) {
        let run=rowJson("agent_runs",row); let result=tutorObject(run,"result"); let item=JsonObject(); let branch=tutorText(result,"branch")
        item.put("id",run["id"]); item.put("time",adminTimestamp(run["created_at"])); item.put("agent",JsonString(adminLabel("agent",jsonText(run,"agent_name")))); item.put("status",run["status"])
        item.put("decision",JsonString(if (branch.isEmpty()) { "完成一次决策" } else { adminLabel("branch",branch) }))
        item.put("goal",JsonString(if (tutorText(result,"next_goal").isEmpty()) { tutorText(result,"goal") } else { tutorText(result,"next_goal") }))
        for (key in ["observation","plan","verification"]) { item.put(key,adminSanitize(result.get(key) ?? JsonObject())) }
        let actions=JsonArray()
        for (callRow in db.query("SELECT * FROM agent_tool_calls WHERE agent_run_id=? ORDER BY created_at,id",[row["id"]]).rows) {
            let call=rowJson("agent_tool_calls",callRow); let action=JsonObject(); action.put("id",call["id"]); action.put("tool",JsonString(adminLabel("tool",jsonText(call,"tool_name"))))
            action.put("input",adminSanitize(call.get("input_json") ?? JsonObject())); action.put("output",adminSanitize(call.get("output_json") ?? JsonObject())); actions.add(action)
        }
        item.put("actions",actions); trace.add(item)
    }
    return trace
}
