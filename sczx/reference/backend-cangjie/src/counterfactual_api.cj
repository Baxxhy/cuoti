package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

// Older cache entries labelled a reference-text match as a SymPy proof.
// Keep the stored history, but never expose that legacy claim as verified.
func safeCounterfactual(value: JsonValue, diagnosis!: Option<JsonObject> = None): JsonValue {
    if (let Some(result) <- (value as JsonObject)) {
        let method=tutorText(result,"verification_method")
        if ((method=="qwen_proposal_sympy_check" || method=="reference_repair_sympy_check") && tutorText(result,"validation_scope").isEmpty() && !result.get("preserved_prefix").isSome()) {
            result.put("verification_method",JsonString("legacy_reference_alignment"))
            result.put("legacy_review_required",JsonBool(true))
            if (tutorFlag(result,"root_cause_confirmed")) {
                result.put("root_cause_confirmed",JsonBool(false)); result.put("status",JsonString("partial"))
                result.put("confidence",JsonFloat(0.5))
                result.put("conclusion",JsonString("这是历史参考过程的修复建议，尚未经过当前规则核验，请结合原题核对。"))
            }
        }
        if (let Some(current) <- diagnosis) {
            if (tutorFlag(current,"user_confirmed") && tutorText(result,"status")!="not_needed" &&
                (!result.get("suspected_step").isSome() || !jsonEquivalent(result.get("suspected_step") ?? JsonNull(),current.get("first_error_step") ?? JsonNull()))) {
                result.put("root_cause_confirmed",JsonBool(false)); result.put("status",JsonString("partial"))
                result.put("stale_after_correction",JsonBool(true)); result.put("confidence",JsonFloat(0.5))
                result.put("verification_method",JsonString("previous_diagnosis_evidence"))
                result.put("conclusion",JsonString("你已调整出错步骤，原有修复建议需要重新核对。"))
            }
        }
    }
    return value
}

func cachedCounterfactual(db: Database, diagnosisId: String): Option<JsonValue> {
    let rows = db.query("SELECT * FROM diagnosis_evidence WHERE diagnosis_id = ? AND kind = 'counterfactual_validation' ORDER BY created_at,id LIMIT 1",[Some(diagnosisId)]).rows
    if (rows.isEmpty()) { return None }
    let diagnoses=db.query("SELECT * FROM diagnoses WHERE id=?",[Some(diagnosisId)]).rows
    let current: Option<JsonObject> = if (diagnoses.isEmpty()) { None } else { Some(rowJson("diagnoses",diagnoses[0])) }
    return Some(safeCounterfactual(rowJson("diagnosis_evidence",rows[0])["metadata_json"],diagnosis:current))
}

public func counterfactualQuestion(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    let parts = context.request.url.path.split("/"); let id = parts[parts.size - 3]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db)
        let initial = db.transaction<(JsonObject,Option<JsonValue>)>({ tx =>
            let snapshot = diagnosisSnapshot(tx,id,user["id"])
            if (snapshot["analysis"] is JsonNull || snapshot["diagnosis"] is JsonNull) { throw ApiError(404,"题目诊断不存在") }
            let diagnosis = (snapshot["diagnosis"] as JsonObject).getOrThrow()
            return (snapshot,cachedCounterfactual(tx,jsonText(diagnosis,"id")))
        })
        if (let Some(cached) <- initial[1]) { return cached }
        let snapshot = initial[0]
        let input = diagnosisInput(snapshot,includeImages: false)
        input.put("operation",JsonString("counterfactual"))
        let computed = algorithmCompute(input)
        return db.transaction<JsonValue>({ tx =>
            let current = diagnosisSnapshot(tx,id,user["id"])
            if (!jsonEquivalent(diagnosisFingerprint(current),diagnosisFingerprint(snapshot))) { throw ApiError(409,"题目或诊断已变化，请重新验证") }
            let diagnosis = (current["diagnosis"] as JsonObject).getOrThrow()
            let diagnosisId = jsonText(diagnosis,"id")
            if (let Some(cached) <- cachedCounterfactual(tx,diagnosisId)) { return cached }
            saveDiagnosticEvidence(tx,diagnosisId,current,computed,includeAlignment: false)
            syncKnowledgeLinks(tx,(current["question"] as JsonObject).getOrThrow(),(current["analysis"] as JsonObject).getOrThrow(),diagnosis: Some(diagnosis))
            return safeCounterfactual(computed["counterfactual"],diagnosis:Some(diagnosis))
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
