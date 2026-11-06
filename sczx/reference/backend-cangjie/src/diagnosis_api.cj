package zhiwei

import std.collection.*
import stdx.encoding.base64.*
import stdx.encoding.json.*
import stdx.net.http.*

func diagnosisSnapshot(db: Database, id: String, owner: Option<String>): JsonObject {
    let result = analysisSnapshot(db,id,owner)
    result.put("references",queryArray(db,"reference_steps","SELECT r.* FROM reference_steps r JOIN problem_analyses a ON r.analysis_id = a.id WHERE a.question_id = ? ORDER BY r.step_index,r.id",id))
    result.put("diagnosis",firstJson(queryArray(db,"diagnoses","SELECT * FROM diagnoses WHERE question_id = ? ORDER BY created_at DESC,id DESC LIMIT 1",id)))
    let question=tutorObject(result,"question")
    result.put("diagnostic_cards",dialogueKnowledge(db,tutorText(question,"question_text"),tutorText(question,"subject"),tutorText(question,"grade")))
    return result
}

func diagnosisFingerprint(snapshot: JsonObject): JsonArray {
    let value = analysisFingerprint(snapshot)
    value.getItems().add(snapshot["references"]); value.getItems().add(snapshot["diagnosis"])
    // Learning-task snapshots predate retrieval cards. Preserve their original
    // fingerprint representation so an upgrade does not invalidate saved work.
    if (let Some(cards) <- snapshot.get("diagnostic_cards")) { value.getItems().add(cards) }
    return value
}

func diagnosisInput(snapshot: JsonObject, includeImages!: Bool = true): JsonObject {
    let question = (snapshot["question"] as JsonObject).getOrThrow()
    let input = JsonObject(); input.put("operation",JsonString("diagnose")); input.put("text",question["question_text"])
    input.put("diagnostic_cards",snapshot.get("diagnostic_cards") ?? JsonArray()); input.put("grade",JsonString(tutorText(question,"grade")))
    for (key in ["subject","question_type","student_answer","options"]) { input.put(key,question[key]) }
    for ((source,target) in [("references","reference_steps"),("steps","student_records")]) {
        let values = JsonArray()
        for (item in (snapshot[source] as JsonArray).getOrThrow().getItems()) {
            let row = (item as JsonObject).getOrThrow(); let record = JsonObject()
            record.put("id",row["id"]); record.put("text",row["text"]); values.getItems().add(record)
        }
        input.put(target,values)
    }
    let images = JsonArray(); let seen = HashSet<String>()
    if (includeImages) {
    for (item in (snapshot["assets"] as JsonArray).getOrThrow().getItems()) {
        let path = jsonText((item as JsonObject).getOrThrow(),"path")
        if (!seen.contains(path)) { images.getItems().add(JsonString(toBase64String(readMedia(path)))); seen.add(path) }
    }
    }
    input.put("images_base64",images)
    return input
}

func sqlValue(value: JsonValue): Option<String> {
    if (value is JsonNull) { return None }
    if (let Some(text) <- (value as JsonString)) { return Some(text.getValue()) }
    if (let Some(flag) <- (value as JsonBool)) { return Some(if (flag.getValue()) { "1" } else { "0" }) }
    return Some(value.toString())
}

func insertDiagnosisEvidence(db: Database, diagnosisId: String, kind: String, content: String, entry: JsonObject, metadata: JsonObject): Unit {
    let values = ArrayList<Option<String>>([Some(newId()),Some(diagnosisId),Some(kind),Some(content)])
    for (key in ["reference_step_id","student_step_id","alignment","equivalent","uses_condition","is_first_error","propagated","math_valid"]) { values.add(sqlValue(entry[key])) }
    values.add(Some(metadata.toString()))
    db.query("INSERT INTO diagnosis_evidence (id,diagnosis_id,kind,content,reference_step_id,student_step_id,alignment,equivalent,uses_condition,is_first_error,propagated,math_valid,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",values.toArray())
}

func saveDiagnosticEvidence(db: Database, diagnosisId: String, snapshot: JsonObject, computed: JsonObject, includeAlignment!: Bool = true): Unit {
    let refs = HashSet<String>(); let steps = HashSet<String>()
    for (item in (snapshot["references"] as JsonArray).getOrThrow().getItems()) { refs.add(jsonText((item as JsonObject).getOrThrow(),"id")) }
    for (item in (snapshot["steps"] as JsonArray).getOrThrow().getItems()) { steps.add(jsonText((item as JsonObject).getOrThrow(),"id")) }
    let alignment = (computed["alignment"] as JsonArray).getOrThrow()
    let counter = (computed["counterfactual"] as JsonObject).getOrThrow()
    let suspected = counter.get("suspected_step") ?? JsonNull()
    var first: Option<JsonObject> = None
    for (item in alignment.getItems()) {
        let entry = (item as JsonObject).getOrThrow()
        for ((key,allowed) in [("reference_step_id",refs),("student_step_id",steps)]) {
            if (let Some(text) <- (entry[key] as JsonString)) { if (!allowed.contains(text.getValue())) { throw ApiError(503,"诊断证据不属于当前作答") } }
        }
        if (includeAlignment) { insertDiagnosisEvidence(db,diagnosisId,"step_alignment",jsonText(entry,"reference_text") + " ⇄ " + jsonText(entry,"student_text"),entry,entry) }
        if (!(suspected is JsonNull) && jsonEquivalent(entry["index"],suspected)) { first = Some(entry) }
    }
    let record = JsonObject()
    record.put("reference_step_id",if (let Some(entry) <- first) { entry["reference_step_id"] } else { JsonNull() })
    record.put("student_step_id",if (let Some(entry) <- first) { entry["student_step_id"] } else { JsonNull() })
    record.put("alignment",counter["status"]); record.put("equivalent",counter["root_cause_confirmed"])
    record.put("uses_condition",JsonBool(!(record["reference_step_id"] is JsonNull)))
    record.put("is_first_error",JsonBool(!(suspected is JsonNull)))
    record.put("propagated",JsonBool(editNumber(counter.get("recovered_steps") ?? JsonInt(0)) > 0.0))
    record.put("math_valid",counter["root_cause_confirmed"])
    insertDiagnosisEvidence(db,diagnosisId,"counterfactual_validation",jsonText(counter,"conclusion"),record,counter)
    let assessment=tutorObject(computed,"evidence_diagnosis")
    if (!tutorText(assessment,"algorithm").isEmpty()) {
        let source=JsonObject()
        for (key in ["reference_step_id","student_step_id"]) { source.put(key,JsonNull()) }
        source.put("alignment",JsonString("evidence_assessment"))
        for (key in ["equivalent","uses_condition","is_first_error","propagated","math_valid"]) { source.put(key,JsonBool(false)) }
        source.put("math_valid",JsonBool(tutorFlag(assessment,"verified")))
        insertDiagnosisEvidence(db,diagnosisId,"eced_assessment",tutorText(assessment,"reason"),source,assessment)
    }
}

public func diagnoseQuestion(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    let parts = context.request.url.path.split("/"); let id = parts[parts.size - 2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db)
        let initial = db.transaction<JsonObject>({ tx => diagnosisSnapshot(tx,id,user["id"]) })
        if (initial["analysis"] is JsonNull) { analyzeQuestion(context,accounts) }
        let snapshot = db.transaction<JsonObject>({ tx => diagnosisSnapshot(tx,id,user["id"]) })
        if (snapshot["analysis"] is JsonNull) { throw ApiError(409,"题目分析已变化，请重新诊断") }
        let computed = algorithmCompute(diagnosisInput(snapshot))
        let diagnosis = (computed["diagnosis"] as JsonObject).getOrThrow()
        return db.transaction<JsonValue>({ tx =>
            let current = diagnosisSnapshot(tx,id,user["id"])
            if (!jsonEquivalent(diagnosisFingerprint(snapshot),diagnosisFingerprint(current))) { throw ApiError(409,"题目、作答或分析已变化，请重新诊断") }
            let diagnosisId = newId()
            let values = ArrayList<Option<String>>([Some(diagnosisId),Some(id)])
            for (key in ["first_error_step","first_error_text","error_type","root_misconception","propagated_errors","strategy_candidates","confidence","error_location","missing_prerequisites","recommended_strategy"]) { values.add(sqlValue(diagnosis[key])) }
            tx.query("INSERT INTO diagnoses (id,question_id,first_error_step,first_error_text,error_type,root_misconception,propagated_errors,strategy_candidates,confidence,error_location,missing_prerequisites,recommended_strategy,user_confirmed,correction,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,JSON_OBJECT(),UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",values.toArray())
            saveDiagnosticEvidence(tx,diagnosisId,snapshot,computed)
            syncKnowledgeLinks(tx,(snapshot["question"] as JsonObject).getOrThrow(),(snapshot["analysis"] as JsonObject).getOrThrow(),diagnosis: Some(diagnosis))
            tx.query("UPDATE questions SET status = 'diagnosed',updated_at = UTC_TIMESTAMP() WHERE id = ?",[Some(id)])
            let result = rowJson("diagnoses",tx.query("SELECT * FROM diagnoses WHERE id = ?",[Some(diagnosisId)]).rows[0])
            result.put("evidence",computed["alignment"]); result.put("counterfactual",computed["counterfactual"])
            result.put("evidence_diagnosis",computed.get("evidence_diagnosis") ?? JsonNull())
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

public func getDiagnosis(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let parts = context.request.url.path.split("/"); let id = parts[parts.size - 2]
    let detail = (questionDetail(context,accounts,id) as JsonObject).getOrThrow()
    return detail["diagnosis"]
}
