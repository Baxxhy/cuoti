package zhiwei

import stdx.encoding.json.*

// Business decisions remain local; a model cannot choose which learning gates apply.
func normalizedTutorQuestionType(value: String, hasOptions: Bool): String {
    let raw = stripWhitespace(value).toAsciiLower()
    let normalized = match (raw) {
        case "单选题" | "选择题" => "choice"
        case "multiple-choice" | "多选题" => "multiple_choice"
        case "填空题" => "fill_blank"
        case "计算题" => "calculation"
        case "证明题" => "proof"
        case "主观题" => "subjective"
        case _ => raw
    }
    if (hasOptions && (normalized == "other" || normalized == "综合题" || normalized.isEmpty())) {
        return "choice"
    }
    return if (normalized.isEmpty()) { "other" } else { normalized }
}

func adaptiveTeachingPolicy(questionType: String, hasOptions: Bool, hasWorking: Bool,
    correctAnswer: String): JsonObject {
    let normalized = normalizedTutorQuestionType(questionType, hasOptions)
    let reliable = !stripWhitespace(correctAnswer).isEmpty()
    let shortQuestion = normalized == "choice" || normalized == "multiple_choice" || normalized == "fill_blank"
    let compressed = reliable && (shortQuestion || !hasWorking)
    let result = JsonObject()
    result.put("mode", JsonString(if (compressed) { "compressed" } else { "full" }))
    result.put("question_type", JsonString(normalized))
    result.put("show_answer_immediately", JsonBool(reliable))
    result.put("max_understanding_checks", JsonInt(if (compressed) { 1 } else { 3 }))
    result.put("skip_teach_back", JsonBool(compressed))
    result.put("skip_far_transfer", JsonBool(compressed))
    result.put("has_working", JsonBool(hasWorking))
    return result
}

// Persisted plans contain grading keys. Expose only progress, including when
// loading older sessions with additional internal fields.
func publicTutorProgress(state: JsonObject): JsonObject {
    let result = JsonObject()
    for (key in ["understood", "understanding_passed", "teach_back", "teach_back_passed",
        "near_transfer", "far_transfer", "next_goal", "strategy", "branch", "mastery_proven",
        "assisted", "understanding_index", "answer_reveal_acknowledged", "targeted_check_pending",
        "transfer_insufficient", "question_changed"]) {
        if (let Some(value) <- state.getFields().get(key)) { result.put(key, value) }
    }
    return result
}
