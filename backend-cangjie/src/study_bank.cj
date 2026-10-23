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
    for ((key,item) in datasetQuestionImages(value,accounts).getFields()) { result.put(key,item) }
    return result
}

func bankGradeAlias(grade: String): String {
    match (grade) {
        case "初一" => "七年级"
        case "初二" => "八年级"
        case "初三" => "九年级"
        case _ => grade
    }
}

func bankStudentGrade(db: Database, owner: String): String {
    let rows=db.query("SELECT grade FROM student_profiles WHERE user_id=?",[Some(owner)]).rows
    let grade=if (rows.isEmpty()) { "" } else { rowText(rows[0],"grade") }
    if (!(["初一","初二","初三","高一","高二","高三"].contains(grade))) { throw ApiError(422,"请先在学习设置中选择具体年级") }
    return grade
}

// Conservative exclusion: source grade labels are necessary, not sufficient.
// These rules reject obvious later-stage math; they never infer a grade for unlabelled data.
func bankLaterMath(grade: String): String {
    let college="微积分|不定积分|定积分|微分方程|偏导数|拉普拉斯|傅里叶|泰勒级数|矩阵|行列式|特征值"
    if (grade.startsWith("初")) {
        let senior=college+"|复数|虚数|共轭|导数|求导|向量|数列|对数|指数函数|椭圆|双曲线|圆锥曲线|排列组合|二项式定理|数学归纳|充分条件|必要条件|奇函数|偶函数|等差|等比|正态分布|随机变量|(^|[^a-zA-Z])(log|ln)([^a-zA-Z]|$)"
        if (grade=="初一" || grade=="初二") {
            let later=senior+"|二次函数|一元二次|反比例函数|三角函数|正弦|余弦|正切|圆周角|圆心角|相似三角形|(^|[^a-zA-Z])(sin|cos|tan)([^a-zA-Z]|$)"
            return if (grade=="初一") { later+"|勾股|全等|二次根式|分式|一次函数|因式分解|完全平方|平方差" } else { later }
        }
        return senior
    }
    return college
}

func bankFilter(subject: String, band: String, source: String, search: String, grade!: String): Array<Option<String>> {
    let params=ArrayList<Option<String>>([Some(subject),Some(subject),Some(band),Some(band),Some(source),Some(source),Some(search),Some("%"+search+"%")])
    if (!grade.startsWith("高")) { params.add(Some(grade)); params.add(Some(bankGradeAlias(grade))); params.add(Some(bankLaterMath(grade))) }
    return params.toArray()
}
let bankWhere=" FROM dataset_questions q WHERE q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND q.has_answer=1 AND (?='' OR q.subject=?) AND (?='' OR q.grade_band=?) AND (?='' OR q.dataset_source_id=?) AND (?='' OR q.question_text LIKE ?)"
func bankScopedWhere(grade: String): String {
    if (grade.startsWith("高")) { return bankWhere.replace("q WHERE","q USE INDEX (ix_bank_browse) WHERE")+" AND q.grade_band='高中'" }
    return bankWhere.replace("q WHERE","q USE INDEX (ix_bank_grade) WHERE")+" AND q.grade IN (?,?) AND (q.subject<>'数学' OR CONCAT(q.question_text,' ',COALESCE(q.options,''),' ',COALESCE(q.knowledge_points,'')) NOT REGEXP ?)"
}

func studyBank(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let form=insightQuery(context)
    let subject=queryLast(form,"subject"); let band=queryLast(form,"grade_band"); let source=queryLast(form,"source_id"); let search=queryLast(form,"search")
    if (subject.size>100 || band.size>100 || source.size>100 || search.size>300) { throw ApiError(422,"筛选条件过长") }
    let page=if (queryLast(form,"page").isEmpty()) { 1 } else { try { Int64.parse(queryLast(form,"page")) } catch (_: Exception) { throw ApiError(422,"页码无效") } }
    if (page<1 || page>10000) { throw ApiError(422,"页码无效") }
    let seed=if (queryLast(form,"shuffle_seed").isEmpty()) { unixNow()%2147483647 } else { try { Int64.parse(queryLast(form,"shuffle_seed")) } catch (_: Exception) { throw ApiError(422,"随机顺序参数无效") } }
    if (seed<0 || seed>2147483647) { throw ApiError(422,"随机顺序参数无效") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        let grade=bankStudentGrade(db,rowText(user,"id"))
        let filters=bankFilter(subject,band,source,search,grade:grade)
        let browseWhere=bankScopedWhere(grade)
        let result=JsonObject(); result.put("page",JsonInt(page)); result.put("page_size",JsonInt(20)); result.put("grade",JsonString(grade)); result.put("scope_label",JsonString(if (grade.startsWith("高")) { "高中" } else { grade }))
        let items=JsonArray()
        let sourceNames=JsonObject()
        for (sourceRow in db.query("SELECT id,name FROM dataset_sources").rows) {
            sourceNames.put(rowText(sourceRow,"id"),JsonString(rowText(sourceRow,"name")))
        }
        let paging=" LIMIT 20 OFFSET "+((page-1)*20).toString()
        // Shuffle IDs, interleaving subjects so large English datasets cannot monopolize "all".
        // The seeded per-ID key stays stable across pages and query execution plans.
        let randomKey="CRC32(CONCAT(q.id,':',"+seed.toString()+"))"
        let listing=if (subject.isEmpty()) {
            "SELECT q.* FROM dataset_questions q JOIN (SELECT id,subject_rank,random_key FROM (SELECT q.id,ROW_NUMBER() OVER (PARTITION BY q.subject ORDER BY "+randomKey+",q.id) AS subject_rank,"+randomKey+" AS random_key"+browseWhere+") mixed ORDER BY subject_rank,random_key,id"+paging+") selected ON selected.id=q.id ORDER BY selected.subject_rank,selected.random_key,selected.id"
        } else { "SELECT q.*"+browseWhere+(if (grade.startsWith("高")) { " ORDER BY q.subject,q.id" } else { " ORDER BY q.grade,q.subject,q.id" })+paging }
        result.put("shuffle_seed",JsonInt(seed))
        for (row in db.query(listing,filters).rows) {
            let value=rowJson("dataset_questions",row)
            value.put("source_name",sourceNames.get(rowText(row,"dataset_source_id")) ?? JsonString("题库")); items.add(bankQuestion(value,accounts))
        }
        result.put("questions",items)
        // One eligibility scan supplies facets, sources and the unsearched count.
        let facetCounts=HashMap<String,JsonObject>(); let sourceCounts=HashMap<String,Int64>()
        var total: Int64=0
        for (row in db.query("SELECT q.subject,q.grade_band,q.dataset_source_id,COUNT(*) AS total"+browseWhere+" GROUP BY q.subject,q.grade_band,q.dataset_source_id",bankFilter("","","","",grade:grade)).rows) {
            let rowSubject=rowText(row,"subject"); let rowBand=rowText(row,"grade_band"); let rowSource=rowText(row,"dataset_source_id")
            let amount=Int64.parse(rowText(row,"total")); let key=rowSubject+"|"+rowBand
            let item=facetCounts.get(key) ?? JsonObject()
            item.put("subject",JsonString(rowSubject)); item.put("grade_band",JsonString(rowBand)); item.put("count",JsonInt(tutorNumber(item,"count")+amount)); facetCounts[key]=item
            sourceCounts[rowSource]=(sourceCounts.get(rowSource) ?? 0)+amount
            if ((subject.isEmpty() || subject==rowSubject) && (band.isEmpty() || band==rowBand) && (source.isEmpty() || source==rowSource)) { total+=amount }
        }
        if (!search.isEmpty()) { total=Int64.parse(rowText(db.query("SELECT COUNT(*) AS total"+browseWhere,filters).rows[0],"total")) }
        result.put("total",JsonInt(total))
        let facets=JsonArray(); for ((_,item) in facetCounts) { facets.add(item) }; result.put("facets",facets)
        let sources=JsonArray()
        for ((id,amount) in sourceCounts) {
            let item=JsonObject(); item.put("id",JsonString(id)); item.put("name",sourceNames.get(id) ?? JsonString("题库")); item.put("count",JsonInt(amount)); sources.add(item)
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
            let added=db.query("SELECT id FROM questions WHERE user_id=? AND status<>'archived' AND JSON_CONTAINS(tags,JSON_QUOTE(?)) LIMIT 1",[sqlValue(value["user_id"]),Some("study-item:"+jsonText(item,"id"))]).rows
            publicItem.put("mistake_id",if (added.isEmpty()) { JsonNull() } else { JsonString(rowText(added[0],"id")) })
            publicItem.put("grading",item["grading"])
            if (available) {
                publicItem.put("answer",snapshot["answer"]); publicItem.put("solution",snapshot["solution"])
                for ((key,value) in datasetSolutionImages(snapshot,accounts).getFields()) { publicItem.put(key,value) }
            }
        }
        items.add(publicItem)
    }
    value.put("items",items); value.put("question_count",JsonInt(items.getItems().size)); return value
}

func studyQuestionAvailable(db: Database, snapshot: JsonObject, lock!: Bool=false): Bool {
    if (tutorFlag(datasetImageLayout(snapshot),"review")) { return false }
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
        let grade=bankStudentGrade(db,owner)
        let body=readJson(context); let mode=optionalText(body,"mode","practice",20)
        if (mode!="practice" && mode!="exam") { throw ApiError(422,"请选择练习或模拟考试") }
        let subject=optionalText(body,"subject","",30); let band=optionalText(body,"grade_band","",30); let source=optionalText(body,"source_id","",36)
        let search=optionalText(body,"search","",300)
        let count=studyInteger(body.get("count") ?? JsonInt(5),1,20); let minutes=studyInteger(body.get("minutes") ?? JsonInt(15),1,180)
        let rawIds=body.get("question_ids") ?? JsonArray()
        if (!(rawIds is JsonArray)) { throw ApiError(422,"题目编号格式无效") }
        let ids=(rawIds as JsonArray).getOrThrow()
        if (ids.getItems().size>1) { throw ApiError(422,"单题练习请选择一道题") }
        let strategy=optionalText(body,"selection_strategy","random",20)
        if (strategy!="random" && strategy!="adaptive") { throw ApiError(422,"选题方式无效") }
        let selection=if (strategy=="adaptive" && mode=="practice" && ids.getItems().isEmpty()) { adaptivePracticeSelection(db,owner,subject,band,source,search,count,grade:grade) } else { JsonObject() }
        let selected=tutorArray(selection,"question_ids")
        let taskId=optionalText(body,"learning_task_id","",36)
        if (!taskId.isEmpty() && (mode!="practice" || ids.getItems().size!=1)) { throw ApiError(422,"请选择本次学习推荐的一道题") }
        return db.transaction<JsonValue>({ tx =>
            let rows=if (!taskId.isEmpty()) {
                // Old mistakes keep their original learning context after the student advances a grade.
                let task=taskRow(tx,taskId,owner)
                let plan=tutorObject(tutorObject(task,"student_view"),"recommendation")
                let requested=(editText(ids.getItems()[0],36,minimum:1,trim:true) as JsonString).getOrThrow().getValue()
                if (tutorText(task,"status")!="completed" || tutorText(plan,"question_source")!="dataset" || tutorText(plan,"question_id")!=requested) { throw ApiError(409,"请从已完成的学习任务打开推荐题") }
                let snapshot=taskSnapshot(tx,tutorText(task,"question_id"),owner)
                if (!taskValidateVersion(tx,task,snapshot)) { throw ApiError(409,"原题已更新，请重新学习后获取推荐") }
                let candidates=tx.query("SELECT * FROM dataset_questions WHERE id=?",[Some(requested)]).rows
                if (candidates.isEmpty() || !usableRetrievalCandidate(tutorObject(snapshot,"question"),rowJson("dataset_questions",candidates[0]),"practice")) { throw ApiError(409,"推荐题已更新，请重新获取练习") }
                candidates
            } else if (!selected.getItems().isEmpty()) {
                let picked=ArrayList<HashMap<String,Option<String>>>()
                for (id in selected.getItems()) {
                    let params=ArrayList<Option<String>>(bankFilter(subject,band,source,search,grade:grade)); params.add(sqlValue(id))
                    for (row in tx.query("SELECT q.*"+bankScopedWhere(grade)+" AND q.id=?",params.toArray()).rows) { picked.add(row) }
                }
                picked
            } else if (ids.getItems().isEmpty()) {
                tx.query("SELECT q.*"+bankScopedWhere(grade)+" ORDER BY RAND() LIMIT "+count.toString(),bankFilter(subject,band,source,search,grade:grade)).rows
            } else {
                let params=ArrayList<Option<String>>(bankFilter(subject,band,source,search,grade:grade))
                params.add(Some((editText(ids.getItems()[0],36,minimum:1,trim:true) as JsonString).getOrThrow().getValue()))
                tx.query("SELECT q.*"+bankScopedWhere(grade)+" AND q.id=?",params.toArray()).rows
            }
            if (rows.isEmpty() || (ids.getItems().isEmpty() && rows.size<count)) { throw ApiError(422,"当前范围可用题目不足，请减少题数或更换学科") }
            for (row in rows) {
                if (tutorFlag(datasetImageLayout(rowJson("dataset_questions",row)),"review")) { throw ApiError(422,"题图需要核对，请选择其他题目") }
            }
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
                    let answer=(rawAnswer as JsonObject).getOrThrow(); let itemId=optionalText(answer,"id","",36)
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
