package zhiwei

import stdx.encoding.base64.*
import stdx.encoding.json.*
import stdx.encoding.url.*
import stdx.net.http.*

func exportQuestions(db: Database, paper: JsonObject, includeImages: Bool): JsonArray {
    let result=JsonArray()
    for (row in db.query("SELECT * FROM paper_items WHERE paper_id=? ORDER BY position,id",[sqlValue(paper["id"])]).rows) {
        let question=paperQuestion(db,rowText(row,"question_id"),jsonText(paper,"user_id")); let id=jsonText(question,"id")
        let analyses=db.query("SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1",[Some(id)]).rows
        let diagnoses=db.query("SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",[Some(id)]).rows
        let analysis=if (analyses.isEmpty()) { JsonObject() } else { rowJson("problem_analyses",analyses[0]) }
        let item=JsonObject(); item.put("question_text",question["question_text"]); item.put("answer",JsonString(tutorText(analysis,"final_answer")))
        let explanation=StringBuilder()
        if (!analyses.isEmpty()) {
            for (text in tutorRowTexts(queryArray(db,"reference_steps","SELECT * FROM reference_steps WHERE analysis_id=? ORDER BY step_index",jsonText(analysis,"id")))) { if (!explanation.toString().isEmpty()) { explanation.append("\n") }; explanation.append(text) }
        }
        item.put("explanation",JsonString(explanation.toString())); item.put("subject",question["subject"]); item.put("score",rowJson("paper_items",row)["score"])
        let formula=StringBuilder(); for (value in tutorArray(question,"formulas").getItems()) { if (!formula.toString().isEmpty()) { formula.append("；") }; formula.append(tutorAnswerText(value)) }
        item.put("formula",JsonString(formula.toString())); item.put("options",question["options"]); item.put("misconception",JsonString(if (diagnoses.isEmpty()) { "" } else { rowText(diagnoses[0],"root_misconception") }))
        let images=JsonArray()
        if (includeImages) {
            for (figure in db.query("SELECT path FROM question_assets WHERE question_id=? AND kind='question_figure' ORDER BY created_at,id",[Some(id)]).rows) {
                try { images.add(JsonString(toBase64String(readMedia(rowText(figure,"path"))))) }
                catch (error: ApiError) { if (error.status!=404) { throw error } }
            }
        }
        item.put("figure_images",images); result.add(item)
    }
    return result
}

func exportPaper(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let body=readJson(context,defaultEmpty:true); let kind=if (body.get("kind").isNone()) { "question" } else { tutorText(body,"kind") }
        if (kind!="question" && kind!="answer" && kind!="excel") { throw ApiError(422,"不支持的导出格式") }
        return db.transaction<JsonValue>({ tx =>
            let paper=ownedPaper(tx,id,rowText(user,"id")); let input=JsonObject(); input.put("operation",JsonString("render_paper")); input.put("paper_title",paper["title"]); input.put("paper_kind",JsonString(kind)); input.put("paper_questions",exportQuestions(tx,paper,kind!="excel"))
            let rendered=algorithmCompute(input); let bytes=fromBase64String(jsonText(rendered,"file_base64")).getOrThrow()
            if (bytes.isEmpty() || bytes.size>64*1024*1024 || sha256(bytes)!=jsonText(rendered,"sha256")) { throw ApiError(503,"导出文件校验失败") }
            let jobId=newId(); let suffix=if (kind=="excel") { "xlsx" } else { "pdf" }; let path="reports/${id}-${kind}-${jobId}.${suffix}"
            writeMedia(path,bytes)
            try {
                tx.query("INSERT INTO export_jobs (id,paper_id,kind,status,path,created_at,updated_at) VALUES (?,?,?,'completed',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(jobId),Some(id),Some(kind),Some(path)])
                let result=rowJson("export_jobs",tx.query("SELECT * FROM export_jobs WHERE id=?",[Some(jobId)]).rows[0]); result.put("url",JsonString(accounts.mediaUrl("/"+path))); return result
            } catch (error: Exception) { try { removeMedia(path) } catch (_: Exception) {}; throw error }
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func downloadPaper(context: HttpContext, accounts: Accounts): Unit {
    var started=false
    try {
        requireMethod(context,"GET"); let parts=context.request.url.path.split("/"); let id=parts[parts.size-2]
        let form=Form(context.request.url.rawQuery ?? ""); let requested=queryLast(form,"kind"); let kind=if (requested.isEmpty()) { "question" } else { requested }
        try (db=Database.fromEnvironment()) {
            let user=accounts.currentUser(context,db); ownedPaper(db,id,rowText(user,"id"))
            let jobs=db.query("SELECT * FROM export_jobs WHERE paper_id=? AND kind=? ORDER BY created_at DESC,id DESC LIMIT 1",[Some(id),Some(kind)]).rows
            if (jobs.isEmpty()) { throw ApiError(404,"请先生成导出文件") }
            let path=rowText(jobs[0],"path"); let data=readMedia(path); let suffix=if (kind=="excel") { "xlsx" } else { "pdf" }
            context.responseBuilder.header("Content-Type",if (kind=="excel") { "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" } else { "application/pdf" })
                .header("Content-Disposition","attachment; filename=\"${id}-${kind}.${suffix}\"").header("Content-Length",data.size.toString())
            started=true; HttpResponseWriter(context).write(data)
        }
    } catch (error: ApiError) {
        if (started) { throw error }; let body=JsonObject(); body.put("detail",JsonString(error.message)); jsonResponse(context,body,status:error.status)
    } catch (error: Exception) {
        if (started) { throw error }; let body=JsonObject(); body.put("detail",JsonString("导出文件暂时不可用")); jsonResponse(context,body,status:500)
    }
}
