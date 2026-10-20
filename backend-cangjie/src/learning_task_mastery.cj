package zhiwei

import std.convert.*
import stdx.encoding.json.*

// Reuse the locked task transaction and existing cognitive_updates ledger.
// Python never selects the owner, source question or the authoritative prior.
func applyTaskAemt(db: Database, task: JsonObject, result: JsonObject, budget: TaskBudget, transferEligible: Bool): Unit {
    let state=tutorObject(result,"checkpoint")
    if (tutorText(state,"workflow_version")!="langgraph-learning-v1") { return }
    let attempt=tutorObject(result,"attempt"); let grading=tutorObject(attempt,"grading")
    let phase=tutorText(attempt,"phase"); let verdict=tutorText(attempt,"verdict")
    if (!["independent","contrast"].contains(phase) || !["confirmed_correct","confirmed_incorrect"].contains(verdict) || !tutorFlag(grading,"can_update_learning")) { return }
    if (phase=="contrast" && verdict=="confirmed_correct" && !transferEligible && !tutorFlag(attempt,"assisted")) { return }
    let action=tutorObject(task,"pending_action")
    if (tutorText(action,"kind")!="answer" || tutorText(attempt,"answer")!=tutorText(action,"text")) { throw ApiError(503,"作答证据与提交不一致") }
    if (tutorText(tutorObject(task,"checkpoint"),"phase")!=phase || tutorText(grading,"verdict")!=verdict || tutorFlag(grading,"correct")!=(verdict=="confirmed_correct")) { throw ApiError(503,"作答核验与当前步骤不一致") }
    let owner=tutorText(task,"user_id"); let questionId=tutorText(task,"question_id"); let requestId=tutorText(task,"active_request"); let taskId=tutorText(task,"id")
    if (!db.query("SELECT id FROM cognitive_updates WHERE user_id=? AND question_id=? AND entity_type='mastery' AND JSON_UNQUOTE(JSON_EXTRACT(evidence,'$.learning_task_id'))=? AND JSON_UNQUOTE(JSON_EXTRACT(evidence,'$.action_request_id'))=? LIMIT 1",[Some(owner),Some(questionId),Some(taskId),Some(requestId)]).rows.isEmpty()) { return }
    let rows=db.query("SELECT * FROM questions WHERE id=? AND user_id=?",[Some(questionId),Some(owner)]).rows
    if (rows.isEmpty()) { throw ApiError(409,"题目来源已变化") }
    let question=rowJson("questions",rows[0]); let event=JsonObject()
    event.put("event_id",JsonString(taskId+":"+requestId)); event.put("verdict",JsonString(verdict)); event.put("scope",JsonString(if (phase=="contrast") { "contrast_question" } else { "original_question" }))
    var revealed=false
    for (value in tutorArray(state,"revealed_phases").getItems()) { if ((value as JsonString).getOrThrow().getValue()==phase) { revealed=true } }
    let hints=tutorArray(tutorObject(state,"hints"),phase).getItems(); let assisted=tutorFlag(attempt,"assisted")
    // Exposure remains in task/action history. It must not refresh the last
    // effective mastery timestamp or create an objective mastery observation.
    if (revealed || (assisted && hints.isEmpty())) { return }
    event.put("hint_used",JsonBool(assisted && !hints.isEmpty())); event.put("solution_seen",JsonBool(revealed || (assisted && hints.isEmpty())))
    event.put("student_confirmed",JsonBool(true)); event.put("source_current",JsonBool(true)); event.put("grading_reliable",JsonBool(true)); event.put("option_count",JsonInt(tutorArray(question,"options").getItems().size))
    let elapsed=db.query("SELECT GREATEST(0,COALESCE(TIMESTAMPDIFF(SECOND,last_evidence_at,UTC_TIMESTAMP()),0)) AS seconds FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? ORDER BY updated_at DESC,id DESC LIMIT 1",[Some(owner),sqlValue(question["subject"]),Some(learningKnowledgePoint(db,question))]).rows
    let days=if (elapsed.isEmpty()) { 0.0 } else { Float64.parse(rowText(elapsed[0],"seconds"))/86400.0 }
    event.put("days_since_last",JsonFloat(days)); event.put("delayed_similar",JsonBool(phase=="contrast" && !assisted && days>=1.0))
    let clock=db.query("SELECT DATE_FORMAT(UTC_TIMESTAMP(),'%Y-%m-%dT%H:%i:%sZ') AS instant").rows
    event.put("occurred_at",JsonString(rowText(clock[0],"instant")))
    let evidence=JsonObject(); evidence.put("aemt_event",event); evidence.put("learning_task_id",JsonString(taskId)); evidence.put("action_request_id",JsonString(requestId)); evidence.put("strategy",JsonString("aemt_assistance_aware")); evidence.put("hint_level",JsonInt(if (assisted) { 1 } else { 0 }))
    if (phase=="contrast" && !assisted) { evidence.put("near_transfer",JsonBool(verdict=="confirmed_correct")) }
    budget.check("before_aemt")
    applyLearningEvidence(db,owner,question,evidence,computeTimeoutSeconds:budget.timeoutSeconds(5,reserveSeconds:1))
    if (db.query("SELECT id FROM review_plans WHERE user_id=? AND question_id=? AND status='pending' LIMIT 1",[Some(owner),Some(questionId)]).rows.isEmpty()) {
        let interval=if (assisted || verdict=="confirmed_incorrect") { "1" } else { "3" }
        db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,TIMESTAMPADD(DAY,?,UTC_TIMESTAMP()),?,'根据本次作答安排复习','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(owner),Some(questionId),Some(interval),Some(interval)])
    }
    budget.check("after_aemt")
}
