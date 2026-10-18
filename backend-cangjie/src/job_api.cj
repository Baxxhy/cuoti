package zhiwei

import stdx.net.http.*
import stdx.encoding.json.*

public func getJob(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context, "GET")
    let parts = context.request.url.path.split("/")
    let id = parts[parts.size - 1]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        let rows = db.query("SELECT j.* FROM processing_jobs j JOIN questions q ON q.id = j.question_id WHERE j.id = ? AND q.user_id = ?", [Some(id), user["id"]]).rows
        if (rows.isEmpty()) { throw ApiError(404, "任务不存在或无权访问") }
        return rowJson("processing_jobs", rows[0])
    }
    throw ApiError(503, "数据库暂时不可用")
}

public func retryJob(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context, "POST")
    let parts = context.request.url.path.split("/")
    let id = parts[parts.size - 2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        let owned = db.query("SELECT j.question_id FROM processing_jobs j JOIN questions q ON q.id = j.question_id WHERE j.id = ? AND q.user_id = ?", [Some(id), user["id"]]).rows
        if (owned.isEmpty()) { throw ApiError(404, "任务不存在或无权访问") }
        let questionId = rowText(owned[0], "question_id")
        let result = db.transaction<(JsonObject, Option<String>, Bool)>({ tx =>
            let questions = tx.query("SELECT status FROM questions WHERE id = ? AND user_id = ? FOR UPDATE", [Some(questionId), user["id"]]).rows
            if (questions.isEmpty() || rowText(questions[0], "status") == "archived") { throw ApiError(404, "题目不存在或已归档") }
            let jobs = tx.query("SELECT * FROM processing_jobs WHERE id = ? AND question_id = ? FOR UPDATE", [Some(id), Some(questionId)]).rows
            if (jobs.isEmpty()) { throw ApiError(404, "任务不存在") }
            let job = jobs[0]
            if (rowText(job, "status") != "failed") { throw ApiError(409, "任务仍在处理或已完成，请刷新后查看结果") }
            let kind = rowText(job, "kind")
            if (kind != "ingest" && kind != "crop" && kind != "ocr" && kind != "reprocess") { throw ApiError(409, "该任务不支持识别重试") }
            let active = tx.query("SELECT * FROM processing_jobs WHERE question_id = ? AND status IN ('pending','running') AND kind IN ('ingest','crop','ocr','reprocess') ORDER BY created_at DESC,id DESC LIMIT 1", [Some(questionId)]).rows
            if (!active.isEmpty()) {
                let response = rowJson("processing_jobs", active[0])
                response.put("resumed", JsonBool(true))
                return (response, None, false)
            }
            let assets = tx.query("SELECT path,kind FROM question_assets WHERE question_id = ? AND (kind = 'crop' OR (kind = 'original' AND ? = 'ingest')) ORDER BY (kind = 'crop') DESC,created_at DESC,id DESC LIMIT 1", [Some(questionId), Some(kind)]).rows
            if (assets.isEmpty()) { throw ApiError(422, "缺少识别图片，请重新框选题目") }
            tx.query("UPDATE processing_jobs SET status = 'pending',progress = 0,error = NULL,updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(id)])
            tx.query("UPDATE questions SET status = 'processing',updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(questionId)])
            let updated = tx.query("SELECT * FROM processing_jobs WHERE id = ?", [Some(id)]).rows[0]
            return (rowJson("processing_jobs", updated), Some(rowText(assets[0], "path")), rowText(assets[0], "kind") == "crop")
        })
        if (let Some(path) <- result[1]) {
            let crop = result[2]
            spawn { runRecognition(id, questionId, path, requireCrop: crop) }
        }
        return result[0]
    }
    throw ApiError(503, "数据库暂时不可用")
}
