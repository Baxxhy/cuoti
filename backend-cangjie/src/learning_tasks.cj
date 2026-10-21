package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.json.*
import stdx.encoding.url.*
import stdx.net.http.*


func taskStrict(body: JsonObject, allowed: Array<String>): Unit {
    for ((key,_) in body.getFields()) { if (!allowed.contains(key)) { throw ApiError(422,"请求包含不支持的字段") } }
}

func taskOwner(context: HttpContext, db: Database, accounts: Accounts): String {
    let user=accounts.currentUser(context,db)
    if (rowText(user,"role")!="student") { throw ApiError(403,"请使用学生账号学习") }
    return rowText(user,"id")
}

func taskRow(db: Database, id: String, owner: String, lock!: Bool=false): JsonObject {
    let rows=db.query("SELECT * FROM learning_tasks WHERE id=? AND user_id=?"+if (lock) { " FOR UPDATE" } else { "" },[Some(id),Some(owner)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"学习任务不存在或无权访问") }
    return rowJson("learning_tasks",rows[0])
}

func taskSnapshot(db: Database, id: String, owner: String, lock!: Bool=true): JsonObject {
    let rows=db.query("SELECT * FROM questions WHERE id=? AND user_id=?"+if (lock) { " FOR UPDATE" } else { "" },[Some(id),Some(owner)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"题目不存在或无权访问") }
    let snapshot=tutorDataSnapshot(db,id,Some(owner))
    snapshot.put("work",firstJson(queryArray(db,"student_works","SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",id)))
    snapshot.put("steps",queryArray(db,"student_steps","SELECT * FROM student_steps WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id",id))
    snapshot.put("assets",queryArray(db,"question_assets","SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id",id))
    snapshot.put("diagnosis",firstJson(queryArray(db,"diagnoses","SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",id)))
    return snapshot
}

func taskFingerprint(snapshot: JsonObject): String { return sha256(diagnosisFingerprint(snapshot).toString().toArray()) }

func taskPublic(task: JsonObject, accounts: Accounts): JsonObject {
    let result=JsonObject()
    for (key in ["id","question_id","session_id","status","version","step_id","input_fingerprint","student_view","created_at","updated_at","learning_applied"]) { result.put(key,task[key]) }
    let view=(JsonValue.fromStr(task["student_view"].toString()) as JsonObject).getOrThrow()
    for (raw in tutorArray(view,"prompt_blocks").getItems()) {
        let block=(raw as JsonObject).getOrThrow(); let images=JsonArray()
        for (path in tutorArray(block,"images").getItems()) { let raw=tutorAnswerText(path); images.add(JsonString(accounts.mediaUrl(if (raw.startsWith("/")) { raw } else { "/"+raw }))) }
        if (!images.getItems().isEmpty()) { block.put("images",images) }
    }
    let draft=tutorObject(view,"handwriting")
    if (!tutorText(draft,"image_url").isEmpty()) { draft.put("image_url",JsonString(accounts.mediaUrl(tutorText(draft,"image_url")))); view.put("handwriting",draft) }
    let limited=taskAtLimit(task) && ["waiting_student","needs_review","failed"].contains(tutorText(task,"status"))
    result.put("restart_required",JsonBool(limited))
    result.put("student_view",if (limited) { taskLimitView() } else { view })
    result.put("last_request_id",task["active_request"])
    result.put("current_action",JsonString(tutorText(tutorObject(task,"pending_action"),"kind")))
    result.put("exit_reason",JsonString(tutorText(task,"exit_reason")))
    return result
}

func taskStoppedView(message: String): JsonObject {
    let view=JsonObject(); view.put("title",JsonString(message)); view.put("prompt_blocks",JsonArray()); view.put("input_kind",JsonString("none")); view.put("primary_action",JsonString("")); view.put("secondary_actions",JsonArray()); view.put("feedback",JsonString(message)); return view
}

func taskValidateVersion(db: Database, task: JsonObject, snapshot: JsonObject): Bool {
    let question=tutorObject(snapshot,"question")
    if (tutorText(task,"input_fingerprint")==taskFingerprint(snapshot) && tutorText(question,"status")!="archived" && tutorFlag(question,"confirmed")) {
        // Older persisted views contain only the stem. Restore options only for
        // the unchanged original question, never for a generated contrast.
        let view=tutorObject(task,"student_view")
        for (raw in tutorArray(view,"prompt_blocks").getItems()) {
            let block=(raw as JsonObject).getOrThrow()
            if (tutorText(block,"kind")=="question" && tutorText(block,"text")==tutorText(question,"question_text") && tutorText(tutorObject(task,"checkpoint"),"phase")!="contrast") {
                block.put("options",tutorArray(question,"options")); block.put("question_type",question["question_type"])
                let figures=JsonArray()
                for (asset in tutorArray(snapshot,"assets").getItems()) {
                    let figure=(asset as JsonObject).getOrThrow()
                    if (tutorText(figure,"kind")=="question_figure") { figures.add(figure["path"]) }
                }
                block.put("images",figures)
            }
        }
        task.put("student_view",view)
        return true
    }
    if (tutorText(task,"status")!="cancelled" && tutorText(task,"status")!="stale") {
        let view=taskStoppedView("题目或学习依据已更新，请回原题重新开始")
        db.query("UPDATE learning_tasks SET status='stale',version=version+1,lease_token=NULL,lease_until=NULL,student_view=?,exit_reason='input_changed',updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(view.toString()),sqlValue(task["id"])])
        db.query("UPDATE learning_task_actions SET status='stale',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",[sqlValue(task["id"])])
        task.put("status",JsonString("stale")); task.put("student_view",view); task.put("version",JsonInt(tutorNumber(task,"version")+1))
    }
    return false
}

func taskContext(db: Database, snapshot: JsonObject, owner: String): JsonObject {
    let result=JsonObject(); let question=tutorObject(snapshot,"question"); let analysis=tutorObject(snapshot,"analysis"); let diagnosis=tutorObject(snapshot,"diagnosis")
    result.put("question_id",question["id"])
    for (key in ["subject","grade","question_type","question_text","options"]) { result.put(key,question.get(key) ?? JsonString("")) }
    if (result["grade"] is JsonNull) { result.put("grade",JsonString("")) }
    result.put("student_work_id",JsonString(tutorText(tutorObject(snapshot,"work"),"id")))
    result.put("student_step_ids",taskStepIds(snapshot,"steps")); result.put("reference_step_ids",taskStepIds(snapshot,"references"))
    result.put("expected",JsonString(tutorText(analysis,"final_answer"))); result.put("reference_steps",tutorStringArray(tutorRowTexts(snapshot["references"]))); result.put("student_steps",tutorStringArray(tutorRowTexts(snapshot["steps"])))
    let step=if (diagnosis.get("first_error_step").isSome() && !(diagnosis["first_error_step"] is JsonNull)) { tutorNumber(diagnosis,"first_error_step") } else { 0 }
    result.put("first_error_step",JsonInt(if (step<0 || step>99) { 0 } else { step }))
    result.put("diagnosed_correct",JsonBool(((diagnosis.get("first_error_step") ?? JsonNull()) is JsonNull) && ["exact","equivalent"].contains(tutorText(diagnosis,"error_type"))))
    result.put("diagnosis_confirmed",JsonBool(tutorFlag(diagnosis,"user_confirmed")))
    result.put("diagnosis_hypothesis",JsonString(tutorText(diagnosis,"root_misconception")))
    let points=tutorKnowledge(snapshot); result.put("knowledge_points",tutorStringArray(points)); let cards=JsonArray(); let seen=HashSet<String>()
    for (point in points) {
        if (cards.getItems().size>=3) { break }
        for (row in db.query("SELECT * FROM knowledge_points WHERE subject=? AND (name=? OR code=?) ORDER BY code LIMIT 3",[sqlValue(question["subject"]),Some(point),Some(point)]).rows) {
            let card=rowJson("knowledge_points",row); let code=jsonText(card,"code")
            if (!seen.contains(code) && cards.getItems().size<3) { cards.add(card); seen.add(code) }
        }
    }
    result.put("cards",cards)
    let prerequisiteCards=JsonArray()
    for (raw in tutorArray(diagnosis,"missing_prerequisites").getItems()) {
        if (prerequisiteCards.getItems().size>=6) { break }
        let label=(raw as JsonString).getOrThrow().getValue()
        for (row in db.query("SELECT k.id FROM knowledge_points k JOIN mastery_states m ON m.subject=k.subject AND (m.knowledge_point=k.name OR m.knowledge_point=k.code) WHERE m.user_id=? AND k.subject=? AND (k.name=? OR k.code=?) AND m.evidence_count>0 AND m.mastery_score<0.3 ORDER BY k.id LIMIT 1",[Some(owner),sqlValue(question["subject"]),Some(label),Some(label)]).rows) { prerequisiteCards.add(JsonString(rowText(row,"id"))) }
    }
    result.put("prerequisite_card_ids",prerequisiteCards)
    result.put("practice_candidates",taskPlanCandidates(db,owner,question,points))
    let seenContrasts=JsonArray()
    for (row in db.query("SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast.question')) AS prompt FROM learning_tasks t JOIN questions q ON q.id=t.question_id WHERE t.user_id=? AND q.subject=? AND (JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast_passed'))='true' OR JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.assistance.contrast'))='true') AND JSON_EXTRACT(t.checkpoint,'$.contrast.question') IS NOT NULL ORDER BY prompt LIMIT 50",[Some(owner),sqlValue(question["subject"])]).rows) { seenContrasts.add(JsonString(rowText(row,"prompt"))) }
    result.put("seen_contrasts",seenContrasts)
    let masteryRows=db.query("SELECT mastery_score,evidence_count,last_evidence_at FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? ORDER BY updated_at DESC,id DESC LIMIT 1",[Some(owner),sqlValue(question["subject"]),Some(learningKnowledgePoint(db,question))]).rows
    if (!masteryRows.isEmpty()) {
        let state=JsonObject(); let count=Int64.parse(rowText(masteryRows[0],"evidence_count")); state.put("mastery",JsonFloat(if (count>0) { Float64.parse(rowText(masteryRows[0],"mastery_score")) } else { 0.35 })); state.put("evidence_count",JsonInt(count))
        state.put("last_effective_at",JsonString(masteryRows[0]["last_evidence_at"] ?? ""))
        let counts=db.query("SELECT COUNT(CASE WHEN JSON_EXTRACT(u.evidence,'$.aemt_event.hint_used')=false THEN 1 END) AS independent_count,COUNT(CASE WHEN JSON_EXTRACT(u.evidence,'$.aemt_event.hint_used')=false AND JSON_UNQUOTE(JSON_EXTRACT(u.evidence,'$.aemt_event.verdict'))='confirmed_correct' THEN 1 END) AS independent_correct,COUNT(CASE WHEN JSON_EXTRACT(u.evidence,'$.aemt_event.hint_used')=true THEN 1 END) AS hinted_count FROM cognitive_updates u JOIN questions q ON q.id=u.question_id WHERE u.user_id=? AND q.subject=? AND u.entity_type='mastery' AND u.entity_key=? AND JSON_EXTRACT(u.evidence,'$.aemt_event.solution_seen')=false",[Some(owner),sqlValue(question["subject"]),Some(learningKnowledgePoint(db,question))]).rows[0]
        for (key in ["independent_count","independent_correct","hinted_count"]) { state.put(key,JsonInt(Int64.parse(rowText(counts,key)))) }
        result.put("mastery_state",state)
    }
    let profiles=db.query("SELECT preferences FROM student_profiles WHERE user_id=?",[Some(owner)]).rows
    if (!profiles.isEmpty()) {
        let preferences=(JsonValue.fromStr(rowText(profiles[0],"preferences")) as JsonObject).getOrThrow()
        let minutes=tutorNumber(preferences,"daily_minutes")
        if (minutes>0 && minutes<=120) {
            let goal=if (minutes<=5) { 3 } else if (minutes<=10) { 5 } else { 10 }
            let completed=db.query("SELECT (SELECT COUNT(DISTINCT question_id) FROM learning_tasks WHERE user_id=? AND status='completed' AND updated_at>=UTC_DATE()) AS tasks,(SELECT COUNT(*) FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id WHERE s.user_id=? AND s.status='submitted' AND s.submitted_at>=UTC_DATE() AND JSON_EXTRACT(i.grading,'$.can_update_learning')=true) AS practice",[Some(owner),Some(owner)]).rows[0]
            let tasks=Int64.parse(rowText(completed,"tasks")); let practice=Int64.parse(rowText(completed,"practice")); let count=tasks+practice; let estimated=tasks*3+practice
            // A transparent estimate, not a fabricated measurement of screen
            // time. A correction reserves three minutes, a bank item one; the active task
            // and actual next-item estimate are accounted for by the planner.
            result.put("available_minutes",JsonInt(if (estimated>=minutes) { 0 } else { minutes-estimated }))
            result.put("goal_remaining",JsonInt(if (count>=goal) { 0 } else { goal-count }))
        }
    }
    applyTaskMemoryContext(result,learningMemory(db,owner,question))
    return result
}

public func learningTasks(context: HttpContext, accounts: Accounts): JsonValue {
    try (db=Database.fromEnvironment()) {
        let owner=taskOwner(context,db,accounts)
        if (context.request.method=="GET") {
            let result=JsonArray()
            let form=try { Form(context.request.url.rawQuery ?? "") } catch (_: Exception) { throw ApiError(422,"筛选条件不正确") }
            let questionId=queryLast(form,"question_id")
            for (row in db.query("SELECT * FROM learning_tasks WHERE user_id=? AND (?='' OR question_id=?) ORDER BY updated_at DESC,id DESC LIMIT 50",[Some(owner),Some(questionId),Some(questionId)]).rows) {
                let item=taskPublic(rowJson("learning_tasks",row),accounts)
                let titles=db.query("SELECT question_text FROM questions WHERE id=?",[row["question_id"]]).rows
                item.put("question_title",JsonString(if (titles.isEmpty()) { "本题学习" } else { academicSummary(rowText(titles[0],"question_text"),60) }))
                result.add(item)
            }
            return result
        }
        requireMethod(context,"POST"); let body=readJson(context); taskStrict(body,["question_id","session_id","request_id"])
        let questionId=textField(body,"question_id",36); let requestId=textField(body,"request_id",80)
        let sessionId=optionalText(body,"session_id","",36)
        let digest=sha256((questionId+"|"+sessionId).toArray())
        return db.transaction<JsonValue>({ tx =>
            let snapshot=taskSnapshot(tx,questionId,owner); let question=tutorObject(snapshot,"question")
            let previous=tx.query("SELECT task_id,body_hash FROM learning_task_requests WHERE user_id=? AND request_id=?",[Some(owner),Some(requestId)]).rows
            if (!previous.isEmpty()) {
                if (rowText(previous[0],"body_hash")!=digest) { throw ApiError(409,"同一请求编号不能用于不同任务") }
                let task=taskRow(tx,rowText(previous[0],"task_id"),owner,lock:true); taskValidateVersion(tx,task,snapshot); return taskPublic(task,accounts)
            }
            if (tutorText(question,"status")=="archived" || !tutorFlag(question,"confirmed") || !(snapshot["analysis"] is JsonObject) || stripWhitespace(tutorText(tutorObject(snapshot,"analysis"),"final_answer")).isEmpty()) { throw ApiError(409,"请先核对题目并完成分析，再开始订正学习") }
            if (!sessionId.isEmpty() && tx.query("SELECT id FROM tutor_sessions WHERE id=? AND user_id=? AND question_id=?",[Some(sessionId),Some(owner),Some(questionId)]).rows.isEmpty()) { throw ApiError(404,"关联学习会话不存在") }
            var id=""; var sourceOrigin="legacy_revalidated"
            let active=tx.query("SELECT * FROM learning_tasks WHERE user_id=? AND question_id=? AND status IN ('queued','running','waiting_student','needs_review','failed') ORDER BY created_at DESC,id DESC LIMIT 1 FOR UPDATE",[Some(owner),Some(questionId)]).rows
            if (!active.isEmpty()) {
                let task=rowJson("learning_tasks",active[0]); if (taskValidateVersion(tx,task,snapshot)) { id=jsonText(task,"id") }
            }
            if (id.isEmpty()) {
                id=newId(); sourceOrigin="created"; let event=JsonObject(); event.put("kind",JsonString("start")); event.put("text",JsonString(""))
                tx.query("INSERT INTO learning_tasks (id,user_id,question_id,session_id,input_fingerprint,status,step_id,checkpoint,student_view,pending_action,active_request,created_at,updated_at) VALUES (?,?,?,?,?,'queued',?,JSON_OBJECT(),?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(id),Some(owner),Some(questionId),if (sessionId.isEmpty()) { None } else { Some(sessionId) },Some(taskFingerprint(snapshot)),Some(newId()),Some(taskStoppedView("正在准备这一步").toString()),Some(event.toString()),Some("__initial__")])
            }
            taskSource(tx,taskRow(tx,id,owner),snapshot,origin:sourceOrigin)
            tx.query("INSERT INTO learning_task_requests (user_id,request_id,task_id,body_hash,created_at) VALUES (?,?,?,?,UTC_TIMESTAMP(6))",[Some(owner),Some(requestId),Some(id),Some(digest)])
            return taskPublic(taskRow(tx,id,owner),accounts)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

public func readLearningTask(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-1]
    try (db=Database.fromEnvironment()) {
        let owner=taskOwner(context,db,accounts); let initial=taskRow(db,id,owner)
        return db.transaction<JsonValue>({ tx =>
            let snapshot=taskSnapshot(tx,jsonText(initial,"question_id"),owner); let task=taskRow(tx,id,owner,lock:true)
            taskValidateVersion(tx,task,snapshot); return taskPublic(task,accounts)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

public func learningTaskAction(context: HttpContext, accounts: Accounts, cancel!: Bool=false): JsonValue {
    requireMethod(context,"POST"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let owner=taskOwner(context,db,accounts); let initial=taskRow(db,id,owner); let body=readJson(context,defaultEmpty:cancel)
        if (!cancel) { taskStrict(body,["kind","text","version","step_id","input_fingerprint","request_id","handwriting_id","handwriting_confirmed","visual_values"]) }
        return db.transaction<JsonValue>({ tx =>
            let snapshot=taskSnapshot(tx,jsonText(initial,"question_id"),owner); let task=taskRow(tx,id,owner,lock:true)
            if (cancel) {
                if (!["completed","cancelled","stale"].contains(jsonText(task,"status"))) {
                    tx.query("UPDATE learning_tasks SET status='cancelled',cancel_requested=1,version=version+1,lease_token=NULL,lease_until=NULL,student_view=?,exit_reason='student_cancelled',updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(taskStoppedView("已结束这次学习，之前的记录仍在").toString()),Some(id)])
                    tx.query("UPDATE learning_task_actions SET status='cancelled',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",[Some(id)])
                }
                return taskPublic(taskRow(tx,id,owner),accounts)
            }
            let requestId=textField(body,"request_id",80); let visualValues=taskVisualValues(body); let values=JsonArray(); for (key in ["kind","text","version","step_id","input_fingerprint","handwriting_id","handwriting_confirmed"]) { values.add(body.get(key) ?? if (key=="text") { JsonString("") } else { JsonNull() }) }; let visualHash=JsonArray(); for (key in ["delta","k","b","a","h"]) { visualHash.add(visualValues.get(key) ?? JsonNull()) }; if (body.get("visual_values").isSome()) { values.add(visualHash) }; let digest=sha256(values.toString().toArray())
            if (requestId=="__initial__") { throw ApiError(422,"请求编号不可用") }
            let prior=tx.query("SELECT body_hash FROM learning_task_actions WHERE task_id=? AND request_id=?",[Some(id),Some(requestId)]).rows
            if (!prior.isEmpty()) {
                if (rowText(prior[0],"body_hash")!=digest) { throw ApiError(409,"同一请求编号不能修改提交内容") }
                taskValidateVersion(tx,task,snapshot); return taskPublic(task,accounts)
            }
            if (!taskValidateVersion(tx,task,snapshot)) { return taskPublic(task,accounts) }
            let status=jsonText(task,"status")
            if (!["waiting_student","needs_review","failed"].contains(status)) { throw ApiError(409,"任务仍在处理或已结束，请先刷新状态") }
            let version=body.get("version") ?? JsonNull()
            if (!(version is JsonInt) || !jsonEquivalent(version,task["version"]) || textField(body,"step_id",36)!=jsonText(task,"step_id") || textField(body,"input_fingerprint",64)!=jsonText(task,"input_fingerprint")) { throw ApiError(409,"这一步已更新，请保留内容并刷新后再提交") }
            let kind=textField(body,"kind",30)
            if (!["answer","hint","reveal","resume","use_text","visualize","observe_visualization","close_visualization"].contains(kind)) { throw ApiError(422,"不支持的学习动作") }
            validateTaskVisualAction(task,body,kind,visualValues)
            let text=if (kind=="observe_visualization") { textField(body,"text",1200) } else { optionalText(body,"text","",12000) }
            if (["answer","observe_visualization"].contains(kind) && stripWhitespace(text).isEmpty()) { throw ApiError(422,"请先写下你的回答") }
            if (taskAtLimit(task)) { throw ApiError(409,"这次学习已到上限，请结束后回原题重开") }
            let event=JsonObject(); event.put("kind",JsonString(kind)); event.put("text",JsonString(text))
            if (kind=="observe_visualization") { event.put("visual_values",visualValues) }
            attachTaskImage(tx,task,body,event)
            if (kind=="resume" && status=="failed" && tutorText(tutorObject(task,"pending_action"),"kind")=="recognize_handwriting") {
                event.put("kind",JsonString("recognize_handwriting")); event.put("handwriting_id",tutorObject(task,"pending_action")["handwriting_id"])
            }
            tx.query("INSERT INTO learning_task_actions (id,task_id,request_id,body_hash,kind,input_version,input_step_id,body,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,'pending',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(id),Some(requestId),Some(digest),Some(kind),sqlValue(version),sqlValue(task["step_id"]),Some(event.toString())])
            tx.query("UPDATE learning_tasks SET status='queued',version=version+1,pending_action=?,active_request=?,lease_token=NULL,lease_until=NULL,exit_reason='',updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(event.toString()),Some(requestId),Some(id)])
            return taskPublic(taskRow(tx,id,owner),accounts)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
