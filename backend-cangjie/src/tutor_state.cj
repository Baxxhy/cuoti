package zhiwei

// The business state belongs to the Cangjie backend. Model-generated text
// cannot bypass the evidence gate or invent a transition.
public func canonicalTutorStage(stage: String): String {
    match (stage.trimAscii()) {
        case "teach_back" | "teach_back_retry" => "teach_back"
        case "near_transfer" | "near_remediation" => "near_transfer"
        case "far_transfer" | "transfer_insufficient" => "far_transfer"
        case "finished" => "finished"
        case _ => "understanding"
    }
}

public func transitionTutorStage(current: String, event: String, understandingPassed: Bool): String {
    let stage = canonicalTutorStage(current)
    if (event == "understanding_advance") {
        if (stage != "understanding") {
            throw IllegalArgumentException("当前不在理解阶段")
        }
        if (!understandingPassed) {
            throw IllegalArgumentException("需要先通过理解检查")
        }
        return "teach_back"
    }
    match ((stage, event)) {
        case ("teach_back", "teach_back_pass") => "near_transfer"
        case ("teach_back", "teach_back_fail") => "teach_back"
        case ("near_transfer", "near_pass") => "far_transfer"
        case ("near_transfer", "near_fail") => "near_transfer"
        case ("far_transfer", "far_pass") => "finished"
        case ("far_transfer", "far_fail") => "far_transfer"
        case _ => throw IllegalArgumentException("阶段 ${stage} 不能执行事件 ${event}")
    }
}

public func previousTutorStage(current: String): String {
    let stage = canonicalTutorStage(current)
    match (stage) {
        case "teach_back" => "understanding"
        case "near_transfer" => "teach_back"
        case "far_transfer" => "near_transfer"
        case _ => throw IllegalArgumentException("阶段 ${stage} 不能返回上一步")
    }
}
