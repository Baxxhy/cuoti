package zhiwei

import std.env.*
import std.convert.*
import std.collection.*
import stdx.encoding.json.*

// Resolve only server-owned snapshots. Never accept image paths supplied by a client.
func studyMistakeSource(db: Database, owner: String, body: JsonObject): JsonObject {
    let sessionId=optionalText(body,"study_session_id","",36)
    let itemId=optionalText(body,"study_item_id","",36)
    if (sessionId.isEmpty() && itemId.isEmpty()) { return JsonObject() }
    let session=ownedStudy(db,sessionId,owner)
    if (tutorText(session,"status")!="submitted") { throw ApiError(409,"请先交卷再加入错题本") }
    for (raw in studyItems(db,sessionId).getItems()) {
        let item=(raw as JsonObject).getOrThrow()
        if (tutorText(item,"id")!=itemId) { continue }
        let grading=tutorObject(item,"grading")
        let correct=grading.get("correct") ?? JsonNull()
        if (!(correct is JsonBool) || tutorFlag(grading,"correct")) { throw ApiError(422,"此题尚未判错") }
        let source=tutorObject(item,"snapshot")
        if (!studyQuestionAvailable(db,source)) { throw ApiError(409,"此题已暂停使用") }
        for (key in ["question_text","subject","grade"]) { body.put(key,source.get(key) ?? JsonNull()) }
        let options=datasetDisplayOptions(source)
        if (options.getItems().size>8) { throw ApiError(422,"选项数量超过支持范围") }
        for (i in 0..options.getItems().size) {
            let option=(options[i] as JsonObject).getOrThrow()
            let key=tutorText(option,"key")
            let explicit=tutorText(option,"label")
            let label=if (!explicit.isEmpty()) { explicit } else if (!key.isEmpty()) { key } else { ["A","B","C","D","E","F","G","H"][i] }
            option.put("label",JsonString(label))
            if (tutorText(option,"text").isEmpty()) { option.put("text",JsonString("见选项${label}配图")) }
        }
        body.put("options",options)
        let kind=tutorText(source,"question_type")
        let multiple=kind.contains("多") || ["multiple_choice","multiple-response","multiple_response","multi_choice","multi-select"].contains(kind)
        body.put("question_type",JsonString(if (options.getItems().isEmpty()) { "综合题" } else if (multiple) { "多选题" } else { "单选题" }))
        body.put("student_answer",JsonString(tutorAnswerText(item["student_answer"])))
        body.put("student_steps",JsonArray())
        return source
    }
    throw ApiError(404,"没有找到这道练习题")
}

func copyStudyFigures(db: Database, id: String, source: JsonObject, copied: ArrayList<String>): Unit {
    let paths=tutorArray(source,"image_paths")
    let layout=datasetImageLayout(source)
    let indices=tutorArray(layout,"stem")
    for (raw in tutorArray(layout,"options").getItems()) {
        for (index in (raw as JsonArray).getOrThrow().getItems()) { indices.add(index) }
    }
    let working=getWorkingDirectory().toString()
    let project=if (working.endsWith("/backend-cangjie")) { working[..working.size-16] } else { working }
    let configured=getVariable("CANGJIE_QUESTION_BANK_ROOT") ?? "data/question_bank_assets"
    let root=if (configured.startsWith("/")) { configured } else { project+"/"+configured }
    for (index in indices.getItems()) {
        let stored=(paths[Int64.parse(index.toString())] as JsonString).getOrThrow().getValue()
        let absolute=if (stored.startsWith("/")) { stored } else { project+"/"+stored }
        if (!absolute.startsWith(root+"/")) { throw ApiError(422,"题库配图路径无效") }
        try (file=MediaFile(root,absolute[root.size+1..])) {
            if (file.length<=0 || file.length>64*1024*1024) { throw ApiError(422,"题库配图大小无效") }
            let bytes=Array<UInt8>(file.length,repeat:0)
            var offset: Int64=0
            while (offset<bytes.size) {
                let amount=file.readAt(bytes[offset..],offset)
                if (amount<=0) { throw ApiError(503,"题库配图读取失败") }; offset+=amount
            }
            let path="uploads/${id}/bank-${index.toString()}."+uploadedImageSuffix(bytes)
            writeMedia(path,bytes)
            copied.add(path)
            db.query("INSERT INTO question_assets (id,question_id,kind,path,sha256,bbox,description,created_at,updated_at) VALUES (?,?,'question_figure',?,?,JSON_ARRAY(),'题库配图',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(id),Some(path),Some(sha256(bytes))])
        }
    }
}
