package zhiwei

import std.collection.*
import stdx.encoding.json.*

func datasetImageMarkers(text: String): Int64 {
    if (text.isEmpty()) { return 0 }
    return text.split("<ImageHere>").size-1
}

func datasetDisplayOptions(question: JsonObject): JsonArray {
    let options=JsonArray()
    for (entry in tutorArray(question,"options").getItems()) {
        let option=if (let Some(object) <- (entry as JsonObject)) {
            (JsonValue.fromStr(object.toString()) as JsonObject).getOrThrow()
        } else { let object=JsonObject(); object.put("text",JsonString(tutorAnswerText(entry))); object }
        if (option.get("text").isNone()) { option.put("text",option.get("content") ?? option.get("value") ?? JsonString("")) }
        options.add(option)
    }
    return options
}

// CMM-Math stores figures in occurrence order: stem, options, answer, solution.
// Keep the original paths/indices immutable, including in historical snapshots.
func datasetImageLayout(question: JsonObject): JsonObject {
    let paths=tutorArray(question,"image_paths"); let count=paths.getItems().size
    let stem=datasetImageMarkers(tutorText(question,"question_text"))
    let optionCounts=ArrayList<Int64>(); var publicCount=stem
    for (entry in datasetDisplayOptions(question).getItems()) {
        let option=(entry as JsonObject).getOrThrow()
        let amount=datasetImageMarkers(tutorText(option,"text"))
        optionCounts.add(amount); publicCount+=amount
    }
    let answer=datasetImageMarkers(tutorAnswerText(question.get("answer") ?? JsonNull()))
    let solution=datasetImageMarkers(tutorText(question,"solution"))
    let total=publicCount+answer+solution
    let metadata=tutorObject(question,"source_metadata")
    let importedMath=tutorFlag(metadata,"has_visual")
    let review=(total!=count && (total>0 || importedMath))
    let result=JsonObject(); result.put("review",JsonBool(review))
    let stemIndices=JsonArray(); let options=JsonArray(); let answerIndices=JsonArray(); let solutionIndices=JsonArray()
    var index: Int64=0
    // Other datasets have ordinary attached question figures and no marker syntax.
    let stemCount=if (total==0 && !importedMath) { count } else { stem }
    for (_ in 0..stemCount) { if (index<count) { stemIndices.add(JsonInt(index)) }; index++ }
    for (amount in optionCounts) {
        let indices=JsonArray()
        for (_ in 0..amount) { if (index<count) { indices.add(JsonInt(index)) }; index++ }
        options.add(indices)
    }
    for (_ in 0..answer) { if (index<count) { answerIndices.add(JsonInt(index)) }; index++ }
    for (_ in 0..solution) { if (index<count) { solutionIndices.add(JsonInt(index)) }; index++ }
    result.put("stem",stemIndices); result.put("options",options)
    result.put("answer",answerIndices); result.put("solution",solutionIndices)
    return result
}

func datasetImageUrls(question: JsonObject, indices: JsonArray, accounts: Accounts): JsonArray {
    let urls=JsonArray()
    for (index in indices.getItems()) {
        urls.add(JsonString(accounts.mediaUrl("/api/v1/practice/questions/${jsonText(question,"id")}/images/${index.toString()}")))
    }
    return urls
}

func datasetQuestionImages(question: JsonObject, accounts: Accounts): JsonObject {
    let layout=datasetImageLayout(question); let result=JsonObject()
    let images=if (tutorFlag(layout,"review")) { JsonArray() } else { datasetImageUrls(question,tutorArray(layout,"stem"),accounts) }
    let previews=(JsonValue.fromStr(images.toString()) as JsonArray).getOrThrow()
    let options=datasetDisplayOptions(question)
    let optionIndices=tutorArray(layout,"options")
    for (i in 0..options.getItems().size) {
        let option=(options[i] as JsonObject).getOrThrow()
        let urls=if (tutorFlag(layout,"review")) { JsonArray() } else { datasetImageUrls(question,(optionIndices[i] as JsonArray).getOrThrow(),accounts) }
        if (!urls.getItems().isEmpty()) { option.put("image_urls",urls) }
        for (url in urls.getItems()) { previews.add(url) }
    }
    result.put("image_urls",images); result.put("preview_image_urls",previews)
    result.put("options",options); result.put("image_layout_review",layout["review"])
    return result
}

func datasetSolutionImages(question: JsonObject, accounts: Accounts): JsonObject {
    let layout=datasetImageLayout(question); let result=JsonObject()
    result.put("answer_image_urls",datasetImageUrls(question,tutorArray(layout,"answer"),accounts))
    result.put("solution_image_urls",datasetImageUrls(question,tutorArray(layout,"solution"),accounts))
    return result
}
