package zhiwei

import std.collection.*
import stdx.encoding.base64.*
import stdx.encoding.json.*
import stdx.net.http.*

func dialogueSnapshot(db: Database, id: String, owner: Option<String>): JsonObject {
    let rows=db.query("SELECT * FROM tutor_sessions WHERE id=? AND user_id=? FOR UPDATE",[Some(id),owner]).rows
    if (rows.isEmpty()) { throw ApiError(404,"教学会话不存在或无权访问") }
    let session=rowJson("tutor_sessions",rows[0]); let stage=canonicalTutorStage(jsonText(session,"stage")); session.put("stage",JsonString(stage))
    if (stage=="finished") { throw ApiError(409,"本次学习已经完成") }
    let questionId=jsonText(session,"question_id"); let snapshot=tutorDataSnapshot(db,questionId,owner); let question=tutorObject(snapshot,"question")
    if (jsonText(question,"status")=="archived" || tutorFlag(tutorObject(session,"state"),"question_changed")) { throw ApiError(409,"题目已变化或归档，请重新开始学习") }
    snapshot.put("session",session)
    snapshot.put("steps",queryArray(db,"student_steps","SELECT * FROM student_steps WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id",questionId))
    snapshot.put("work",firstJson(queryArray(db,"student_works","SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",questionId)))
    snapshot.put("assets",queryArray(db,"question_assets","SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id",questionId))
    snapshot.put("turns",queryArray(db,"tutor_turns","SELECT * FROM tutor_turns WHERE session_id=? ORDER BY created_at DESC,id DESC LIMIT 7",id))
    let memory=learningMemory(db,owner.getOrThrow(),question)
    snapshot.put("memory",memory["legacy_rows"]); snapshot.put("memory_snapshot",memory["snapshot"]); return snapshot
}

func dialogueContext(snapshot: JsonObject, message: String): JsonObject {
    let question=tutorObject(snapshot,"question"); let analysis=tutorObject(snapshot,"analysis"); let session=tutorObject(snapshot,"session"); let state=tutorObject(session,"state")
    let result=JsonObject(); result.put("memory_snapshot",snapshot["memory_snapshot"])
    for (key in ["subject","question_type","question_text","student_answer","knowledge_points"]) { result.put(key,question[key]) }
    let points=JsonArray(); let labels=HashSet<String>()
    for (container in [question,analysis]) { for (point in tutorArray(container,"knowledge_points").getItems()) { let label=point.toString(); if (!labels.contains(label) && points.getItems().size<10) { points.add(point); labels.add(label) } } }
    result.put("knowledge_points",points)
    result.put("grade",JsonString(tutorText(question,"grade")))
    result.put("final_answer",JsonString(tutorText(analysis,"final_answer"))); result.put("reference_steps",tutorStringArray(tutorRowTexts(snapshot["references"]))); result.put("student_steps",tutorStringArray(tutorRowTexts(snapshot["steps"])))
    result.put("student_message",JsonString(message)); result.put("turn_count",JsonInt(tutorNumber(session,"turn_count")+1)); result.put("hint_level",session["hint_level"])
    result.put("repeated_count",JsonInt(if (message==tutorText(state,"last_message")) { tutorNumber(state,"repeated_count")+1 } else { 0 }))
    let recent=JsonArray(); let rows=tutorArray(snapshot,"turns").getItems()
    for (offset in 0..rows.size) { let turn=(rows[rows.size-1-offset] as JsonObject).getOrThrow(); let item=JsonObject(); item.put("role",turn["role"]); item.put("content",turn["content"]); recent.add(item) }
    let input=JsonObject(); input.put("role",JsonString("user")); input.put("content",JsonString(message)); recent.add(input); result.put("recent_turns",recent); return result
}

func dialogueCardScore(card: JsonObject, query: String, grade: String): Int64 {
    let content=tutorObject(card,"content"); let level=tutorText(content,"grade")
    if (grade.startsWith("初") && level.startsWith("高")) { return 0 }
    let text=knowledgeLabel(query); var score: Int64=0
    for (label in [jsonText(card,"name"),jsonText(card,"code")]) {
        let key=knowledgeLabel(label); if (runeCount(key)>=2 && text.contains(key)) { score=100+runeCount(key) }
    }
    for (value in tutorArray(content,"related_knowledge").getItems()) {
        if (let Some(alias) <- (value as JsonString)) {
            let key=knowledgeLabel(alias.getValue()); if (runeCount(key)>=2 && text.contains(key) && score==0) { score=runeCount(key) }
        }
    }
    return score
}

func dialogueKnowledge(db: Database, query: String, subject: String, grade: String): JsonArray {
    let available=db.query("SELECT * FROM knowledge_points WHERE subject=? ORDER BY code LIMIT 200",[Some(subject)]).rows
    let rows=ArrayList<HashMap<String,Option<String>>>()
    let consumed=HashSet<String>()
    for (_ in 0..3) {
        var best: Int64=0; var selected: Int64 = -1
        for (index in 0..available.size) {
            let card=rowJson("knowledge_points",available[index]); let score=dialogueCardScore(card,query,grade)
            if (!consumed.contains(jsonText(card,"id")) && score>best) { best=score; selected=index }
        }
        if (selected<0) { break }; rows.add(available[selected]); consumed.add(rowText(available[selected],"id"))
    }
    let result=JsonArray(); let seen=HashSet<String>()
    for (row in rows) {
        let card=rowJson("knowledge_points",row); card.put("retrieval_role",JsonString("anchor")); result.add(card); seen.add(jsonText(card,"code"))
    }
    // Seed relation source is the current topic, target is its prerequisite.
    for (row in rows) {
        let anchor=rowJson("knowledge_points",row)
        for (dependency in db.query("SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON r.target_id=k.id WHERE r.source_id=? AND r.relation_type='prerequisite' AND k.subject=? ORDER BY k.code LIMIT 2",[sqlValue(anchor["id"]),Some(subject)]).rows) {
            let card=rowJson("knowledge_points",dependency); let code=jsonText(card,"code")
            if (result.getItems().size>=8 || seen.contains(code)) { continue }
            card.put("retrieval_role",JsonString("prerequisite")); card.put("anchor_code",anchor["code"]); result.add(card); seen.add(code)
        }
    }
    return result
}

func tutorDialogue(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let body=readJson(context); let message=stripWhitespace(optionalText(body,"message","",12000))
        if (message.isEmpty()) { throw ApiError(422,"请输入你的想法") }
        let snapshot=db.transaction<JsonObject>({ tx => dialogueSnapshot(tx,id,user["id"]) }); let input=JsonObject(); let domain=dialogueContext(snapshot,message)
        input.put("operation",JsonString("tutor_dialogue_prepare")); input.put("dialogue_context",domain); input.put("dialogue_memory_rows",snapshot["memory"])
        let preparation=algorithmCompute(input); let plan=tutorObject(preparation,"plan"); let knowledge=tutorText(plan,"tool_name")=="knowledge_search"
        let cards=if (knowledge) { dialogueKnowledge(db,jsonText(preparation,"knowledge_query"),jsonText(domain,"subject"),jsonText(domain,"grade")) } else { JsonArray() }
        input.put("operation",JsonString("tutor_dialogue_finish")); input.put("dialogue_preparation",preparation); input.put("dialogue_cards",cards)
        let images=JsonArray(); let seen=HashSet<String>()
        for (value in tutorArray(snapshot,"assets").getItems()) {
            let path=jsonText((value as JsonObject).getOrThrow(),"path")
            if (seen.contains(path)) { continue }; seen.add(path)
            try { images.add(JsonString(toBase64String(readMedia(path)))) } catch (error: ApiError) { if (error.status!=404) { throw error } }
        }
        input.put("images_base64",images); let computed=algorithmCompute(input)
        return db.transaction<JsonValue>({ tx =>
            let current=dialogueSnapshot(tx,id,user["id"])
            if (!jsonEquivalent(snapshot,current)) { throw ApiError(409,"题目、会话或学习记录已变化，请刷新后重试") }
            if (knowledge && !jsonEquivalent(cards,dialogueKnowledge(tx,jsonText(preparation,"knowledge_query"),jsonText(domain,"subject"),jsonText(domain,"grade")))) { throw ApiError(409,"知识卡已更新，请重试") }
            let session=tutorObject(current,"session"); let state=tutorObject(session,"state"); let stage=jsonText(session,"stage"); let graph=tutorObject(computed,"graph"); let agent=tutorObject(computed,"agent"); let tool=tutorObject(agent,"tool"); let verification=tutorObject(agent,"verification")
            state.put("last_message",JsonString(message)); state.put("repeated_count",domain["repeated_count"])
            for (key in ["branch","strategy","next_goal","mastery_proven"]) { state.put(key,graph[key]) }
            if (state.get("understanding_passed").isNone()) { state.put("understanding_passed",JsonBool(false)) }
            state.put("dialogue_stage",graph["stage"]); state.put("agent_verification",verification["status"]); state.put("agent_memory_refs",plan["memory_source_ids"])
            if (tutorText(plan,"tool_name")=="visualization") { state.put("visualization_type",tutorObject(tool,"evidence").get("visualization_type") ?? JsonNull()) }
            tx.query("UPDATE tutor_sessions SET stage=?,turn_count=?,hint_level=?,state=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(stage),sqlValue(domain["turn_count"]),sqlValue(graph["hint_level"]),Some(state.toString()),Some(id)])
            let userMeta=JsonObject(); userMeta.put("input_stage",JsonString(stage)); let metadata=JsonObject()
            for (key in ["branch","strategy","next_goal","mastery_proven"]) { metadata.put(key,graph[key]) }
            metadata.put("knowledge_sources",computed.get("knowledge_sources") ?? JsonArray()); metadata.put("tool_name",plan["tool_name"]); metadata.put("decision_verified",verification["status"]); metadata.put("planner_status",agent["planner_status"])
            for ((role,text,meta) in [("user",message,userMeta),("assistant",jsonText(computed,"reply"),metadata)]) { tx.query("INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(id),Some(role),Some(text),Some(stage),Some(meta.toString())]) }
            let output=tutorObject(tool,"evidence"); output.put("stage",JsonString(stage)); output.put("next_goal",graph["next_goal"]); output.put("executed",tool["executed"])
            let details=JsonObject(); details.put("memory_manifest",memoryAuditManifest(tutorObject(snapshot,"memory_snapshot"))); for (key in ["observation","plan","verification","planner_status"]) { details.put(key,agent[key]) }
            recordTutorTool(tx,id,jsonText(graph,"branch"),jsonText(plan,"tool_name"),tutorObject(tool,"consumed_input"),output,runResult:details)
            let result=JsonObject(); result.put("message",computed["reply"]); result.put("stage",JsonString(stage)); result.put("hint_level",graph["hint_level"]); for ((key,value) in metadata.getFields()) { result.put(key,value) }; return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
