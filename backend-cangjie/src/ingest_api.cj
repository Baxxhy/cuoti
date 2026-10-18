package zhiwei

import stdx.encoding.base64.*
import stdx.encoding.json.*
import stdx.encoding.url.*
import stdx.net.http.*

// The validated upload is retained independently of the normalized JPEG used
// by existing crop/recognition workflows. Never derive this suffix from a name.
func uploadedImageSuffix(bytes: Array<UInt8>): String {
    if (bytesMatch(bytes,[0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a],0)) { return "png" }
    if (bytesMatch(bytes,[0xff,0xd8,0xff],0)) { return "jpg" }
    if (bytesMatch(bytes,"RIFF".toArray(),0) && bytesMatch(bytes,"WEBP".toArray(),8)) { return "webp" }
    if (bytesMatch(bytes,"GIF87a".toArray(),0) || bytesMatch(bytes,"GIF89a".toArray(),0)) { return "gif" }
    if (bytesMatch(bytes,"BM".toArray(),0)) { return "bmp" }
    if (bytesMatch(bytes,[0x49,0x49,0x2a,0],0) || bytesMatch(bytes,[0x4d,0x4d,0,0x2a],0)) { return "tif" }
    return "bin"
}

public func ingestQuestion(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context, "POST")
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        let upload = readImageUpload(context)
        let form = Form(context.request.url.rawQuery ?? "")
        let subject = queryLast(form, "subject")
        let actualSubject = if (subject.isEmpty()) { "数学" } else { subject }
        if (runeCount(actualSubject) > 30) { throw ApiError(422, "学科名称过长") }
        let input = JsonObject()
        input.put("operation", JsonString("normalize"))
        input.put("image_base64", JsonString(toBase64String(upload.bytes)))
        let normalized = algorithmCompute(input)
        if (jsonText(normalized, "kind") != "original") { throw ApiError(503, "原图结果无效") }
        let bytes = algorithmImage(normalized)
        let id = newId()
        let jobId = newId()
        let path = "uploads/${id}/original.jpg"
        let uploadedPath = "uploads/${id}/uploaded." + uploadedImageSuffix(upload.bytes)
        let uploadedHash = sha256(upload.bytes)
        try {
            writeMedia(path, bytes)
            writeMedia(uploadedPath, upload.bytes)
            db.transaction<Unit>({ tx =>
                tx.query("INSERT INTO questions (id,user_id,subject,title,question_text,status,confirmed,favorite,tags,formulas,options,question_type,knowledge_points,created_at,updated_at) VALUES (?,?,?,?,'',?,0,0,JSON_ARRAY(),JSON_ARRAY(),JSON_ARRAY(),'综合题',JSON_ARRAY(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                    [Some(id), user["id"], Some(actualSubject), Some(upload.filename), Some(if (upload.deferred) { "awaiting_crop" } else { "processing" })])
                tx.query("INSERT INTO question_assets (id,question_id,kind,path,sha256,bbox,created_at,updated_at) VALUES (?,?,'original',?,?,JSON_ARRAY(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                    [Some(newId()), Some(id), Some(path), Some(jsonText(normalized, "sha256"))])
                tx.query("INSERT INTO question_assets (id,question_id,kind,path,sha256,bbox,created_at,updated_at) VALUES (?,?,'uploaded_original',?,?,JSON_ARRAY(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                    [Some(newId()), Some(id), Some(uploadedPath), Some(uploadedHash)])
                if (!upload.deferred) {
                    tx.query("INSERT INTO processing_jobs (id,question_id,kind,status,progress,created_at,updated_at) VALUES (?,?,'ingest','pending',0,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [Some(jobId), Some(id)])
                }
                ()
            })
        } catch (error: Exception) {
            try { removeMedia(path) } catch (_: Exception) {}
            try { removeMedia(uploadedPath) } catch (_: Exception) {}
            throw error
        }
        if (!upload.deferred) { spawn { runRecognition(jobId, id, path) } }
        let result = JsonObject()
        result.put("question_id", JsonString(id))
        result.put("job_id", if (upload.deferred) { JsonNull() } else { JsonString(jobId) })
        result.put("status", JsonString(if (upload.deferred) { "awaiting_crop" } else { "pending" }))
        return result
    }
    throw ApiError(503, "数据库暂时不可用")
}
