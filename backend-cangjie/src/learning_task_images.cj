package zhiwei

import std.convert.*
import stdx.encoding.base64.*
import stdx.encoding.json.*
import stdx.net.http.*

func taskImage(db: Database, task: JsonObject, id: String): JsonObject {
    let rows=db.query("SELECT * FROM learning_task_images WHERE id=? AND task_id=? AND input_fingerprint=?",[Some(id),sqlValue(task["id"]),sqlValue(task["input_fingerprint"])]).rows
    if (rows.isEmpty()) { throw ApiError(422,"这张作答照片不属于当前任务版本") }
    return rowJson("learning_task_images",rows[0])
}

func attachTaskImage(db: Database, task: JsonObject, body: JsonObject, event: JsonObject): Unit {
    let id=schoolText(body,"handwriting_id","",36)
    if (id.isEmpty()) {
        if (body.get("handwriting_confirmed").isSome()) { throw ApiError(422,"核对标记缺少对应照片") }
        return
    }
    if (tutorText(event,"kind")!="answer") { throw ApiError(422,"照片只能关联本人确认后的作答") }
    let flag=body.get("handwriting_confirmed") ?? JsonNull()
    if (!(flag is JsonBool) || !tutorFlag(body,"handwriting_confirmed")) { throw ApiError(422,"请先核对照片识别文字，再确认提交") }
    let image=taskImage(db,task,id)
    if (tutorText(image,"confirmation_step_id")!=jsonText(task,"step_id") || !(image["recognition"] is JsonObject)) { throw ApiError(409,"照片对应的步骤已更新，请重新核对当前作答") }
    event.put("handwriting_id",JsonString(id)); event.put("handwriting_confirmed",JsonBool(true)); event.put("handwriting_recognition",image["recognition"])
}

func taskImageComputeAction(task: JsonObject): JsonObject {
    let event=(JsonValue.fromStr(task["pending_action"].toString()) as JsonObject).getOrThrow()
    if (tutorText(event,"kind")!="recognize_handwriting") { return event }
    try (db=Database.fromEnvironment()) {
        let image=taskImage(db,task,jsonText(event,"handwriting_id")); let raw=readMedia(jsonText(image,"original_path"))
        if (sha256(raw)!=jsonText(image,"sha256")) { throw ApiError(503,"作答原图校验失败，请重新上传") }
        event.put("image_base64",JsonString(toBase64String(raw))); return event
    }
    throw ApiError(503,"作答照片暂时不可用")
}

func saveTaskImageResult(db: Database, task: JsonObject, view: JsonObject, nextStep: String): Unit {
    let event=tutorObject(task,"pending_action")
    if (tutorText(event,"kind")!="recognize_handwriting") { return }
    let draft=tutorObject(view,"handwriting"); let image=taskImage(db,task,jsonText(event,"handwriting_id"))
    if (jsonText(draft,"id")!=jsonText(image,"id") || !((draft.get("recognition") ?? JsonNull()) is JsonObject)) { throw ApiError(503,"手写转写结果格式不正确") }
    db.query("UPDATE learning_task_images SET recognition=?,confirmation_step_id=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(draft["recognition"].toString()),Some(nextStep),sqlValue(image["id"])])
    draft.put("image_url",JsonString("/"+jsonText(image,"original_path")))
    view.put("handwriting",draft)
}

func retainTaskImageForSupport(db: Database, task: JsonObject, result: JsonObject, view: JsonObject, nextStep: String): Unit {
    let kind=tutorText(tutorObject(task,"pending_action"),"kind")
    if (!["visualize","observe_visualization","close_visualization","hint","reveal","resume"].contains(kind) || tutorText(tutorObject(task,"checkpoint"),"phase")!=tutorText(tutorObject(result,"checkpoint"),"phase") || tutorText(view,"input_kind")!="text") { return }
    let draft=tutorObject(tutorObject(task,"student_view"),"handwriting")
    if (draft.getFields().isEmpty() || !tutorObject(view,"handwriting").getFields().isEmpty()) { return }
    let image=taskImage(db,task,jsonText(draft,"id"))
    if (tutorText(image,"confirmation_step_id")!=jsonText(task,"step_id")) { return }
    db.query("UPDATE learning_task_images SET confirmation_step_id=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(nextStep),sqlValue(image["id"])])
    view.put("handwriting",draft)
}

public func uploadTaskHandwriting(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    let written=JsonObject()
    try (db=Database.fromEnvironment()) {
        let owner=taskOwner(context,db,accounts); let initial=taskRow(db,id,owner); let upload=readImageUpload(context)
        let body=JsonObject()
        for ((key,value) in upload.fields) {
            if (!["request_id","version","step_id","input_fingerprint"].contains(key)) { throw ApiError(422,"上传包含不支持的字段") }
            body.put(key,JsonString(value))
        }
        let requestId=textField(body,"request_id",80); let step=textField(body,"step_id",36); let fingerprint=textField(body,"input_fingerprint",64)
        if (requestId=="__initial__") { throw ApiError(422,"请求编号不可用") }
        let version=try { Int64.parse(textField(body,"version",12)) } catch (_: Exception) { throw ApiError(422,"步骤版本无效") }
        let bytes=upload.bytes
        let extension=if (bytesMatch(bytes,[0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a],0)) { "png" } else if (bytesMatch(bytes,[0xff,0xd8,0xff],0)) { "jpg" } else if (bytesMatch(bytes,"RIFF".toArray(),0) && bytesMatch(bytes,"WEBP".toArray(),8)) { "webp" } else { throw ApiError(422,"请上传JPEG、PNG或WEBP作答照片") }
        let checksum=sha256(bytes); let values=JsonArray(); for (value in [version.toString(),step,fingerprint,checksum]) { values.add(JsonString(value)) }; let digest=sha256(values.toString().toArray())
        return db.transaction<JsonValue>({ tx =>
            let snapshot=taskSnapshot(tx,jsonText(initial,"question_id"),owner); let task=taskRow(tx,id,owner,lock:true)
            let prior=tx.query("SELECT body_hash FROM learning_task_actions WHERE task_id=? AND request_id=?",[Some(id),Some(requestId)]).rows
            if (!prior.isEmpty()) {
                if (rowText(prior[0],"body_hash")!=digest) { throw ApiError(409,"同一上传编号不能更换照片或步骤") }
                taskValidateVersion(tx,task,snapshot); return taskPublic(task,accounts)
            }
            if (!taskValidateVersion(tx,task,snapshot)) { return taskPublic(task,accounts) }
            if (!["waiting_student","needs_review"].contains(tutorText(task,"status")) || tutorText(tutorObject(task,"student_view"),"input_kind")!="text") { throw ApiError(409,"请先回到当前可作答步骤再上传") }
            if (version!=tutorNumber(task,"version") || step!=jsonText(task,"step_id") || fingerprint!=jsonText(task,"input_fingerprint")) { throw ApiError(409,"学习步骤已更新，请刷新后重新上传") }
            if (taskAtLimit(task)) { throw ApiError(409,"这次学习已到上限，请结束后回原题重开") }
            let imageId=newId(); let path="uploads/answers/${owner}/learning_task/${id}/${imageId}.${extension}"
            written.put("path",JsonString(path)); writeMedia(path,bytes)
            tx.query("INSERT INTO learning_task_images (id,task_id,request_id,input_fingerprint,upload_step_id,original_path,sha256,created_at,updated_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(imageId),Some(id),Some(requestId),Some(fingerprint),Some(step),Some(path),Some(checksum)])
            let event=JsonObject(); event.put("kind",JsonString("recognize_handwriting")); event.put("text",JsonString("")); event.put("handwriting_id",JsonString(imageId))
            tx.query("INSERT INTO learning_task_actions (id,task_id,request_id,body_hash,kind,input_version,input_step_id,body,status,created_at,updated_at) VALUES (?,?,?,?,'recognize_handwriting',?,?,?,'pending',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(id),Some(requestId),Some(digest),Some(version.toString()),Some(step),Some(event.toString())])
            tx.query("UPDATE learning_tasks SET status='queued',version=version+1,pending_action=?,active_request=?,lease_token=NULL,lease_until=NULL,exit_reason='',updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(event.toString()),Some(requestId),Some(id)])
            return taskPublic(taskRow(tx,id,owner),accounts)
        })
    } catch (error: Exception) { if (!tutorText(written,"path").isEmpty()) { removeMedia(tutorText(written,"path")) }; throw error }
    throw ApiError(503,"数据库暂时不可用")
}
