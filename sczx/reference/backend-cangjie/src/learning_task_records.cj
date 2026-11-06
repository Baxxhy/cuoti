package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

func selfCheckRow(db: Database, task: JsonObject): JsonObject {
    let rows=db.query("SELECT * FROM learning_self_checks WHERE user_id=? AND task_id=?",[sqlValue(task["user_id"]),sqlValue(task["id"])]).rows
    return if (rows.isEmpty()) { JsonObject() } else { rowJson("learning_self_checks",rows[0]) }
}

func selfCheckPublic(note: JsonObject, current: Bool, canSave: Bool): JsonObject {
    let result=JsonObject(); let present=!note.getFields().isEmpty()
    result.put("version",JsonInt(if (present) { tutorNumber(note,"version") } else { 0 }))
    result.put("source_current",JsonBool(current)); result.put("can_save",JsonBool(canSave))
    if (!present || tutorFlag(note,"deleted")) { result.put("note",JsonNull()); return result }
    let item=JsonObject()
    for (key in ["id","task_id","question_id","text","version","updated_at"]) { item.put(key,note[key]) }
    item.put("kind",JsonString("student_self_report")); result.put("note",item); return result
}

func auditSelfCheck(db: Database, task: JsonObject, note: JsonObject, operation: String): Unit {
    let runId=newId(); let evidence=JsonObject()
    for (key in ["task_id","question_id","version","input_fingerprint"]) { evidence.put(key,note[key]) }
    evidence.put("note_id",note["id"]); evidence.put("operation",JsonString(operation)); evidence.put("scope",JsonString("student_self_report")); evidence.put("student_confirmed",JsonBool(true))
    db.query("INSERT INTO agent_runs (id,session_id,agent_name,status,result,created_at,updated_at) VALUES (?,?,'student_self_check','completed',?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(runId),sqlValue(task["session_id"]),Some(evidence.toString())])
    db.query("INSERT INTO agent_tool_calls (id,agent_run_id,tool_name,input_json,output_json,created_at,updated_at) VALUES (?,?,'save_self_check',?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(runId),Some(evidence.toString()),Some(evidence.toString())])
}

public func learningSelfCheck(context: HttpContext, accounts: Accounts): JsonValue {
    let method=context.request.method
    if (!["GET","PATCH","DELETE"].contains(method)) { throw ApiError(405,"此接口不支持该方法") }
    let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let owner=taskOwner(context,db,accounts); let initial=taskRow(db,id,owner)
        let body=if (method=="GET") { JsonObject() } else { readJson(context) }
        if (method!="GET") { taskStrict(body,if (method=="DELETE") { ["version"] } else { ["text","version","confirmed","input_fingerprint"] }) }
        return db.transaction<JsonValue>({ tx =>
            let snapshot=taskSnapshot(tx,jsonText(initial,"question_id"),owner); let task=taskRow(tx,id,owner,lock:true)
            let current=taskValidateVersion(tx,task,snapshot); let canSave=current && tutorText(task,"status")=="completed"
            let note=selfCheckRow(tx,task); let version=if (note.getFields().isEmpty()) { 0 } else { tutorNumber(note,"version") }
            if (method=="GET") { return selfCheckPublic(note,current,canSave) }
            let supplied=body.get("version") ?? JsonNull()
            if (!(supplied is JsonInt) || (supplied as JsonInt).getOrThrow().getValue()<0) { throw ApiError(422,"请提供要点版本") }
            if (method=="DELETE" && (note.getFields().isEmpty() || tutorFlag(note,"deleted"))) { return selfCheckPublic(note,current,canSave) }
            var text=""
            if (method=="PATCH") {
                if (!canSave) { throw ApiError(409,"请完成当前题目版本的学习，再保存自检要点") }
                let confirmation=body.get("confirmed") ?? JsonNull()
                if (!(confirmation is JsonBool) || !tutorFlag(body,"confirmed")) { throw ApiError(422,"请先确认这是你要保存的自检要点") }
                if (textField(body,"input_fingerprint",64)!=jsonText(task,"input_fingerprint")) { throw ApiError(409,"原题版本已变化，请重新核对") }
                text=textField(body,"text",300)
                if (stripWhitespace(text).isEmpty()) { throw ApiError(422,"请写一句自检要点") }
                // Retrying an acknowledged-but-lost response does not create a new revision/audit.
                if (!note.getFields().isEmpty() && !tutorFlag(note,"deleted") && jsonText(note,"text")==text) { return selfCheckPublic(note,current,canSave) }
            }
            if (!jsonEquivalent(supplied,JsonInt(version))) { throw ApiError(409,"自检要点已在别处更新，请重新读取后再保存") }
            if (note.getFields().isEmpty()) {
                tx.query("INSERT INTO learning_self_checks (id,user_id,question_id,task_id,input_fingerprint,text,version,deleted,created_at,updated_at) VALUES (?,?,?,?,?,?,1,0,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(owner),sqlValue(task["question_id"]),Some(id),sqlValue(task["input_fingerprint"]),Some(text)])
            } else {
                tx.query("UPDATE learning_self_checks SET text=?,deleted=?,version=version+1,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(text),Some(if (method=="DELETE") { "1" } else { "0" }),sqlValue(note["id"])])
            }
            let saved=selfCheckRow(tx,task); auditSelfCheck(tx,task,saved,if (method=="DELETE") { "delete" } else { if (version==0) { "create" } else { "edit" } })
            return selfCheckPublic(saved,current,canSave)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

public func learningTaskHistory(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let owner=taskOwner(context,db,accounts); taskRow(db,id,owner)
        let items=JsonArray(); let rows=db.query("SELECT * FROM learning_task_actions WHERE task_id=? ORDER BY created_at DESC,id DESC LIMIT 51",[Some(id)]).rows
        for (index in 0..rows.size) {
            if (index>=50) { break }
            let action=rowJson("learning_task_actions",rows[index]); let result=tutorObject(action,"result"); let item=JsonObject()
            for (key in ["id","kind","status","created_at"]) { item.put(key,action[key]) }
            item.put("text",JsonString(tutorText(tutorObject(action,"body"),"text")))
            // Only public feedback and the verdict/scope of this submitted attempt leave the server.
            item.put("feedback",JsonString(tutorText(tutorObject(result,"student_view"),"feedback")))
            let attempt=tutorObject(result,"attempt")
            item.put("phase",JsonString(tutorText(attempt,"phase"))); item.put("verdict",JsonString(tutorText(attempt,"verdict"))); item.put("assisted",JsonBool(tutorFlag(attempt,"assisted")))
            item.put("source",attempt.get("source") ?? JsonNull())
            let kind=tutorText(action,"kind"); let visual=tutorObject(tutorObject(result,"checkpoint"),"visualization")
            item.put("visualization",JsonNull())
            if (["visualize","observe_visualization","close_visualization"].contains(kind) && !visual.getFields().isEmpty()) {
                let summary=JsonObject(); summary.put("title",tutorObject(visual,"spec")["title"]); summary.put("relation_tex",visual["current_equation_tex"])
                let controls=StringBuilder()
                for (rawVariable in tutorArray(tutorObject(visual,"spec"),"interactive_variables").getItems()) {
                    let variable=(rawVariable as JsonObject).getOrThrow(); let name=tutorText(variable,"name")
                    controls.append(tutorText(variable,"label")+"："+tutorObject(visual,"values")[name].toString()+"；")
                }
                summary.put("controls",JsonString(controls.toString())); item.put("visualization",summary); item.put("phase",visual["source_phase"]); item.put("assisted",JsonBool(true))
            }
            let imageId=tutorText(tutorObject(action,"body"),"handwriting_id")
            item.put("handwriting_image_url",JsonString(if (imageId.isEmpty()) { "" } else { accounts.mediaUrl("/"+jsonText(taskImage(db,taskRow(db,id,owner),imageId),"original_path")) }))
            items.add(item)
        }
        let output=JsonObject(); output.put("items",items); output.put("has_more",JsonBool(rows.size>50)); output.put("source_question",taskSourcePublic(db,id)); return output
    }
    throw ApiError(503,"数据库暂时不可用")
}

func addTaskJourney(db: Database, result: JsonObject, owner: String, questionId: String): JsonObject {
    let rows=db.query("SELECT * FROM learning_tasks WHERE user_id=? AND question_id=? ORDER BY updated_at DESC,id DESC LIMIT 50",[Some(owner),Some(questionId)]).rows
    if (rows.isEmpty()) { return result }
    let snapshot=taskSnapshot(db,questionId,owner); let items=JsonArray(); let events=ArrayList<JsonObject>()
    for (raw in tutorArray(result,"events").getItems()) { events.add((raw as JsonObject).getOrThrow()) }
    var active=""; var repair=false; var original=false; var near=false; var finished=false
    for (row in rows) {
        let task=rowJson("learning_tasks",row); let current=taskValidateVersion(db,task,snapshot); let status=tutorText(task,"status"); let flags=tutorObject(task,"checkpoint"); let assistance=tutorObject(flags,"assistance")
        if (current) {
            repair=repair || tutorFlag(flags,"repair_passed")
            original=original || (tutorFlag(flags,"independent_passed") && !tutorFlag(assistance,"independent"))
            near=near || tutorFlag(task,"learning_applied")
            finished=finished || status=="completed"
            if (active.isEmpty() && ["queued","running","waiting_student","needs_review","failed"].contains(status)) { active=jsonText(task,"id") }
        }
        let item=JsonObject(); for (key in ["id","status","updated_at","learning_applied"]) { item.put(key,task[key]) }; item.put("source_current",JsonBool(current)); items.add(item)
        let detail=if (!current) { "原题已更新，本次过程保留为历史。" } else { if (status=="completed") { if (tutorFlag(task,"learning_applied")) { "本次对照已独立完成，仍需间隔复习检验保持。" } else { "本轮学习已结束，未新增独立迁移证据。" } } else { if (status=="cancelled") { "本次已结束，回答与订正记录保留。" } else { "已保存当前步骤，可回任务继续查看。" } } }
        journeyEvent(events,"task:"+jsonText(task,"id"),jsonText(task,"updated_at"),"订正学习",detail)
    }
    let progress=JsonObject(); progress.put("items",items); progress.put("repair_verified",JsonBool(repair)); progress.put("original_independent",JsonBool(original)); progress.put("near_transfer",JsonBool(near)); result.put("learning_tasks",progress)
    let currentAction=tutorText(tutorObject(result,"next_action"),"url")
    let question=tutorObject(snapshot,"question")
    if (!active.isEmpty() && tutorFlag(question,"confirmed") && tutorText(question,"status")!="awaiting_crop" && !currentAction.startsWith("/pages/ocr/")) {
        let action=JsonObject(); action.put("label",JsonString("继续订正学习")); action.put("url",JsonString("/pages/task/task?id="+active)); action.put("reason",JsonString("从已保存的当前步骤继续，不必重新开始。")); result.put("next_action",action)
    } else if (finished && currentAction.startsWith("/pages/diagnosis/")) { result.put("next_action",JourneyAction.Practice.payload(questionId,"")) }
    if (near) { result.put("summary",JsonString("已有本次单条件对照的独立证据，继续用间隔复习检验保持。")) }
    let notes=JsonArray()
    for (row in db.query("SELECT n.* FROM learning_self_checks n WHERE n.user_id=? AND n.question_id=? AND n.deleted=0 ORDER BY n.updated_at DESC,n.id DESC LIMIT 50",[Some(owner),Some(questionId)]).rows) {
        let note=rowJson("learning_self_checks",row); let task=taskRow(db,jsonText(note,"task_id"),owner)
        let current=jsonText(note,"input_fingerprint")==taskFingerprint(snapshot) && tutorText(task,"status")!="stale" && tutorText(question,"status")!="archived"
        let view=tutorObject(selfCheckPublic(note,current,false),"note"); view.put("source_current",JsonBool(current)); notes.add(view)
        journeyEvent(events,"selfcheck:"+jsonText(note,"id"),jsonText(note,"updated_at"),"保存自检要点",if (current) { "学生确认的提醒，不作为掌握证明。" } else { "原题已更新，这条要点保留为历史提醒。" })
    }
    result.put("self_checks",notes)
    let recent=JsonArray(); let used=HashSet<Int64>()
    for (_ in 0..30) {
        var best: Int64 = -1
        for (index in 0..events.size) { if (!used.contains(index) && (best<0 || journeyTimeKey(jsonText(events[index],"time"))>journeyTimeKey(jsonText(events[best],"time")))) { best=index } }
        if (best<0) { break }; used.add(best); recent.add(events[best])
    }
    result.put("events",recent); return result
}
