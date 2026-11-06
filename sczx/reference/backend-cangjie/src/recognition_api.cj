package zhiwei

import stdx.net.http.*
import stdx.encoding.json.*

public func startRecognition(context: HttpContext, accounts: Accounts, synchronous: Bool): JsonValue {
    requireMethod(context, "POST")
    let parts = context.request.url.path.split("/")
    let id = parts[parts.size - 2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        let started = db.transaction<(JsonObject, Option<String>)>({ tx =>
            let rows = tx.query("SELECT status FROM questions WHERE id = ? AND user_id = ? FOR UPDATE", [Some(id), user["id"]]).rows
            if (rows.isEmpty() || rowText(rows[0], "status") == "archived") { throw ApiError(404, "题目不存在或已归档") }
            let active = tx.query("SELECT * FROM processing_jobs WHERE question_id = ? AND status IN ('pending','running') AND kind IN ('ingest','crop','ocr','reprocess') ORDER BY created_at DESC,id DESC LIMIT 1", [Some(id)]).rows
            if (!active.isEmpty()) { return (rowJson("processing_jobs", active[0]), None) }
            let assets = tx.query("SELECT path FROM question_assets WHERE question_id = ? AND kind = 'crop' ORDER BY created_at DESC,id DESC LIMIT 1", [Some(id)]).rows
            if (assets.isEmpty()) { throw ApiError(422, "请先框选题目，生成裁剪图片后再识别") }
            let jobId = newId()
            tx.query("INSERT INTO processing_jobs (id,question_id,kind,status,progress,created_at,updated_at) VALUES (?,?,?,'pending',0,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [Some(jobId), Some(id), Some(if (synchronous) { "ocr" } else { "reprocess" })])
            tx.query("UPDATE questions SET status = 'processing',updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(id)])
            return (rowJson("processing_jobs", tx.query("SELECT * FROM processing_jobs WHERE id = ?", [Some(jobId)]).rows[0]), Some(rowText(assets[0], "path")))
        })
        let jobId = jsonText(started[0], "id")
        if (let Some(path) <- started[1]) {
            if (synchronous) { runRecognition(jobId, id, path, requireCrop: true) }
            else { spawn { runRecognition(jobId, id, path, requireCrop: true) } }
        }
        let result = JsonObject()
        if (synchronous) {
            result.put("job", rowJson("processing_jobs", db.query("SELECT * FROM processing_jobs WHERE id = ?", [Some(jobId)]).rows[0]))
            result.put("question", questionDetail(context, accounts, id))
        } else { result.put("job_id", JsonString(jobId)) }
        if (started[1].isNone()) { result.put("resumed", JsonBool(true)) }
        return result
    }
    throw ApiError(503, "数据库暂时不可用")
}
