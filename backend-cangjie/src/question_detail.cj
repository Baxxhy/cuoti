package zhiwei

import std.convert.*
import stdx.encoding.json.*
import stdx.net.http.*

func queryArray(db: Database, table: String, sql: String, id: String): JsonArray {
    let result = JsonArray()
    for (row in db.query(sql, [Some(id)]).rows) { result.getItems().add(rowJson(table, row)) }
    return result
}

func firstJson(array: JsonArray): JsonValue {
    if (array.getItems().isEmpty()) { return JsonNull() }
    return array.getItems()[0]
}

func jsonText(object: JsonObject, key: String): String {
    return (object[key] as JsonString).getOrThrow().getValue()
}

func assetCrop(assets: JsonArray): JsonValue {
    for (item in assets.getItems()) {
        let asset = (item as JsonObject).getOrThrow()
        if (jsonText(asset, "kind") != "crop") { continue }
        try {
            let bbox = (asset["bbox"] as JsonArray).getOrThrow().getItems()
            if (bbox.size != 4) { return JsonNull() }
            let x = Float64.parse(bbox[0].toString())
            let y = Float64.parse(bbox[1].toString())
            let right = Float64.parse(bbox[2].toString())
            let bottom = Float64.parse(bbox[3].toString())
            if (!(x >= 0.0 && y >= 0.0 && right > x && bottom > y && right <= 1.0 && bottom <= 1.0)) { return JsonNull() }
            let result = JsonArray()
            for (value in [x, y, right - x, bottom - y]) { result.getItems().add(JsonFloat(value)) }
            return result
        } catch (_: Exception) { return JsonNull() }
    }
    return JsonNull()
}

public func questionDetail(context: HttpContext, accounts: Accounts, id: String): JsonValue {
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        // All dependent rows belong to one database snapshot.
        return db.transaction<JsonValue>({ tx =>
            let rows = tx.query("SELECT * FROM questions WHERE id = ? AND user_id = ?", [Some(id), user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404, "内容不存在或无权访问") }
            let result = rowJson("questions", rows[0])
            let assets = queryArray(tx, "question_assets", "SELECT * FROM question_assets WHERE question_id = ?", id)
            let figures = JsonArray()
            let working = JsonArray()
            let annotations = JsonArray()
            for (item in assets.getItems()) {
                let asset = (item as JsonObject).getOrThrow()
                asset.put("url", JsonString(accounts.mediaUrl("/" + jsonText(asset, "path"))))
                match (jsonText(asset, "kind")) {
                    case "question_figure" => figures.getItems().add(asset)
                    case "student_working_figure" => working.getItems().add(asset)
                    case "teacher_annotation_region" => annotations.getItems().add(asset)
                    case _ => ()
                }
            }
            result.put("assets", assets)
            result.put("question_figures", figures)
            result.put("student_working_figures", working)
            result.put("teacher_annotation_regions", annotations)
            result.put("crop_box", assetCrop(assets))
            let ocr = queryArray(tx, "ocr_runs", "SELECT * FROM ocr_runs WHERE question_id = ? ORDER BY created_at DESC", id)
            var selected = firstJson(ocr)
            for (item in ocr.getItems()) {
                if (jsonText((item as JsonObject).getOrThrow(), "stream") == "qwen_crop") { selected = item; break }
            }
            result.put("ocr", selected)
            result.put("ocr_runs", ocr)
            let analyses = queryArray(tx, "problem_analyses", "SELECT * FROM problem_analyses WHERE question_id = ? LIMIT 1", id)
            let analysis = firstJson(analyses)
            result.put("analysis", analysis)
            result.put("reference_steps", if (let Some(object) <- (analysis as JsonObject)) {
                queryArray(tx, "reference_steps", "SELECT * FROM reference_steps WHERE analysis_id = ? ORDER BY step_index", jsonText(object, "id"))
            } else { JsonArray() })
            let diagnoses = queryArray(tx, "diagnoses", "SELECT * FROM diagnoses WHERE question_id = ? ORDER BY created_at DESC,id DESC LIMIT 1", id)
            let diagnosis = firstJson(diagnoses)
            if (let Some(object) <- (diagnosis as JsonObject)) {
                let evidence = queryArray(tx, "diagnosis_evidence", "SELECT * FROM diagnosis_evidence WHERE diagnosis_id = ? ORDER BY COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(metadata_json,'$.index')) AS UNSIGNED),10000),created_at,id", jsonText(object, "id"))
                let steps = JsonArray()
                var counterfactual: JsonValue = JsonNull()
                var found = false
                for (item in evidence.getItems()) {
                    let entry = (item as JsonObject).getOrThrow()
                    let kind = jsonText(entry, "kind")
                    if (kind == "step_alignment") { steps.getItems().add(entry) }
                    if (kind == "counterfactual_validation" && !found) { counterfactual = entry["metadata_json"]; found = true }
                }
                object.put("evidence", steps)
                object.put("counterfactual", safeCounterfactual(counterfactual,diagnosis:Some(object)))
            }
            result.put("diagnosis", diagnosis)
            result.put("student_steps", queryArray(tx, "student_steps", "SELECT s.* FROM student_steps s WHERE s.work_id = (SELECT id FROM student_works WHERE question_id = ? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY s.step_index", id))
            result.put("teacher_marks", queryArray(tx, "teacher_marks", "SELECT * FROM teacher_marks WHERE question_id = ?", id))
            result.put("processing_job", firstJson(queryArray(tx, "processing_jobs", "SELECT * FROM processing_jobs WHERE question_id = ? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running') ORDER BY created_at DESC LIMIT 1", id)))
            return result
        })
    }
    throw ApiError(503, "数据库暂时不可用")
}
