package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.base64.*
import stdx.encoding.json.*
import stdx.net.http.*

func readCropBox(data: JsonObject): Array<Float64> {
    try {
        let items = (data["box"] as JsonArray).getOrThrow().getItems()
        if (items.size != 4) { throw IllegalArgumentException("box") }
        let values = Array<Float64>(4, repeat: 0.0)
        for (index in 0..4) {
            let item = items[index]
            values[index] = Float64.parse(if (let Some(text) <- (item as JsonString)) { text.getValue() } else { item.toString() })
        }
        let x = values[0]; let y = values[1]; let w = values[2]; let h = values[3]
        if (!(x >= 0.0 && x < 1.0 && y >= 0.0 && y < 1.0 && w > 0.0 && w <= 1.0 && h > 0.0 && h <= 1.0 && x + w <= 1.000001 && y + h <= 1.000001)) { throw IllegalArgumentException("box") }
        return values
    } catch (_: Exception) { throw ApiError(422, "裁剪范围无效，请重新框选题目") }
}

func cropNumbers(values: Array<Float64>): JsonArray {
    let result = JsonArray()
    for (value in values) { result.getItems().add(JsonFloat(value)) }
    return result
}

public func cropQuestion(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context, "POST")
    let parts = context.request.url.path.split("/")
    let id = parts[parts.size - 2]
    let files = ArrayList<String>()
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        let box = readCropBox(readJson(context))
        let result = db.transaction<(JsonObject, Option<String>)>({ tx =>
            let questions = tx.query("SELECT status FROM questions WHERE id = ? AND user_id = ? FOR UPDATE", [Some(id), user["id"]]).rows
            if (questions.isEmpty() || rowText(questions[0], "status") == "archived") { throw ApiError(404, "题目不存在或已归档") }
            let active = tx.query("SELECT id,status FROM processing_jobs WHERE question_id = ? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running') ORDER BY created_at DESC,id DESC LIMIT 1", [Some(id)]).rows
            let old = tx.query("SELECT * FROM question_assets WHERE question_id = ? AND kind = 'crop' ORDER BY created_at DESC,id DESC LIMIT 1", [Some(id)]).rows
            if (!active.isEmpty()) {
                if (old.isEmpty()) { throw ApiError(409, "已有识别任务正在处理，请先查看结果再调整范围") }
                let asset = rowJson("question_assets", old[0])
                let list = JsonArray(); list.getItems().add(asset)
                let stored = assetCrop(list)
                if (!(stored is JsonArray)) { throw ApiError(409, "已有识别任务正在处理") }
                let values = (stored as JsonArray).getOrThrow().getItems()
                for (index in 0..4) {
                    let difference = Float64.parse(values[index].toString()) - box[index]
                    if (difference > 0.000001 || difference < -0.000001) { throw ApiError(409, "已有识别任务正在处理，请先查看结果再调整范围") }
                }
                asset.put("url", JsonString(accounts.mediaUrl("/" + rowText(old[0], "path"))))
                asset.put("job_id", JsonString(rowText(active[0], "id")))
                asset.put("status", JsonString(rowText(active[0], "status")))
                asset.put("resumed", JsonBool(true)); asset.put("crop_box", stored)
                return (asset, None)
            }
            let originals = tx.query("SELECT path FROM question_assets WHERE question_id = ? AND kind = 'original' ORDER BY created_at,id LIMIT 1", [Some(id)]).rows
            if (originals.isEmpty()) { throw ApiError(404, "原图不存在") }
            let input = JsonObject()
            input.put("operation", JsonString("crop")); input.put("box", cropNumbers(box))
            input.put("image_base64", JsonString(toBase64String(readMedia(rowText(originals[0], "path")))))
            let computed = algorithmCompute(input)
            if (jsonText(computed, "kind") != "crop") { throw ApiError(503, "裁剪结果无效") }
            let path = "uploads/${id}/crops/" + newId() + ".jpg"
            writeMedia(path, algorithmImage(computed)); files.add(path)
            let right = if (box[0] + box[2] > 1.0) { 1.0 } else { box[0] + box[2] }
            let bottom = if (box[1] + box[3] > 1.0) { 1.0 } else { box[1] + box[3] }
            let bbox = cropNumbers([box[0], box[1], right, bottom]).toString()
            let assetId = if (old.isEmpty()) { newId() } else { rowText(old[0], "id") }
            if (old.isEmpty()) {
                tx.query("INSERT INTO question_assets (id,question_id,kind,path,sha256,bbox,created_at,updated_at) VALUES (?,?,'crop',?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [Some(assetId), Some(id), Some(path), Some(jsonText(computed, "sha256")), Some(bbox)])
            } else {
                tx.query("UPDATE question_assets SET path = ?,sha256 = ?,bbox = ?,updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(path), Some(jsonText(computed, "sha256")), Some(bbox), Some(assetId)])
            }
            let jobId = newId()
            tx.query("INSERT INTO processing_jobs (id,question_id,kind,status,progress,created_at,updated_at) VALUES (?,?,'crop','pending',0,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [Some(jobId), Some(id)])
            tx.query("UPDATE questions SET status = 'processing',updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(id)])
            let asset = rowJson("question_assets", tx.query("SELECT * FROM question_assets WHERE id = ?", [Some(assetId)]).rows[0])
            asset.put("url", JsonString(accounts.mediaUrl("/" + path)))
            asset.put("geometry", computed["geometry"]); asset.put("original_preserved", JsonBool(true))
            asset.put("job_id", JsonString(jobId)); asset.put("status", JsonString("pending"))
            return (asset, Some(path))
        })
        files.clear()
        if (let Some(path) <- result[1]) {
            let jobId = jsonText(result[0], "job_id")
            spawn { runRecognition(jobId, id, path, requireCrop: true) }
        }
        return result[0]
    } finally { for (path in files) { try { removeMedia(path) } catch (_: Exception) {} } }
    throw ApiError(503, "数据库暂时不可用")
}
