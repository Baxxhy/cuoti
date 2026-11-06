package zhiwei

import stdx.encoding.json.*

func retrievalGrade(grade: String, band: String): String {
    let clean=stripWhitespace(grade)
    for ((prefix,label) in [("七年级","初一"),("八年级","初二"),("九年级","初三"),("初中","初中"),("高中","高中")]) {
        if (clean.startsWith(prefix)) { return label }
    }
    return if (clean.isEmpty()) { band } else { clean }
}

func usableRetrievalCandidate(source: JsonObject, candidate: JsonObject, kind: String): Bool {
    if (tutorFlag(datasetImageLayout(candidate),"review")) { return false }
    if (tutorText(source,"subject")!=tutorText(candidate,"subject") || !tutorFlag(candidate,"usable_for_practice") || !tutorFlag(candidate,"has_answer") || stripWhitespace(tutorAnswerText(candidate["answer"])).isEmpty()) { return false }
    if (kind=="practice" && !tutorFlag(candidate,"usable_for_auto_grade")) { return false }
    let raw=tutorText(source,"grade"); let band=if (raw.startsWith("高")) { "高中" } else { "初中" }
    let grade=retrievalGrade(tutorText(candidate,"grade"),tutorText(candidate,"grade_band"))
    return grade==retrievalGrade(raw,band) || grade==band
}

func retrievalPreparationInput(db: Database, question: JsonObject, analysis: JsonValue, kind: String, mode: String): JsonObject {
    let input=JsonObject(); input.put("operation",JsonString("retrieval_prepare")); input.put("retrieval_source",question); input.put("retrieval_analysis",analysis)
    input.put("retrieval_kind",JsonString(kind)); input.put("retrieval_mode",JsonString(mode))
    input.put("retrieval_diagnosis",firstJson(queryArray(db,"diagnoses","SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",jsonText(question,"id"))))
    // Missing diagnoses are represented by an empty snapshot, never an ORM query in Python.
    if (input["retrieval_diagnosis"] is JsonNull) { input.put("retrieval_diagnosis",JsonObject()) }
    input.put("retrieval_cards",queryArray(db,"knowledge_points","SELECT * FROM knowledge_points WHERE subject=?",jsonText(question,"subject")))
    return input
}

func retrievalPreparation(db: Database, question: JsonObject, analysis: JsonValue, kind: String, mode: String): JsonObject {
    return algorithmCompute(retrievalPreparationInput(db,question,analysis,kind,mode))
}

func retrievalCandidates(db: Database, question: JsonObject, preparation: JsonObject, excluded: JsonArray, kind: String, mode: String): JsonObject {
    let search=JsonObject(); search.put("operation",JsonString("retrieval_search")); search.put("retrieval_query",preparation["query"]); search.put("subject",question["subject"])
    let grade=tutorText(question,"grade"); search.put("grade",JsonString(grade)); search.put("grade_band",JsonString(if (grade.startsWith("高")) { "高中" } else { "初中" }))
    let hits=tutorArray(algorithmCompute(search),"hits"); let candidates=JsonArray()
    for (value in hits.getItems()) {
        let hit=(value as JsonObject).getOrThrow(); let id=jsonText(hit,"id")
        let rows=db.query("SELECT * FROM dataset_questions WHERE id=? AND subject=? AND usable_for_practice=1",[Some(id),sqlValue(question["subject"])]).rows
        if (rows.isEmpty()) { continue }
        let item=rowJson("dataset_questions",rows[0]); if (!usableRetrievalCandidate(question,item,kind)) { continue }; let candidate=JsonObject()
        for (key in ["dense_rank","sparse_rank","fusion_rank","fusion_score"]) { candidate.put(key,hit[key]) }
        candidate.put("question",item)
        let sources=db.query("SELECT `key` FROM dataset_sources WHERE id=?",[sqlValue(item["dataset_source_id"])]).rows
        candidate.put("source_dataset",JsonString(if (sources.isEmpty()) { "unknown" } else { rowText(sources[0],"key") }))
        let links=JsonArray()
        for (row in db.query("SELECT k.id,k.name,l.role FROM question_knowledge_links l JOIN knowledge_points k ON k.id=l.knowledge_point_id WHERE l.dataset_question_id=?",[Some(id)]).rows) {
            let link=JsonObject(); for (key in ["id","name","role"]) { link.put(key,JsonString(rowText(row,key))) }; links.add(link)
        }
        candidate.put("knowledge_points",links); candidates.add(candidate)
    }
    let rank=JsonObject(); rank.put("operation",JsonString("retrieval_rank")); rank.put("retrieval_query",preparation["query"]); rank.put("text",question["question_text"]); rank.put("question_type",question["question_type"])
    rank.put("retrieval_candidates",candidates); rank.put("retrieval_excluded_ids",excluded); rank.put("retrieval_kind",JsonString(kind)); rank.put("retrieval_mode",JsonString(mode))
    return algorithmCompute(rank)
}
