package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

func tutorStrings(value: JsonValue): Array<String> {
    let result = ArrayList<String>()
    for (item in (value as JsonArray).getOrThrow().getItems()) { result.add((item as JsonString).getOrThrow().getValue()) }
    return result.toArray()
}

func tutorRowTexts(value: JsonValue): Array<String> {
    let result = ArrayList<String>()
    for (item in (value as JsonArray).getOrThrow().getItems()) { result.add(jsonText((item as JsonObject).getOrThrow(),"text")) }
    return result.toArray()
}

func tutorKnowledge(snapshot: JsonObject): Array<String> {
    let analysis = (snapshot["analysis"] as JsonObject) ?? JsonObject()
    let points = tutorStrings(analysis.get("knowledge_points") ?? JsonArray())
    return if (points.isEmpty()) { tutorStrings((snapshot["question"] as JsonObject).getOrThrow()["knowledge_points"]) } else { points }
}

func tutorVisualization(subject: String, kind: String, points: Array<String>): JsonValue {
    let builder = StringBuilder(); builder.append(subject); builder.append(" "); builder.append(kind)
    for (point in points) { builder.append(" "); builder.append(point) }
    let text = builder.toString().toAsciiLower()
    for ((words,visual) in [("勾股|直角三角形","right_triangle"),("圆周角|圆心角|圆","circle"),
        ("坐标|中点|两点距离","coordinate_geometry"),("三角形|全等|相似","triangle"),
        ("二次函数|抛物线","quadratic_function"),("一次函数|直线函数","linear_function"),
        ("方程|等式|移项","equation_balance"),("匀加速|速度时间|v-t","uniform_acceleration"),
        ("抛体|平抛|斜抛","projectile_motion"),("匀速|路程|s=vt","uniform_motion"),
        ("受力|合力|支持力","force_diagram"),("机械能|动能|势能|功与能","work_energy"),
        ("压强|压力","pressure"),("浮力|排液","buoyancy"),("时间轴|年代|先后顺序","history_timeline"),
        ("时空|传播|地图","timeline_map")]) {
        for (word in words.split("|")) { if (text.contains(word)) { return JsonString(visual) } }
    }
    return JsonNull()
}

func tutorCompact(value: String): String {
    let builder = StringBuilder()
    for (rune in value.runes()) {
        let one = StringBuilder(); one.append(rune)
        if (!pythonWhitespace.contains(one.toString())) { builder.append(rune) }
    }
    return builder.toString()
}

func tutorChoiceAnswer(answer: String, options: JsonArray): String {
    let text = stripWhitespace(answer); let chars = ArrayList<String>()
    for (rune in text.toAsciiUpper().runes()) { let one = StringBuilder(); one.append(rune); chars.add(one.toString()) }
    let selected = StringBuilder()
    for (index in 0..chars.size) {
        let letter = chars[index]
        if (letter.size != 1 || !"ABCDEFGH".contains(letter)) { continue }
        if ((index > 0 && "ABCDEFGHIJKLMNOPQRSTUVWXYZ".contains(chars[index-1])) ||
            (index+1 < chars.size && "ABCDEFGHIJKLMNOPQRSTUVWXYZ".contains(chars[index+1]))) { continue }
        for (item in options.getItems()) {
            let option = (item as JsonObject).getOrThrow()
            if (stripWhitespace(jsonText(option,"label")).toAsciiUpper() == letter) { selected.append(letter); break }
        }
    }
    if (!selected.toString().isEmpty()) { return selected.toString() }
    let compact = tutorCompact(text)
    for (item in options.getItems()) {
        let option = (item as JsonObject).getOrThrow()
        if (!compact.isEmpty() && compact == tutorCompact(jsonText(option,"text"))) { return stripWhitespace(jsonText(option,"label")).toAsciiUpper() }
    }
    return text
}

func startTutorSnapshot(db: Database, id: String, owner: Option<String>): JsonObject {
    let snapshot = diagnosisSnapshot(db,id,owner)
    if (!(snapshot["analysis"] is JsonObject)) { throw ApiError(409,"请先完成题目分析，再开始学习") }
    let answer = jsonText((snapshot["analysis"] as JsonObject).getOrThrow(),"final_answer")
    if (stripWhitespace(answer).isEmpty() || answer.startsWith("需要根据完整题目")) { throw ApiError(409,"请先完成题目分析，再开始学习") }
    return snapshot
}

func initialTutorState(snapshot: JsonObject, policy: JsonObject, brief: JsonValue): JsonObject {
    let question = (snapshot["question"] as JsonObject).getOrThrow()
    let analysis = (snapshot["analysis"] as JsonObject).getOrThrow()
    let points = tutorKnowledge(snapshot)
    let state = (JsonValue.fromStr(##"{"understood":false,"understanding_passed":false,"teach_back":null,"near_transfer":null,"far_transfer":null,"next_goal":"完成一个小问题","strategy":"micro_activity","branch":"opening","mastery_proven":false,"last_message":"","repeated_count":0,"assisted":false,"understanding_index":0,"activity_attempts":{},"activity_feedback":"","answer_reveal_acknowledged":false,"targeted_check_pending":false}"##) as JsonObject).getOrThrow()
    state.put("teaching_policy",policy); state.put("teaching_brief",brief)
    state.put("subject",question["subject"]); state.put("question_type",question["question_type"])
    state.put("visualization_type",tutorVisualization(jsonText(question,"subject"),jsonText(question,"question_type"),tutorStrings(question["knowledge_points"])))
    state.put("understanding_plan",if (brief is JsonObject) { JsonArray() } else {
        buildUnderstandingPlan(jsonText(question,"question_text"),jsonText(question,"subject"),jsonText(question,"question_type"),points,tutorRowTexts(snapshot["references"])) })
    let reveal = JsonObject(); let rawAnswer = if (question["student_answer"] is JsonNull) { "" } else { jsonText(question,"student_answer") }
    var student = if (rawAnswer.isEmpty()) { "未作答" } else { rawAnswer }
    if (let Some(item) <- (brief as JsonObject)) {
        let kind = jsonText(policy,"question_type")
        if (kind == "choice" || kind == "multiple_choice") { student = tutorChoiceAnswer(rawAnswer,(question["options"] as JsonArray).getOrThrow()) }
        for (key in ["topic","correct_answer","key_explanation","option_explanations"]) { reveal.put(key,item[key]) }
    } else {
        reveal.put("topic",JsonString(tutorTopic(points,jsonText(question,"question_type"))))
        reveal.put("correct_answer",JsonString(stripWhitespace(jsonText(analysis,"final_answer"))))
        reveal.put("key_explanation",JsonString("")); reveal.put("option_explanations",JsonArray())
    }
    reveal.put("student_answer",JsonString(student)); state.put("answer_reveal",reveal)
    return state
}

public func startTutor(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db); let body = readJson(context)
        let id = if (let Some(value) <- body.get("question_id")) { (editText(value,36,minimum: 1) as JsonString).getOrThrow().getValue() } else { "" }
        let snapshot = db.transaction<JsonObject>({ tx => startTutorSnapshot(tx,id,user["id"]) })
        let question = (snapshot["question"] as JsonObject).getOrThrow(); let analysis = (snapshot["analysis"] as JsonObject).getOrThrow()
        let expected = diagnosisFingerprint(snapshot); let steps = tutorRowTexts(snapshot["steps"])
        let policy = adaptiveTeachingPolicy(jsonText(question,"question_type"),!(question["options"] as JsonArray).getOrThrow().getItems().isEmpty(),!steps.isEmpty(),jsonText(analysis,"final_answer"))
        var brief: JsonValue = JsonNull()
        if (jsonText(policy,"mode") == "compressed") {
            let input = JsonObject(); input.put("operation",JsonString("teaching_brief")); input.put("text",question["question_text"])
            for (key in ["student_answer","options"]) { input.put(key,question[key]) }
            input.put("question_type",policy["question_type"]); input.put("correct_answer",analysis["final_answer"])
            input.put("student_steps",tutorStringArray(steps)); input.put("knowledge_points",tutorStringArray(tutorKnowledge(snapshot)))
            input.put("diagnosis",if (snapshot["diagnosis"] is JsonObject) { snapshot["diagnosis"] } else { JsonObject() })
            brief = algorithmCompute(input)["brief"]
            if (!(brief is JsonObject)) { throw ApiError(503,"教学简报不完整") }
        }
        let state = initialTutorState(snapshot,policy,brief)
        return db.transaction<JsonValue>({ tx =>
            let current = startTutorSnapshot(tx,id,user["id"])
            if (!jsonEquivalent(diagnosisFingerprint(current),expected)) { throw ApiError(409,"题目或诊断已变化，请重新开始学习") }
            let sessionId = newId(); let opening = if (jsonText(policy,"mode") == "compressed") { "先看清正确答案和刚才选项的关键差别。" } else { "我们先只解决一个小问题。选出你认为正确的答案就可以。" }
            tx.query("INSERT INTO tutor_sessions (id,user_id,question_id,stage,hint_level,turn_count,mastery_score,state,status,created_at,updated_at) VALUES (?,?,?,'understanding',0,0,0,?,'active',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(sessionId),user["id"],Some(id),Some(state.toString())])
            tx.query("INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,'assistant',?,'understanding',?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(sessionId),Some(opening),Some(##"{"branch":"opening","next_goal":"解释首错步骤"}"##)])
            let toolOutput = JsonObject(); toolOutput.put("diagnosis_id",if (let Some(diagnosis) <- (snapshot["diagnosis"] as JsonObject)) { diagnosis["id"] } else { JsonNull() })
            let runResult = JsonObject(); runResult.put("branch",JsonString("opening")); runResult.put("diagnosis_id",toolOutput["diagnosis_id"])
            let toolInput = JsonObject(); toolInput.put("question_id",JsonString(id)); let runId = newId()
            tx.query("INSERT INTO agent_runs (id,session_id,agent_name,status,result,created_at,updated_at) VALUES (?,?,'mindtrace_tutor','completed',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(runId),Some(sessionId),Some(runResult.toString())])
            tx.query("INSERT INTO agent_tool_calls (id,agent_run_id,tool_name,input_json,output_json,created_at,updated_at) VALUES (?,?,'diagnosis_lookup',?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(runId),Some(toolInput.toString()),Some(toolOutput.toString())])
            let session = rowJson("tutor_sessions",tx.query("SELECT * FROM tutor_sessions WHERE id = ?",[Some(sessionId)]).rows[0])
            return tutorSessionPayload(tx,accounts,session,snapshot)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
