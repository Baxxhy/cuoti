package zhiwei

import std.collection.*
import std.time.*
import stdx.encoding.json.*
import stdx.net.http.*

// These are navigation decisions from persisted facts, not grading or mastery calculations.
enum JourneyAction {
    Crop | Processing | Confirm | Diagnose | Resume | Review | Learn | Practice
    func payload(question: String, target: String): JsonObject {
        let (label,path,reason)=match (this) {
            case Crop => ("继续框选题目","/pages/crop/crop?id="+question,"框选要学习的题目，再开始识别。")
            case Processing => ("查看识别进度","/pages/ocr/ocr?id="+question+"&job="+target,"识别仍在处理中，完成后核对题干和答案。")
            case Confirm => ("核对题目信息","/pages/ocr/ocr?id="+question+if (target.isEmpty()) { "" } else { "&job="+target },"确认题干和自己的作答，避免识别偏差影响诊断。")
            case Diagnose => ("开始错因诊断","/pages/diagnosis/diagnosis?id="+question,"根据确认后的题目与步骤寻找错误原因。")
            case Resume => ("继续上次辅导","/pages/tutor/tutor?id="+target,"从已保存的学习阶段继续。")
            case Review => ("完成到期复习","/pages/review/review?plan="+target,"先独立回忆，再根据判题结果安排下次复习。")
            case Learn => ("查看诊断并学习","/pages/diagnosis/diagnosis?id="+question,"理解首错原因，再练习验证。")
            case Practice => ("练一道相似题","/pages/practice/practice?id="+question,"用独立作答检验理解。")
        }
        let result=JsonObject(); result.put("label",JsonString(label)); result.put("url",JsonString(path)); result.put("reason",JsonString(reason)); return result
    }
}

func journeyTimeKey(time: String): String {
    let utc=time.replace("+00:00","").replace("Z","").replace(" ","T")
    if (!utc.contains(".")) { return utc+".000000" }
    var result=utc; while (result.size<26) { result+="0" }; return result
}

func journeyTime(time: String): String {
    let key=journeyTimeKey(time)
    return (if (key.endsWith(".000000")) { key[..19] } else { key })+"+00:00"
}

func journeyTrusted(item: JsonObject): Bool {
    let details=tutorObject(item,"grading_details")
    return tutorFlag(details,"can_update_learning") && !tutorFlag(details,"question_changed")
}

func journeyStep(key: String,label: String,done: Bool,detail: String): JsonObject {
    let result=JsonObject(); result.put("key",JsonString(key)); result.put("label",JsonString(label)); result.put("completed",JsonBool(done)); result.put("detail",JsonString(detail)); return result
}

func journeyEvent(events: ArrayList<JsonObject>,id: String,time: String,title: String,detail: String): Unit {
    let item=JsonObject(); item.put("id",JsonString(id)); item.put("time",JsonString(journeyTime(time))); item.put("title",JsonString(title)); item.put("detail",JsonString(detail)); events.add(item)
}

func buildLearningJourney(data: JsonObject,now: String): JsonObject {
    let question=tutorObject(data,"question"); let qid=jsonText(question,"id")
    let diagnosis=tutorObject(data,"diagnosis"); let analysis=tutorObject(data,"analysis"); let job=tutorObject(data,"job"); let ocr=tutorObject(data,"ocr")
    var latest=""; var active=""; var activeTime=""; var understanding=false; var independent=false
    let events=ArrayList<JsonObject>()
    journeyEvent(events,"question:"+qid,jsonText(question,"created_at"),"记录错题",jsonText(question,"subject")+" · "+jsonText(question,"question_type"))
    if (!ocr.getFields().isEmpty()) { journeyEvent(events,"ocr:"+jsonText(ocr,"id"),jsonText(ocr,"created_at"),"图片识别","识别完成，请以人工核对后的内容为准。") }
    if (!diagnosis.getFields().isEmpty()) { let root=tutorText(diagnosis,"root_misconception"); journeyEvent(events,"diagnosis:"+jsonText(diagnosis,"id"),jsonText(diagnosis,"created_at"),"错因诊断",if (root.isEmpty()) { "可在诊断页查看具体证据。" } else { root }) }
    for (raw in tutorArray(data,"sessions").getItems()) {
        let session=(raw as JsonObject).getOrThrow(); let flags=tutorObject(session,"state"); let time=journeyTimeKey(jsonText(session,"created_at"))
        if (!tutorFlag(flags,"question_changed")) {
            if (latest.isEmpty() || time>latest) { latest=time }
            if (jsonText(session,"status")=="active" && (activeTime.isEmpty() || time>activeTime)) { active=jsonText(session,"id"); activeTime=time }
            understanding=understanding || (tutorFlag(flags,"understanding_passed") && tutorFlag(flags,"teach_back_passed"))
            independent=independent || (tutorFlag(flags,"near_transfer") && tutorFlag(flags,"far_transfer") && !tutorFlag(flags,"assisted") && !tutorFlag(flags,"transfer_insufficient"))
        }
        var detail=if (jsonText(session,"status")=="completed") { "本轮已结束，后续仍需独立练习和复习。" } else { "学习进度已保存，可继续。" }
        if (tutorFlag(flags,"question_changed")) { detail="题目信息已修改，本次记录保留为历史，不计入当前进度。" }
        else if (tutorFlag(flags,"assisted") || tutorFlag(flags,"transfer_insufficient")) { detail="本轮使用了辅助或迁移尚不稳定，仍需巩固。" }
        journeyEvent(events,"session:"+jsonText(session,"id"),jsonText(session,"updated_at"),"辅导记录",detail)
    }
    var attempts: Int64=0; var verified: Int64=0; var correct: Int64=0; var waiting: Int64=0
    for (raw in tutorArray(data,"practices").getItems()) {
        let item=(raw as JsonObject).getOrThrow(); attempts++; let trusted=journeyTrusted(item); let changed=tutorFlag(tutorObject(item,"grading_details"),"question_changed")
        if (trusted) { verified++; if (tutorFlag(item,"correct")) { correct++ } }
        if (!tutorFlag(tutorObject(item,"grading_details"),"can_update_learning") && !changed) { waiting++ }
        var detail=if (trusted) { if (tutorFlag(item,"correct")) { "独立练习作答正确" } else { "本次作答仍需巩固" } } else { "本次结果待核对，未作为掌握证据" }
        if (changed) { detail="题目信息已修改，此次练习作为历史记录保留。" }
        journeyEvent(events,"practice:"+jsonText(item,"id"),jsonText(item,"created_at"),"题库练习",detail)
    }
    var completed: Int64=0; var reviewCorrect=false
    for (raw in tutorArray(data,"reviews").getItems()) {
        let item=(raw as JsonObject).getOrThrow(); let trusted=journeyTrusted(item) && jsonText(item,"grade")!="pending"
        if (trusted) { completed++; reviewCorrect=reviewCorrect || tutorFlag(item,"correct") }
        var detail=if (trusted) { if (tutorFlag(item,"correct")) { "复习作答正确" } else { "复习仍需巩固" } } else { "等待完成判定和难度反馈" }
        if (tutorFlag(tutorObject(item,"grading_details"),"question_changed")) { detail="题目信息已修改，此次复习作为历史记录保留。" }
        journeyEvent(events,"review:"+jsonText(item,"id"),jsonText(item,"created_at"),"复习作答",detail)
    }
    // Chinese local-day boundary matches the original student review page.
    let seconds=DateTime.parse(now).toUnixTimeStamp().toSeconds(); let endDay=((seconds+8*3600)/86400+1)*86400-8*3600
    var due: Int64=0; var nextTime=""; var nextId=""
    for (raw in tutorArray(data,"plans").getItems()) {
        let plan=(raw as JsonObject).getOrThrow(); if (jsonText(plan,"status")!="pending") { continue }
        let time=jsonText(plan,"due_at"); let key=journeyTimeKey(time)
        if (nextTime.isEmpty() || key<journeyTimeKey(nextTime)) { nextTime=time; nextId=jsonText(plan,"id") }
        if (DateTime.parse(time).toUnixTimeStamp().toSeconds()<endDay) { due++ }
    }
    var action=JourneyAction.Practice; var target=""
    if (jsonText(question,"status")=="awaiting_crop") { action=JourneyAction.Crop }
    else if (tutorText(job,"status")=="pending" || tutorText(job,"status")=="running") { action=JourneyAction.Processing; target=jsonText(job,"id") }
    else if (!tutorFlag(question,"confirmed")) { action=JourneyAction.Confirm; if (tutorText(job,"status")=="failed") { target=jsonText(job,"id") } }
    else if (diagnosis.getFields().isEmpty()) { action=JourneyAction.Diagnose }
    else if (!active.isEmpty()) { action=JourneyAction.Resume; target=active }
    else if (due>0) { action=JourneyAction.Review; target=nextId }
    else if (latest.isEmpty()) { action=JourneyAction.Learn }
    let stages=JsonArray()
    stages.add(journeyStep("confirmed","核对题目",tutorFlag(question,"confirmed"),if (tutorFlag(question,"confirmed")) { "题干与作答已确认" } else { "等待核对识别内容" }))
    stages.add(journeyStep("diagnosed","找到错因",!diagnosis.getFields().isEmpty(),if (diagnosis.getFields().isEmpty()) { "等待完成诊断" } else { "已有诊断证据，可查看和纠正" }))
    stages.add(journeyStep("understanding","理解并讲清",understanding,if (understanding) { "理解检查与教回均通过" } else { "以实际检查与教回结果为准" }))
    stages.add(journeyStep("transfer","独立迁移",independent,if (independent) { "相似题和综合应用均独立通过" } else { "尚无完整的独立迁移证据" }))
    stages.add(journeyStep("review","间隔复习",reviewCorrect,if (completed>0) { "完成 ${completed} 次有效复习" } else { "等待复习验证长期保持" }))
    // At most 203 events, return newest 30; equal-time events retain source order.
    let recent=JsonArray(); let used=HashSet<Int64>()
    for (_ in 0..30) {
        var best: Int64 = -1
        for (index in 0..events.size) { if (!used.contains(index) && (best<0 || journeyTimeKey(jsonText(events[index],"time"))>journeyTimeKey(jsonText(events[best],"time")))) { best=index } }
        if (best<0) { break }; used.add(best); recent.add(events[best])
    }
    let result=JsonObject(); for (key in ["title","question_text","subject"]) { result.put(key,question[key]) }
    result.put("question_id",JsonString(qid)); result.put("generated_at",JsonString(journeyTime(now))); result.put("stages",stages); result.put("next_action",action.payload(qid,target)); result.put("summary",JsonString(if (independent) { "曾有独立迁移证据，继续用复习检验保持。" } else { "按记录逐步巩固，完成辅导不等于已经掌握。" }))
    let verification=JsonObject(); verification.put("label",JsonString(if (tutorFlag(analysis,"verified")) { "已完成规则校验" } else { "尚未通过规则校验" })); verification.put("verified",JsonBool(tutorFlag(analysis,"verified"))); verification.put("diagnosis_confirmed",JsonBool(tutorFlag(diagnosis,"user_confirmed"))); result.put("verification",verification)
    let practice=JsonObject(); practice.put("attempts",JsonInt(attempts)); practice.put("verified_attempts",JsonInt(verified)); practice.put("correct",JsonInt(correct)); practice.put("pending",JsonInt(waiting)); result.put("practice",practice)
    let review=JsonObject(); review.put("completed",JsonInt(completed)); review.put("due",JsonInt(due)); review.put("next_due_at",if (nextTime.isEmpty()) { JsonNull() } else { JsonString(journeyTime(nextTime)) }); result.put("review",review); result.put("events",recent); result.put("history_limit",JsonInt(50)); return result
}

func learningJourney(context: HttpContext,accounts: Accounts): JsonValue {
    requireMethod(context,"GET"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let rows=tx.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived'",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"题目不存在") }
            let data=JsonObject(); data.put("question",rowJson("questions",rows[0]))
            for ((key,table) in [("analysis","problem_analyses"),("diagnosis","diagnoses"),("job","processing_jobs"),("ocr","ocr_runs")]) { data.put(key,firstJson(queryArray(tx,table,"SELECT * FROM ${table} WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",id))) }
            for ((key,table,column) in [("sessions","tutor_sessions","question_id"),("practices","dataset_practice_attempts","mistake_id"),("plans","review_plans","question_id")]) {
                let values=JsonArray(); let filter=if (key=="plans") { " AND status='pending' ORDER BY due_at,id" } else { " ORDER BY created_at DESC,id DESC" }
                for (row in tx.query("SELECT * FROM ${table} WHERE ${column}=? AND user_id=?"+filter+" LIMIT 50",[Some(id),user["id"]]).rows) { values.add(rowJson(table,row)) }; data.put(key,values)
            }
            let reviews=JsonArray(); for (row in tx.query("SELECT r.* FROM review_records r JOIN review_plans p ON p.id=r.plan_id WHERE p.question_id=? AND p.user_id=? ORDER BY r.created_at DESC,r.id DESC LIMIT 50",[Some(id),user["id"]]).rows) { reviews.add(rowJson("review_records",row)) }; data.put("reviews",reviews)
            let now=rowText(tx.query("SELECT UTC_TIMESTAMP(6) AS now").rows[0],"now").replace(" ","T")+"+00:00"
            return addTaskJourney(tx,buildLearningJourney(data,now),rowText(user,"id"),id)
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
