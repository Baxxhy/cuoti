package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.json.*
import stdx.net.http.*

func diagnosisEdits(body: JsonObject): JsonObject {
    let edits = JsonObject()
    for ((key,value) in body.getFields()) {
        match (key) {
            case "first_error_step" =>
                if (value is JsonNull) { edits.put(key,value) }
                else if (value is JsonInt) {
                    let index = Int64.parse(value.toString())
                    if (index < 0 || index > 2147483647) { throw ApiError(422,"错误步骤序号无效") }
                    edits.put(key,value)
                } else { throw ApiError(422,"错误步骤序号必须为非负整数或空值") }
            case "first_error_text" | "root_misconception" | "error_location" | "recommended_strategy" => edits.put(key,editText(value,12000))
            case "error_type" =>
                let code=(editText(value,60) as JsonString).getOrThrow().getValue()
                if (!(["exact","equivalent","branch_solution","necessary_condition","missing_step","extra_step","sign_error","calculation_error","invalid_transformation","condition_omission","formula_error","formula_selection","concept_error","reasoning_gap","unknown","unit_error","model_error","direction_error","substance_error","equation_error","balance_error","condition_error","phenomenon_error","evidence_missing","context_error","theme_error","expression_error","language_error","grammar_error","vocabulary_error","reading_evidence_missing","writing_error","structure_function_error","process_error","variable_error","control_error","evidence_error","fact_error","chronology_error","causality_confusion","impact_error","location_error","map_reading_error","factor_error","spatial_relation_error","chart_error","material_mismatch","concept_confusion","rule_error","action_missing","logic_error","analysis_shallow"].contains(code))) { throw ApiError(422,"请选择支持的错误类型") }
                edits.put(key,value)
            case "confidence" =>
                let confidence = editNumber(value)
                if (!(confidence >= 0.0 && confidence <= 1.0)) { throw ApiError(422,"置信度超出范围") }
                edits.put(key,JsonFloat(confidence))
            case "missing_prerequisites" =>
                let values = manualArray(body,key,100)
                for (item in values.getItems()) { editText(item,12000) }
                edits.put(key,values)
            case _ => ()
        }
    }
    return edits
}

public func correctDiagnosis(context: HttpContext, accounts: Accounts): JsonValue {
    let parts = context.request.url.path.split("/"); let id = parts[parts.size - 2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db)
        let body = readJson(context,maxBytes: 2 * 1024 * 1024)
        let edits = diagnosisEdits(body)
        return db.transaction<JsonValue>({ tx =>
            let questions = tx.query("SELECT status FROM questions WHERE id = ? AND user_id = ? FOR UPDATE",[Some(id),user["id"]]).rows
            if (questions.isEmpty()) { throw ApiError(404,"题目不存在或无权访问") }
            if (rowText(questions[0],"status") == "archived") { throw ApiError(409,"题目已归档，不能修正诊断") }
            let diagnoses = tx.query("SELECT * FROM diagnoses WHERE question_id = ? ORDER BY created_at DESC,id DESC LIMIT 1 FOR UPDATE",[Some(id)]).rows
            if (diagnoses.isEmpty()) { throw ApiError(404,"诊断不存在") }
            if (edits.getFields().isEmpty()) { throw ApiError(422,"请提供需要修正的诊断内容") }
            if (let Some(index) <- edits.get("first_error_step")) {
                if (index is JsonInt) {
                    let steps=tx.query("SELECT s.text FROM student_steps s WHERE s.work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY s.step_index",[Some(id)]).rows
                    let number=Int64.parse(index.toString())
                    if (number>=steps.size) { throw ApiError(422,"错误步骤不在当前作答中，请重新核对") }
                    edits.put("first_error_text",JsonString(rowText(steps[number],"text")))
                } else { edits.put("first_error_text",JsonString("")) }
            }
            let current=rowJson("diagnoses",diagnoses[0])
            let effectiveType=(edits.get("error_type") ?? current["error_type"]).toString()
            if (effectiveType==JsonString("exact").toString() || effectiveType==JsonString("equivalent").toString()) {
                if (let Some(index) <- edits.get("first_error_step")) {
                    if (!(index is JsonNull)) { throw ApiError(422,"未发现错误时不能同时指定出错步骤") }
                }
                edits.put("first_error_step",JsonNull()); edits.put("first_error_text",JsonString(""))
            }
            let diagnosisId = rowText(diagnoses[0],"id")
            let sql = StringBuilder(); let params = ArrayList<Option<String>>()
            sql.append("UPDATE diagnoses SET user_confirmed = 1,correction = ?,updated_at = UTC_TIMESTAMP(6)")
            params.add(Some(body.toString()))
            for ((key,value) in edits.getFields()) { sql.append(", `${key}` = ?"); params.add(sqlValue(value)) }
            sql.append(" WHERE id = ?"); params.add(Some(diagnosisId))
            tx.query(sql.toString(),params.toArray())
            return rowJson("diagnoses",tx.query("SELECT * FROM diagnoses WHERE id = ?",[Some(diagnosisId)]).rows[0])
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

public func diagnosisRoute(context: HttpContext, accounts: Accounts): JsonValue {
    if (context.request.method == "GET") { return getDiagnosis(context,accounts) }
    if (context.request.method == "PATCH") { return correctDiagnosis(context,accounts) }
    context.responseBuilder.header("Allow","GET, PATCH")
    throw ApiError(405,"请求方法不支持")
}
