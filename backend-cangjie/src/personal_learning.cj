package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.json.*
import stdx.net.http.*

// Search projections never include reference answers or another learner's records.
func searchReviewQuestions(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let form=insightQuery(context); let query=stripWhitespace(queryLast(form,"q")); let subject=queryLast(form,"subject")
    let scope=if (queryLast(form,"scope").isEmpty()) { "pending" } else { queryLast(form,"scope") }
    if (query.size>300 || subject.size>100 || !["pending","today","completed"].contains(scope)) { throw ApiError(422,"复习筛选条件无效") }
    let page=if (queryLast(form,"page").isEmpty()) { 1 } else { try { Int64.parse(queryLast(form,"page")) } catch (_: Exception) { throw ApiError(422,"页码无效") } }
    if (page<1 || page>10000) { throw ApiError(422,"页码无效") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        let criteria=StringBuilder(); criteria.append(" FROM review_plans p JOIN questions q ON q.id=p.question_id AND q.user_id=p.user_id WHERE p.user_id=? AND q.status<>'archived'")
        let params=ArrayList<Option<String>>(); params.add(user["id"])
        criteria.append(if (scope=="completed") { " AND p.status='completed'" } else { " AND p.status='pending'" })
        if (scope=="today") { criteria.append(" AND p.due_at<TIMESTAMPADD(HOUR,16,DATE(TIMESTAMPADD(HOUR,8,UTC_TIMESTAMP())))") }
        if (!subject.isEmpty()) { criteria.append(" AND q.subject=?"); params.add(Some(subject)) }
        if (!query.isEmpty()) {
            criteria.append(" AND (LOCATE(?,q.question_text)>0 OR LOCATE(?,CAST(q.knowledge_points AS CHAR))>0 OR LOCATE(?,p.reason)>0 OR LOCATE(?,q.title)>0)")
            for (_ in 0..4) { params.add(Some(query)) }
        }
        let total=db.query("SELECT COUNT(*) AS total"+criteria.toString(),params.toArray()).rows[0]
        let items=JsonArray()
        for (row in db.query("SELECT p.id,p.question_id,p.due_at,p.reason,p.status,q.subject,q.grade,q.title,q.question_text,q.knowledge_points,(p.due_at<TIMESTAMPADD(HOUR,16,DATE(TIMESTAMPADD(HOUR,8,UTC_TIMESTAMP())))) AS is_due"+criteria.toString()+" ORDER BY p.due_at "+(if (scope=="completed") { "DESC" } else { "ASC" })+",p.id LIMIT 20 OFFSET "+((page-1)*20).toString(),params.toArray()).rows) {
            let item=JsonObject()
            for (key in ["id","question_id","due_at","reason","status","subject","grade","title","question_text"]) { item.put(key,JsonString(rowText(row,key))) }
            item.put("due_at",JsonString(rowText(row,"due_at").replace(" ","T")+"+00:00"))
            item.put("knowledge_points",JsonValue.fromStr(rowText(row,"knowledge_points"))); item.put("is_due",JsonBool(rowText(row,"is_due")=="1")); items.add(item)
        }
        let result=JsonObject(); result.put("items",items); result.put("total",JsonInt(Int64.parse(rowText(total,"total")))); result.put("page",JsonInt(page)); result.put("page_size",JsonInt(20)); return result
    }
    throw ApiError(503,"复习题目暂时无法读取")
}

func personalKnowledgeFramework(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let nodes=JsonArray(); let edges=JsonArray(); let ids=HashMap<String,String>()
        let counts=HashMap<String,Int64>()
        for (row in db.query("SELECT l.knowledge_point_id,COUNT(DISTINCT l.question_id) AS total FROM user_question_knowledge_links l JOIN questions q ON q.id=l.question_id AND q.user_id=l.user_id WHERE l.user_id=? AND q.status<>'archived' GROUP BY l.knowledge_point_id",[user["id"]]).rows) { counts[rowText(row,"knowledge_point_id")]=Int64.parse(rowText(row,"total")) }
        let mastery=HashMap<String,JsonObject>()
        for (row in db.query("SELECT * FROM mastery_states WHERE user_id=?",[user["id"]]).rows) {
            let value=rowJson("mastery_states",row); mastery[insightPair(jsonText(value,"subject"),jsonText(value,"knowledge_point"))]=value
        }
        for (row in db.query("SELECT * FROM knowledge_points ORDER BY subject,code").rows) {
            let card=rowJson("knowledge_points",row); let content=tutorObject(card,"content"); let node=JsonObject(); let id=jsonText(card,"id"); let code=jsonText(card,"code")
            ids[id]=code
            for (key in ["code","subject","name"]) { node.put(key,card[key]) }
            node.put("grade",JsonString(tutorText(content,"grade"))); node.put("chapter",JsonString(tutorText(content,"chapter")))
            node.put("question_count",JsonInt(counts.get(id) ?? 0))
            node.put("mastery",if (let Some(state) <- mastery.get(insightPair(jsonText(card,"subject"),jsonText(card,"name")))) { state } else { JsonNull() })
            nodes.add(node)
        }
        for (row in db.query("SELECT source_id,target_id FROM knowledge_relations WHERE relation_type='prerequisite' ORDER BY source_id,target_id").rows) {
            if (let Some(source) <- ids.get(rowText(row,"source_id"))) {
                if (let Some(target) <- ids.get(rowText(row,"target_id"))) { let edge=JsonObject(); edge.put("code",JsonString(source)); edge.put("prerequisite_code",JsonString(target)); edges.add(edge) }
            }
        }
        let result=JsonObject(); result.put("nodes",nodes); result.put("relations",edges)
        let profiles=db.query("SELECT grade,preferences FROM student_profiles WHERE user_id=?",[user["id"]]).rows
        var defaultSubject="数学"; var defaultGrade=""
        if (!profiles.isEmpty()) {
            defaultGrade=rowText(profiles[0],"grade")
            let raw=rowText(profiles[0],"preferences")
            if (!raw.isEmpty()) {
                if (let Some(preferences) <- (JsonValue.fromStr(raw) as JsonObject)) {
                    let focus=tutorText(preferences,"focus_subject"); if (!focus.isEmpty()) { defaultSubject=focus }
                }
            }
        }
        result.put("default_subject",JsonString(defaultSubject)); result.put("default_grade",JsonString(defaultGrade)); return result
    }
    throw ApiError(503,"知识框架暂时无法读取")
}

func lessonRow(row: HashMap<String,Option<String>>): JsonObject {
    let item=JsonObject()
    for (key in ["id","knowledge_code","prompt","created_at"]) { item.put(key,JsonString(rowText(row,key))) }
    item.put("result",JsonValue.fromStr(rowText(row,"result"))); return item
}

func lessonCards(db: Database, code: String): JsonArray {
    let rows=db.query("SELECT * FROM knowledge_points WHERE code=?",[Some(code)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"知识卡不存在") }
    let result=JsonArray(); let anchor=rowJson("knowledge_points",rows[0]); result.add(anchor)
    for (row in db.query("SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON k.id=r.target_id WHERE r.source_id=? AND r.relation_type='prerequisite' AND k.subject=? ORDER BY k.code LIMIT 3",[rows[0]["id"],rows[0]["subject"]]).rows) {
        let card=rowJson("knowledge_points",row); card.put("retrieval_role",JsonString("prerequisite")); card.put("anchor_code",JsonString(code)); result.add(card)
    }
    return result
}

// Import timestamps and internal row IDs do not change the teaching material.
// Keep the content, subject and dependency roles in the version boundary.
func lessonSourceVersion(cards: JsonArray): String {
    let source=JsonArray()
    for (value in cards.getItems()) {
        let card=(value as JsonObject).getOrThrow(); let fields=JsonArray()
        for (key in ["code","name","subject","content","retrieval_role","anchor_code"]) { fields.add(card.get(key) ?? JsonNull()) }
        source.add(fields)
    }
    return sha256(source.toString().toArray())
}

func lessonVersionMatches(record: JsonObject, cards: JsonArray, prompt: String): Bool {
    let suffix=":"+sha256(prompt.toArray()); let fingerprint=tutorText(record,"input_fingerprint")
    // Old records remain readable and replayable when their original source is
    // still provable; never silently upgrade an already-stale record.
    return fingerprint==lessonSourceVersion(cards)+suffix || fingerprint==sha256(cards.toString().toArray())+suffix
}

func knowledgeLessons(context: HttpContext, accounts: Accounts): JsonValue {
    let parts=context.request.url.path.split("/"); let code=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        if (context.request.method=="GET") {
            let cards=lessonCards(db,code); let result=JsonArray()
            for (row in db.query("SELECT * FROM knowledge_lessons WHERE user_id=? AND knowledge_code=? ORDER BY created_at DESC,id DESC LIMIT 10",[user["id"],Some(code)]).rows) {
                let item=lessonRow(row); let record=JsonObject(); record.put("input_fingerprint",JsonString(rowText(row,"input_fingerprint")))
                item.put("source_current",JsonBool(lessonVersionMatches(record,cards,rowText(row,"prompt")))); result.add(item)
            }
            return result
        }
        requireMethod(context,"POST")
        let body=readJson(context); let prompt=stripWhitespace(optionalText(body,"prompt","",800)); let requestId=stripWhitespace(optionalText(body,"request_id","",80))
        if (requestId.isEmpty()) { throw ApiError(422,"缺少请求编号") }
        let cards=lessonCards(db,code); let sourceHash=lessonSourceVersion(cards); let fingerprint=sourceHash+":"+sha256(prompt.toArray())
        let previous=db.query("SELECT * FROM knowledge_lessons WHERE user_id=? AND request_id=?",[user["id"],Some(requestId)]).rows
        if (!previous.isEmpty()) {
            let record=JsonObject(); record.put("input_fingerprint",JsonString(rowText(previous[0],"input_fingerprint")))
            if (rowText(previous[0],"knowledge_code")!=code || !lessonVersionMatches(record,cards,prompt)) { throw ApiError(409,"这次提问或知识内容已变化，请重新提问") }
            return lessonRow(previous[0])
        }
        let anchor=(cards.getItems()[0] as JsonObject).getOrThrow(); let input=JsonObject(); input.put("operation",JsonString("knowledge_lesson")); input.put("subject",anchor["subject"]); input.put("grade",JsonString(tutorText(tutorObject(anchor,"content"),"grade"))); input.put("text",JsonString(prompt)); input.put("dialogue_cards",cards)
        let history=JsonArray(); let recent=db.query("SELECT prompt,result FROM knowledge_lessons WHERE user_id=? AND knowledge_code=? AND (input_fingerprint LIKE ? OR input_fingerprint LIKE ?) ORDER BY created_at DESC,id DESC LIMIT 3",[user["id"],Some(code),Some(sourceHash+":%"),Some(sha256(cards.toString().toArray())+":%")]).rows
        for (index in 0..recent.size) {
            let row=recent[recent.size-1-index]; let result=(JsonValue.fromStr(rowText(row,"result")) as JsonObject).getOrThrow(); let turn=JsonObject(); turn.put("question",JsonString(rowText(row,"prompt"))); turn.put("explanation",JsonString(tutorText(result,"explanation"))); turn.put("check_question",JsonString(tutorText(result,"check_question"))); history.add(turn)
        }
        input.put("knowledge_history",history)
        let result=try { algorithmCompute(input,timeoutSeconds:30) } catch (_: ApiError) { throw ApiError(503,"讲解暂时没有完成，请稍后重试。可以先查看知识卡中的公式和示例。") }
        if ((result.get("can_update_learning") ?? JsonNull()).toString()!="false") { throw ApiError(503,"讲解结果未通过检查") }
        return db.transaction<JsonValue>({ tx =>
            let latest=lessonCards(tx,code)
            if (lessonSourceVersion(latest)!=sourceHash) { throw ApiError(409,"知识内容刚刚更新，请重新提问") }
            tx.query("INSERT INTO knowledge_lessons (id,user_id,knowledge_code,request_id,input_fingerprint,prompt,result,created_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(6)) ON DUPLICATE KEY UPDATE id=id",[Some(newId()),user["id"],Some(code),Some(requestId),Some(fingerprint),Some(prompt),Some(result.toString())])
            let saved=tx.query("SELECT * FROM knowledge_lessons WHERE user_id=? AND request_id=?",[user["id"],Some(requestId)]).rows[0]
            let savedRecord=JsonObject(); savedRecord.put("input_fingerprint",JsonString(rowText(saved,"input_fingerprint")))
            if (!lessonVersionMatches(savedRecord,latest,prompt) || rowText(saved,"knowledge_code")!=code) { throw ApiError(409,"请求编号已用于其他提问") }
            return lessonRow(saved)
        })
    }
    throw ApiError(503,"知识讲解暂时不可用")
}

func savedReviewFilters(context: HttpContext, accounts: Accounts, deleting: Bool): JsonValue {
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        if (deleting) {
            requireMethod(context,"DELETE"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-1]
            if (db.query("SELECT id FROM saved_review_filters WHERE id=? AND user_id=?",[Some(id),user["id"]]).rows.isEmpty()) { throw ApiError(404,"复习范围不存在") }
            db.query("DELETE FROM saved_review_filters WHERE id=? AND user_id=?",[Some(id),user["id"]]); let result=JsonObject(); result.put("deleted",JsonBool(true)); return result
        }
        if (context.request.method=="POST") {
            let body=readJson(context); let name=stripWhitespace(optionalText(body,"name","",80)); let query=stripWhitespace(optionalText(body,"q","",300)); let subject=optionalText(body,"subject","",30); let scope=optionalText(body,"scope","pending",20)
            if (name.isEmpty() || !["pending","today","completed"].contains(scope)) { throw ApiError(422,"请填写名称并选择有效的复习范围") }
            db.transaction<Unit>({ tx =>
                tx.query("SELECT id FROM users WHERE id=? FOR UPDATE",[user["id"]])
                let existing=tx.query("SELECT id FROM saved_review_filters WHERE user_id=? AND name=? AND query_text=? AND subject=? AND scope=?",[user["id"],Some(name),Some(query),Some(subject),Some(scope)]).rows
                if (existing.isEmpty()) {
                    if (Int64.parse(rowText(tx.query("SELECT COUNT(*) AS total FROM saved_review_filters WHERE user_id=?",[user["id"]]).rows[0],"total"))>=20) { throw ApiError(409,"最多保存20个复习范围，请先移除不再使用的范围") }
                    tx.query("INSERT INTO saved_review_filters (id,user_id,name,query_text,subject,scope,created_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6))",[Some(newId()),user["id"],Some(name),Some(query),Some(subject),Some(scope)])
                }
                ()
            })
        } else { requireMethod(context,"GET") }
        let result=JsonArray()
        for (row in db.query("SELECT * FROM saved_review_filters WHERE user_id=? ORDER BY created_at DESC,id DESC",[user["id"]]).rows) {
            let item=JsonObject(); for (key in ["id","name","subject","scope"]) { item.put(key,JsonString(rowText(row,key))) }; item.put("q",JsonString(rowText(row,"query_text"))); result.add(item)
        }
        return result
    }
    throw ApiError(503,"复习范围暂时无法保存")
}
