package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

func ownedPaper(db: Database, id: String, owner: String): JsonObject {
    let rows=db.query("SELECT * FROM papers WHERE id=? AND user_id=?",[Some(id),Some(owner)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"试卷不存在或无权访问") }
    return rowJson("papers",rows[0])
}

func paperQuestion(db: Database, id: String, owner: String): JsonObject {
    let rows=db.query("SELECT * FROM questions WHERE id=? AND user_id=?",[Some(id),Some(owner)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"题目不存在或无权访问") }
    return rowJson("questions",rows[0])
}

func paperDetail(db: Database, accounts: Accounts, paper: JsonObject): JsonObject {
    let id=jsonText(paper,"id"); let items=queryArray(db,"paper_items","SELECT * FROM paper_items WHERE paper_id=? ORDER BY position,id",id)
    for (value in items.getItems()) {
        let item=(value as JsonObject).getOrThrow(); item.put("question",paperQuestion(db,jsonText(item,"question_id"),jsonText(paper,"user_id")))
    }
    let exports=queryArray(db,"export_jobs","SELECT * FROM export_jobs WHERE paper_id=? ORDER BY created_at DESC,id DESC",id)
    for (value in exports.getItems()) { let item=(value as JsonObject).getOrThrow(); item.put("url",JsonString(accounts.mediaUrl("/"+jsonText(item,"path")))) }
    paper.put("items",items); paper.put("exports",exports); return paper
}

func insertPaperItems(db: Database, id: String, owner: String, items: JsonArray): Unit {
    var position: Int64=0
    for (value in items.getItems()) {
        let item=(value as JsonObject).getOrThrow(); let questionId=jsonText(item,"question_id"); paperQuestion(db,questionId,owner)
        db.query("INSERT INTO paper_items (id,paper_id,question_id,position,score,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(id),Some(questionId),Some(position.toString()),sqlValue(item["score"])]); position++
    }
}

func papersApi(context: HttpContext, accounts: Accounts): JsonValue {
    let creating=context.request.method=="POST"; if (!creating) { requireMethod(context,"GET") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        if (!creating) { return queryArray(db,"papers","SELECT * FROM papers WHERE user_id=? ORDER BY created_at,id",rowText(user,"id")) }
        let body=paperPayload(readJson(context),true)
        return db.transaction<JsonValue>({ tx =>
            let id=newId(); let filters=tutorObject(body,"filters"); var ids=tutorArray(body,"question_ids")
            if (ids.getItems().isEmpty()) {
                let candidates=paperCandidatesData(tx,rowText(user,"id"),filters); let chosen=JsonArray(); var count: Int64=0
                for (candidate in candidates.getItems()) {
                    if (count>=tutorNumber(body,"limit")) { break }; chosen.add((candidate as JsonObject).getOrThrow()["id"]); count++
                }
                ids=chosen
            }
            let items=JsonArray()
            for (questionId in ids.getItems()) {
                let item=JsonObject(); item.put("question_id",questionId); var score: JsonValue=body["default_score"]
                for (scored in tutorArray(body,"items").getItems()) { let entry=(scored as JsonObject).getOrThrow(); if (entry["question_id"].toString()==questionId.toString()) { score=entry["score"] } }
                item.put("score",score); items.add(item)
            }
            tx.query("INSERT INTO papers (id,user_id,title,filters,created_at,updated_at) VALUES (?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(id),user["id"],Some(if (body.get("title").isSome()) { jsonText(body,"title") } else { "我的错题练习" }),Some(filters.toString())])
            insertPaperItems(tx,id,rowText(user,"id"),items); return ownedPaper(tx,id,rowText(user,"id"))
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func paperApi(context: HttpContext, accounts: Accounts): JsonValue {
    let method=context.request.method
    if (method!="GET" && method!="PATCH" && method!="DELETE") { throw ApiError(405,"请求方法不支持") }
    let parts=context.request.url.path.split("/"); let id=parts[parts.size-1]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let body=if (method=="PATCH") { paperPayload(readJson(context),false) } else { JsonObject() }
        return db.transaction<JsonValue>({ tx =>
            if (method=="DELETE") {
                let rows=tx.query("SELECT id FROM papers WHERE id=? AND user_id=?",[Some(id),user["id"]]).rows
                let result=JsonObject(); result.put("deleted",JsonBool(!rows.isEmpty()))
                if (rows.isEmpty()) { return result }
                tx.query("DELETE FROM export_jobs WHERE paper_id=?",[Some(id)]); tx.query("DELETE FROM paper_items WHERE paper_id=?",[Some(id)]); tx.query("DELETE FROM papers WHERE id=?",[Some(id)]); return result
            }
            ownedPaper(tx,id,rowText(user,"id"))
            if (method=="PATCH") {
                if (let Some(title) <- body.get("title")) { tx.query("UPDATE papers SET title=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[sqlValue(title),Some(id)]) }
                if (let Some(filters) <- body.get("filters")) { tx.query("UPDATE papers SET filters=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(filters.toString()),Some(id)]) }
                if (body.get("items").isSome()) { tx.query("DELETE FROM paper_items WHERE paper_id=?",[Some(id)]); insertPaperItems(tx,id,rowText(user,"id"),tutorArray(body,"items")) }
            }
            return paperDetail(tx,accounts,ownedPaper(tx,id,rowText(user,"id")))
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
