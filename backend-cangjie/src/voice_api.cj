package zhiwei

import stdx.encoding.base64.*
import stdx.encoding.json.*
import stdx.encoding.url.*
import stdx.net.http.*

func validateVoiceContext(db: Database, owner: String, questionId: String, workId: String): Unit {
    if (!questionId.isEmpty()) { paperQuestion(db,questionId,owner) }
    if (!workId.isEmpty()) {
        let rows=db.query("SELECT * FROM student_works WHERE id=? AND user_id=?",[Some(workId),Some(owner)]).rows
        if (rows.isEmpty()) { throw ApiError(404,"作答记录不存在或无权访问") }
        if (!questionId.isEmpty() && rowText(rows[0],"question_id")!=questionId) { throw ApiError(422,"作答记录与题目不匹配") }
    }
}

func insertVoice(db: Database, owner: String, questionId: String, workId: String, kind: String, path: String, text: String, metadata: JsonObject, failed!: Bool=false): JsonObject {
    let id=newId(); let duration=paperInteger(metadata.get("duration_ms") ?? JsonInt(0),0,2147483647)
    db.query("INSERT INTO voice_records (id,user_id,question_id,work_id,kind,audio_path,transcript,model_name,status,duration_ms,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(id),Some(owner),if (questionId.isEmpty()) { None } else { Some(questionId) },if (workId.isEmpty()) { None } else { Some(workId) },Some(kind),Some(path),Some(text),Some(tutorText(metadata,"model")),Some(if (failed) { "failed" } else { "completed" }),Some(duration.toString())])
    return rowJson("voice_records",db.query("SELECT * FROM voice_records WHERE id=?",[Some(id)]).rows[0])
}

func transcribeVoice(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let owner=rowText(user,"id"); let form=Form(context.request.url.rawQuery ?? "")
        let questionId=queryLast(form,"question_id"); let workId=queryLast(form,"work_id"); validateVoiceContext(db,owner,questionId,workId)
        let upload=readImageUpload(context,audio:true); let parts=upload.filename.split("."); var suffix=".webm"
        if (parts.size>1) { let candidate="."+parts[parts.size-1].toAsciiLower(); for (allowed in [".webm",".wav",".mp3",".m4a",".ogg",".mp4"]) { if (candidate==allowed) { suffix=candidate } } }
        let path="uploads/voice/${owner}/${newId()}${suffix}"; writeMedia(path,upload.bytes)
        let input=JsonObject(); input.put("operation",JsonString("voice_transcribe")); input.put("audio_base64",JsonString(toBase64String(upload.bytes))); input.put("audio_suffix",JsonString(suffix))
        var computed=JsonObject()
        try { computed=algorithmCompute(input) }
        catch (_: Exception) {
            let metadata=JsonObject(); metadata.put("model",JsonString("faster-whisper-small")); insertVoice(db,owner,questionId,workId,"stt",path,"",metadata,failed:true)
            throw ApiError(502,"语音转写失败，请稍后重试或使用文字输入")
        }
        let metadata=tutorObject(computed,"metadata"); let text=jsonText(computed,"text")
        let record=db.transaction<JsonObject>({ tx =>
            let saved=insertVoice(tx,owner,questionId,workId,"stt",path,text,metadata)
            if (!workId.isEmpty()) { tx.query("UPDATE student_works SET explanation=?,updated_at=UTC_TIMESTAMP(6) WHERE id=? AND user_id=?",[Some(text),Some(workId),Some(owner)]) }
            return saved
        })
        record.put("text",JsonString(text)); record.put("bytes",JsonInt(upload.bytes.size)); record.put("editable",JsonBool(true)); record.put("metadata",metadata); record.put("audio_url",JsonString(accounts.mediaUrl("/"+path))); return record
    }
    throw ApiError(503,"数据库暂时不可用")
}

func synthesizeVoice(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let owner=rowText(user,"id"); let body=readJson(context)
        let text=stripWhitespace(schoolText(body,"text","",12000))
        if (text.isEmpty()) { throw ApiError(400,"朗读文本不能为空") }
        let questionId=if ((body.get("question_id") ?? JsonNull()) is JsonNull) { "" } else { schoolText(body,"question_id","",36) }; validateVoiceContext(db,owner,questionId,"")
        let input=JsonObject(); input.put("operation",JsonString("voice_synthesize")); input.put("text",JsonString(text)); input.put("voice",JsonString(schoolText(body,"voice","zh-CN-XiaoxiaoNeural",100)))
        let computed=algorithmCompute(input); let data=fromBase64String(jsonText(computed,"audio_base64")).getOrThrow()
        if (data.isEmpty() || data.size>64*1024*1024 || sha256(data)!=jsonText(computed,"sha256")) { throw ApiError(502,"语音合成结果无效") }
        let metadata=tutorObject(computed,"metadata"); let path="uploads/voice/${owner}/tts-${newId()}.mp3"; writeMedia(path,data)
        try {
            let record=insertVoice(db,owner,questionId,"","tts",path,text,metadata)
            record.put("text",JsonString(text)); record.put("browser_fallback",JsonBool(false)); record.put("metadata",metadata); record.put("audio_url",JsonString(accounts.mediaUrl("/"+path))); return record
        } catch (error: Exception) { try { removeMedia(path) } catch (_: Exception) {}; throw error }
    }
    throw ApiError(503,"数据库暂时不可用")
}
