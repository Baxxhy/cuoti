package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

func visualizationConfig(question: JsonObject, points: JsonArray, values: JsonObject): JsonObject {
    let input=JsonObject(); input.put("operation",JsonString("visualization_config")); input.put("subject",question["subject"])
    input.put("question_type",question["question_type"]); input.put("teach_back_points",points); input.put("visualization_values",values)
    return algorithmCompute(input)
}

func visualizationContext(db: Database, id: String, owner: String): JsonObject {
    let sessions=db.query("SELECT * FROM tutor_sessions WHERE id=? AND user_id=?",[Some(id),Some(owner)]).rows
    if (sessions.isEmpty()) { throw ApiError(404,"教学会话不存在或无权访问") }
    let session=rowJson("tutor_sessions",sessions[0]); let snapshot=tutorDataSnapshot(db,jsonText(session,"question_id"),Some(owner))
    let result=JsonObject(); result.put("session",session); result.put("snapshot",snapshot); return result
}

func sessionVisualization(context: HttpContext, accounts: Accounts): JsonValue {
    let writing=context.request.method=="POST"
    if (!writing) { requireMethod(context,"GET") }
    let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let body=if (writing) { readJson(context,defaultEmpty:true) } else { JsonObject() }
        let values=body.get("values") ?? JsonObject()
        if (!(values is JsonObject)) { throw ApiError(422,"演示参数格式不正确") }
        let observation=schoolText(body,"observation","",12000)
        return db.transaction<JsonValue>({ tx =>
            let visible=visualizationContext(tx,id,rowText(user,"id")); let session=tutorObject(visible,"session"); let snapshot=tutorObject(visible,"snapshot")
            let question=tutorObject(snapshot,"question")
            if (writing && (tutorFlag(tutorObject(session,"state"),"question_changed") || jsonText(question,"status")=="archived")) { throw ApiError(409,"题目已变化或归档，请重新开始学习") }
            let config=visualizationConfig(question,tutorStringArray(tutorKnowledge(snapshot)),(values as JsonObject).getOrThrow())
            let specValue=config["spec"]
            if (!(specValue is JsonObject)) { throw ApiError(404,"这道题暂时没有匹配的互动演示") }
            let spec=(specValue as JsonObject).getOrThrow()
            if (!writing) {
                let result=JsonObject(); let summary=JsonObject()
                for (key in ["id","title","question_text"]) { summary.put(key,question[key]) }
                result.put("question",summary); result.put("spec",spec); return result
            }
            let visualId=newId()
            tx.query("INSERT INTO visualization_specs (id,session_id,type,title,spec,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(visualId),Some(id),sqlValue(spec["type"]),sqlValue(spec["title"]),Some(spec.toString())])
            if (!observation.isEmpty()) {
                let interactionId=newId()
                tx.query("INSERT INTO visualization_interactions (id,visualization_id,user_id,`values`,observation,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(interactionId),Some(visualId),user["id"],Some(values.toString()),Some(observation)])
                let input=JsonObject(); input.put("type",spec["type"]); input.put("values",values)
                let output=JsonObject(); output.put("interaction_id",JsonString(interactionId)); output.put("observation",JsonString(observation)); output.put("expected_observation",spec["expected_observation"])
                recordTutorTool(tx,id,"visualization_evidence","observe_visualization",input,output)
            }
            return rowJson("visualization_specs",tx.query("SELECT * FROM visualization_specs WHERE id=?",[Some(visualId)]).rows[0])
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func visualizationTypes(context: HttpContext): JsonValue {
    requireMethod(context,"GET")
    let question=JsonObject(); question.put("subject",JsonString("数学")); question.put("question_type",JsonString("综合题"))
    return visualizationConfig(question,JsonArray(),JsonObject())["catalog"]
}

func readVisualization(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-1]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        let rows=db.query("SELECT v.* FROM visualization_specs v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND s.user_id=?",[Some(id),user["id"]]).rows
        if (rows.isEmpty()) { throw ApiError(404,"可视化不存在或无权访问") }
        let result=rowJson("visualization_specs",rows[0]); result.put("interactions",queryArray(db,"visualization_interactions","SELECT * FROM visualization_interactions WHERE visualization_id=? ORDER BY created_at,id",id)); return result
    }
    throw ApiError(503,"数据库暂时不可用")
}
