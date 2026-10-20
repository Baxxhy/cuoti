package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.json.*
import stdx.net.http.*

// Only the public question projection leaves this module before submission.
func bankQuestion(value: JsonObject, accounts: Accounts): JsonObject {
    let result=JsonObject()
    for (key in ["id","subject","grade","grade_band","title","question_text","question_type","options","difficulty","knowledge_points","source_name"]) {
        result.put(key,value.get(key) ?? JsonNull())
    }
    // Reading passages stay complete in the question, while the bank lists
    // the actual subquestion so a page does not repeat twenty long articles.
    if (!tutorText(tutorObject(value,"source_metadata"),"passage_id").isEmpty()) {
        let paragraphs=jsonText(value,"question_text").split("\n\n")
        if (paragraphs.size>1) { result.put("preview_text",JsonString("阅读理解："+paragraphs[paragraphs.size-1])) }
    }
    let images=JsonArray(); var index: Int64=0
    for (_ in tutorArray(value,"image_paths").getItems()) {
        images.add(JsonString(accounts.mediaUrl("/api/v1/practice/questions/"+jsonText(value,"id")+"/images/"+index.toString()))); index++
    }
    result.put("image_urls",images); return result
}

func bankFilter(subject: String, band: String, source: String, search: String): Array<Option<String>> {
    return [Some(subject),Some(subject),Some(band),Some(band),Some(source),Some(source),Some(search),Some("%"+search+"%")]
}
let bankWhere=" FROM dataset_questions q JOIN dataset_sources s ON s.id=q.dataset_source_id WHERE q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND q.has_answer=1 AND (?='' OR q.subject=?) AND (?='' OR q.grade_band=?) AND (?='' OR q.dataset_source_id=?) AND (?='' OR q.question_text LIKE ?)"

func studyBank(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let form=insightQuery(context)
    let subject=queryLast(form,"subject"); let band=queryLast(form,"grade_band"); let source=queryLast(form,"source_id"); let search=queryLast(form,"search")
    if (subject.size>100 || band.size>100 || source.size>100 || search.size>300) { throw ApiError(422,"筛选条件过长") }
    let page=if (queryLast(form,"page").isEmpty()) { 1 } else { try { Int64.parse(queryLast(form,"page")) } catch (_: Exception) { throw ApiError(422,"页码无效") } }
    if (page<1 || page>10000) { throw ApiError(422,"页码无效") }
    try (db=Database.fromEnvironment()) {
        accounts.currentUser(context,db)
        let filters=bankFilter(subject,band,source,search)
        let count=db.query("SELECT COUNT(*) AS total"+bankWhere,filters).rows[0]
        let result=JsonObject(); result.put("total",JsonInt(Int64.parse(rowText(count,"total")))); result.put("page",JsonInt(page)); result.put("page_size",JsonInt(20))
        let items=JsonArray()
        for (row in db.query("SELECT q.*"+bankWhere+" ORDER BY q.subject,q.id LIMIT 20 OFFSET "+((page-1)*20).toString(),filters).rows) {
            let value=rowJson("dataset_questions",row)
            let sources=db.query("SELECT name FROM dataset_sources WHERE id=?",[row["dataset_source_id"]]).rows
            value.put("source_name",JsonString(if (sources.isEmpty()) { "题库" } else { rowText(sources[0],"name") })); items.add(bankQuestion(value,accounts))
        }
        result.put("questions",items)
        let facets=JsonArray()
        for (row in db.query("SELECT q.subject,q.grade_band,COUNT(*) AS total FROM dataset_questions q WHERE q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND q.has_answer=1 GROUP BY q.subject,q.grade_band ORDER BY q.subject,q.grade_band").rows) {
            let item=JsonObject(); item.put("subject",JsonString(rowText(row,"subject"))); item.put("grade_band",JsonString(rowText(row,"grade_band"))); item.put("count",JsonInt(Int64.parse(rowText(row,"total")))); facets.add(item)
        }
        result.put("facets",facets)
        let sources=JsonArray()
        for (row in db.query("SELECT s.id,s.name,COUNT(*) AS total FROM dataset_sources s JOIN dataset_questions q ON s.id=q.dataset_source_id WHERE q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND q.has_answer=1 GROUP BY s.id,s.name ORDER BY s.name").rows) {
            let item=JsonObject(); item.put("id",JsonString(rowText(row,"id"))); item.put("name",JsonString(rowText(row,"name"))); item.put("count",JsonInt(Int64.parse(rowText(row,"total")))); sources.add(item)
        }
        result.put("sources",sources); return result
    }
    throw ApiError(503,"题库暂时无法读取")
}

func studySessionRow(row: HashMap<String,Option<String>>): JsonObject {
    let value=JsonObject()
    for ((key,raw) in row) {
        if (let Some(text) <- raw) {
            if (key=="version" || key=="duration_seconds" || key=="remaining_seconds" || key=="question_count" || key=="expired") { value.put(key,JsonInt(Int64.parse(text))) }
            else if (key=="results") { value.put(key,JsonValue.fromStr(text)) }
            else { value.put(key,JsonString(text)) }
        } else { value.put(key,JsonNull()) }
    }
    return value
}

func ownedStudy(db: Database, id: String, owner: String, lock!: Bool=false): JsonObject {
    let rows=db.query("SELECT *,CEIL(GREATEST(0,COALESCE(TIMESTAMPDIFF(MICROSECOND,UTC_TIMESTAMP(6),deadline_at),0))/1000000) AS remaining_seconds,IF(deadline_at IS NOT NULL AND deadline_at<=UTC_TIMESTAMP(6),1,0) AS expired FROM study_sessions WHERE id=? AND user_id=?"+if (lock) { " FOR UPDATE" } else { "" },[Some(id),Some(owner)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"没有找到这次练习或考试") }
    return studySessionRow(rows[0])
}

func studyItems(db: Database, id: String): JsonArray {
    let result=JsonArray()
    for (row in db.query("SELECT * FROM study_session_items WHERE session_id=? ORDER BY position",[Some(id)]).rows) {
        let item=JsonObject(); item.put("id",JsonString(rowText(row,"id"))); item.put("position",JsonInt(Int64.parse(rowText(row,"position")))); item.put("snapshot",JsonValue.fromStr(rowText(row,"snapshot")))
        item.put("student_answer",if (let Some(raw) <- row["student_answer"]) { JsonValue.fromStr(raw) } else { JsonNull() })
        item.put("grading",if (let Some(raw) <- row["grading"]) { JsonValue.fromStr(raw) } else { JsonNull() }); result.add(item)
    }
    return result
}

func studyDetail(db: Database, value: JsonObject, accounts: Accounts): JsonObject {
    let items=JsonArray(); let submitted=jsonText(value,"status")=="submitted"
    for (raw in studyItems(db,jsonText(value,"id")).getItems()) {
        let item=(raw as JsonObject).getOrThrow(); let snapshot=tutorObject(item,"snapshot"); let publicItem=JsonObject()
        let available=studyQuestionAvailable(db,snapshot)
        publicItem.put("id",item["id"]); publicItem.put("position",item["position"]); publicItem.put("student_answer",item["student_answer"]); publicItem.put("unavailable",JsonBool(!available))
        if (available) { publicItem.put("question",bankQuestion(snapshot,accounts)) }
        else { let question=JsonObject(); question.put("subject",snapshot["subject"]); question.put("question_type",snapshot["question_type"]); publicItem.put("question",question) }
        if (submitted) {
            publicItem.put("grading",item["grading"])
            if (available) { publicItem.put("answer",snapshot["answer"]); publicItem.put("solution",snapshot["solution"]) }
        }
        items.add(publicItem)
    }
    value.put("items",items); value.put("question_count",JsonInt(items.getItems().size)); return value
}

func studyQuestionAvailable(db: Database, snapshot: JsonObject, lock!: Bool=false): Bool {
    if (jsonText(snapshot,"quality_status")=="format_review") { return false }
    let rows=db.query("SELECT quality_status,source_metadata FROM dataset_questions WHERE id=?"+if (lock) { " FOR SHARE" } else { "" },[Some(jsonText(snapshot,"id"))]).rows
    if (rows.isEmpty()) { return true }
    if (rowText(rows[0],"quality_status")=="format_review") { return false }
    let metadata=(JsonValue.fromStr(rowText(rows[0],"source_metadata")) as JsonObject).getOrThrow()
    for (entry in tutorArray(metadata,"format_review_history").getItems()) {
        if (jsonText((entry as JsonObject).getOrThrow(),"content_hash")==jsonText(snapshot,"content_hash")) { return false }
    }
    return true
}

func studyUnavailableGrade(): JsonObject {
    let grading=JsonObject(); grading.put("correct",JsonNull()); grading.put("can_update_learning",JsonBool(false)); grading.put("method",JsonString("question_unavailable")); grading.put("feedback",JsonString("此题已暂停使用，未计分")); return grading
}

func studyInteger(value: JsonValue, minimum: Int64, maximum: Int64): Int64 {
    if (!(value is JsonInt)) { throw ApiError(422,"请填写整数") }
    return paperInteger(value,minimum,maximum)
}

func studySessions(context: HttpContext, accounts: Accounts): JsonValue {
    let creating=context.request.method=="POST"; if (!creating) { requireMethod(context,"GET") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let owner=rowText(user,"id")
        if (!creating) {
            let result=JsonArray()
            for (row in db.query("SELECT s.*,(SELECT COUNT(*) FROM study_session_items i WHERE i.session_id=s.id) AS question_count FROM study_sessions s WHERE s.user_id=? ORDER BY s.created_at DESC,s.id DESC LIMIT 50",[Some(owner)]).rows) { result.add(studySessionRow(row)) }; return result
        }
        let body=readJson(context); let mode=schoolText(body,"mode","practice",20)
        if (mode!="practice" && mode!="exam") { throw ApiError(422,"请选择练习或模拟考试") }
        let subject=schoolText(body,"subject","",30); let band=schoolText(body,"grade_band","",30); let source=schoolText(body,"source_id","",36)
        let search=schoolText(body,"search","",300)
        let count=studyInteger(body.get("count") ?? JsonInt(5),1,20); let minutes=studyInteger(body.get("minutes") ?? JsonInt(15),1,180)
        let rawIds=body.get("question_ids") ?? JsonArray()
        if (!(rawIds is JsonArray)) { throw ApiError(422,"题目编号格式无效") }
        let ids=(rawIds as JsonArray).getOrThrow()
        if (ids.getItems().size>1) { throw ApiError(422,"单题练习请选择一道题") }
        let strategy=schoolText(body,"selection_strategy","random",20)
        if (strategy!="random" && strategy!="adaptive") { throw ApiError(422,"选题方式无效") }
        let selection=if (strategy=="adaptive" && mode=="practice" && ids.getItems().isEmpty()) { adaptivePracticeSelection(db,owner,subject,band,source,search,count) } else { JsonObject() }
        let selected=tutorArray(selection,"question_ids")
        return db.transaction<JsonValue>({ tx =>
            let rows=if (!selected.getItems().isEmpty()) {
                let picked=ArrayList<HashMap<String,Option<String>>>()
                for (id in selected.getItems()) {
                    let params=ArrayList<Option<String>>(bankFilter(subject,band,source,search)); params.add(sqlValue(id))
                    for (row in tx.query("SELECT q.*"+bankWhere+" AND q.id=?",params.toArray()).rows) { picked.add(row) }
                }
                picked
            } else if (ids.getItems().isEmpty()) {
                tx.query("SELECT q.*"+bankWhere+" ORDER BY RAND() LIMIT "+count.toString(),bankFilter(subject,band,source,search)).rows
            } else {
                tx.query("SELECT * FROM dataset_questions WHERE id=? AND usable_for_practice=1 AND usable_for_auto_grade=1 AND has_answer=1",[Some((editText(ids.getItems()[0],36,minimum:1,trim:true) as JsonString).getOrThrow().getValue())]).rows
            }
            if (rows.isEmpty() || (ids.getItems().isEmpty() && rows.size<count)) { throw ApiError(422,"当前范围题目不足，请减少题数或调整学科") }
            let id=newId(); let title=if (mode=="exam") { (if (subject.isEmpty()) { "综合" } else { subject })+"模拟试卷" } else { (if (subject.isEmpty()) { "题库" } else { subject })+"练习" }
            tx.query("INSERT INTO study_sessions (id,user_id,mode,title,subject,grade_band,status,duration_seconds,deadline_at,version,created_at,updated_at) VALUES (?,?,?,?,?,?,'active',?,IF(?='exam',TIMESTAMPADD(SECOND,?,UTC_TIMESTAMP(6)),NULL),1,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(id),Some(owner),Some(mode),Some(title),Some(subject),Some(band),Some((minutes*60).toString()),Some(mode),Some((minutes*60).toString())])
            var position: Int64=0
            for (row in rows) {
                let snapshot=rowJson("dataset_questions",row); let sources=tx.query("SELECT name FROM dataset_sources WHERE id=?",[row["dataset_source_id"]]).rows
                if (!selected.getItems().isEmpty()) { snapshot.put("adaptive_selection",selection) }
                snapshot.put("source_name",JsonString(if (sources.isEmpty()) { "题库" } else { rowText(sources[0],"name") }))
                tx.query("INSERT INTO study_session_items (id,session_id,position,snapshot,student_answer,grading) VALUES (?,?,?,?,NULL,NULL)",[Some(newId()),Some(id),Some(position.toString()),Some(snapshot.toString())]); position++
            }
            return studyDetail(tx,ownedStudy(tx,id,owner),accounts)
        })
    }
    throw ApiError(503,"暂时无法创建练习")
}

func studyAnswer(value: JsonValue): JsonValue {
    if (value is JsonNull) { return JsonNull() }
    if (value is JsonString) { return editText(value,3000) }
    if (let Some(values) <- (value as JsonArray)) {
        if (values.getItems().size>12) { throw ApiError(422,"选项过多") }
        let result=JsonArray(); let seen=HashSet<String>()
        for (entry in values.getItems()) {
            let clean=(editText(entry,30,minimum:1,trim:true) as JsonString).getOrThrow().getValue()
            if (seen.contains(clean)) { throw ApiError(422,"选项不能重复") }; seen.add(clean); result.add(JsonString(clean))
        }
        return result
    }
    throw ApiError(422,"作答格式无效")
}

func studyAnswered(value: JsonValue): Bool {
    if (let Some(text) <- (value as JsonString)) { return !stripWhitespace(text.getValue()).isEmpty() }
    if (let Some(items) <- (value as JsonArray)) { return !items.getItems().isEmpty() }
    return false
}

func gradeStudyItem(item: JsonObject): JsonObject {
    if (!studyAnswered(item["student_answer"])) {
        let result=JsonObject(); result.put("correct",JsonBool(false)); result.put("can_update_learning",JsonBool(true)); result.put("feedback",JsonString("未作答")); result.put("method",JsonString("unanswered")); return result
    }
    let question=tutorObject(item,"snapshot"); let input=JsonObject(); input.put("operation",JsonString("grade_answer"))
    input.put("text",question["question_text"]); input.put("answer",item["student_answer"]); input.put("expected",question["answer"])
    for (field in ["subject","question_type","options"]) { input.put(field,question[field]) }
    let solution=JsonArray(); for (line in jsonText(question,"solution").split("\n")) { if (!stripWhitespace(line).isEmpty()) { solution.add(JsonString(line)) } }; input.put("reference_solution",solution)
    // Existing internal grading validates model outputs and checks mathematics.
    // Session scores do not change mastery or manufacture wrong-question evidence.
    return algorithmCompute(input,timeoutSeconds:20)
}

func studySessionApi(context: HttpContext, accounts: Accounts): JsonValue {
    let method=context.request.method; let parts=context.request.url.path.split("/"); let id=parts[4]
    let submitting=parts[parts.size-1]=="submit"
    if ((submitting && method!="POST") || (!submitting && method!="GET" && method!="PATCH")) { throw ApiError(405,"请求方法不支持") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db); let owner=rowText(user,"id")
        if (method=="GET") { return studyDetail(db,ownedStudy(db,id,owner),accounts) }
        let body=readJson(context); let version=studyInteger(body.get("version") ?? JsonNull(),1,100000000)
        if (!submitting) {
            let raw=body.get("answers") ?? JsonNull()
            if (!(raw is JsonArray)) { throw ApiError(422,"请提交作答列表") }; let answers=(raw as JsonArray).getOrThrow()
            return db.transaction<JsonValue>({ tx =>
                let session=ownedStudy(tx,id,owner,lock:true)
                if (jsonText(session,"status")!="active") { throw ApiError(409,"已经交卷，不能修改作答") }
                if (tutorNumber(session,"version")!=version) { throw ApiError(409,"作答已在其他页面更新，请重新读取") }
                if (jsonText(session,"mode")=="exam" && tutorNumber(session,"expired")==1) { throw ApiError(409,"考试时间已到，请交卷") }
                let current=studyItems(tx,id); let allowed=HashSet<String>(); let seen=HashSet<String>()
                for (entry in current.getItems()) { allowed.add(jsonText((entry as JsonObject).getOrThrow(),"id")) }
                if (answers.getItems().size!=current.getItems().size) { throw ApiError(422,"作答题目与试卷不一致") }
                for (rawAnswer in answers.getItems()) {
                    if (!(rawAnswer is JsonObject)) { throw ApiError(422,"作答格式无效") }
                    let answer=(rawAnswer as JsonObject).getOrThrow(); let itemId=schoolText(answer,"id","",36)
                    if (!allowed.contains(itemId) || seen.contains(itemId)) { throw ApiError(422,"作答题目与试卷不一致") }; seen.add(itemId)
                    let clean=studyAnswer(answer.get("answer") ?? JsonNull())
                    tx.query("UPDATE study_session_items SET student_answer=? WHERE id=? AND session_id=?",[Some(clean.toString()),Some(itemId),Some(id)])
                }
                tx.query("UPDATE study_sessions SET version=version+1,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(id)])
                return studyDetail(tx,ownedStudy(tx,id,owner),accounts)
            })
        }
        let before=ownedStudy(db,id,owner)
        if (jsonText(before,"status")=="submitted") { return studyDetail(db,before,accounts) }
        if (tutorNumber(before,"version")!=version) { throw ApiError(409,"作答已更新，请重新读取后交卷") }
        let items=studyItems(db,id).getItems(); let results=JsonArray()
        let unavailable=HashSet<String>()
        for (entry in items) { let item=(entry as JsonObject).getOrThrow(); if (!studyQuestionAvailable(db,tutorObject(item,"snapshot"))) { unavailable.add(jsonText(item,"id")) } }
        // Bounded parallel computation outside the transaction; no locks during AI.
        var start: Int64=0
        while (start<items.size) {
            let offset=start; let size=if (items.size-start>4) { 4 } else { items.size-start }
            let jobs=Array(size,{ index =>
                let item=(items[offset+index] as JsonObject).getOrThrow()
                let blocked=unavailable.contains(jsonText(item,"id"))
                spawn { if (blocked) { studyUnavailableGrade() } else { gradeStudyItem(item) } }
            })
            for (job in jobs) { results.add(job.get()) }; start+=size
        }
        return db.transaction<JsonValue>({ tx =>
            let session=ownedStudy(tx,id,owner,lock:true)
            if (jsonText(session,"status")=="submitted") { return studyDetail(tx,session,accounts) }
            if (tutorNumber(session,"version")!=version) { throw ApiError(409,"作答已更新，本次判分未保存，请重新交卷") }
            var correct: Int64=0; var pending: Int64=0; var answered: Int64=0; var excluded: Int64=0
            for (index in 0..items.size) {
                let item=(items[index] as JsonObject).getOrThrow()
                let available=studyQuestionAvailable(tx,tutorObject(item,"snapshot"),lock:true)
                let grading=if (available) { (results.getItems()[index] as JsonObject).getOrThrow() } else { studyUnavailableGrade() }
                if (studyAnswered(item["student_answer"])) { answered++ }
                if (!available) { excluded++ } else if (!tutorFlag(grading,"can_update_learning")) { pending++ } else if (tutorFlag(grading,"correct")) { correct++ }
                tx.query("UPDATE study_session_items SET grading=? WHERE id=? AND session_id=?",[Some(grading.toString()),Some(jsonText(item,"id")),Some(id)])
            }
            let summary=JsonObject(); summary.put("correct",JsonInt(correct)); summary.put("pending",JsonInt(pending)); if (excluded>0) { summary.put("excluded",JsonInt(excluded)) }; summary.put("answered",JsonInt(answered)); summary.put("total",JsonInt(items.size)); summary.put("score",JsonInt(correct*5)); summary.put("max_score",JsonInt((items.size-excluded)*5))
            tx.query("UPDATE study_sessions SET status='submitted',results=?,version=version+1,submitted_at=UTC_TIMESTAMP(6),updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(summary.toString()),Some(id)])
            return studyDetail(tx,ownedStudy(tx,id,owner),accounts)
        })
    }
    throw ApiError(503,"练习记录暂时不可用")
}
