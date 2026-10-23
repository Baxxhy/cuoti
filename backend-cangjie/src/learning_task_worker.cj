package zhiwei

import stdx.encoding.json.*

func taskLeaseValid(task: JsonObject, lease: String): Bool {
    return tutorText(task,"status")=="running" && tutorText(task,"lease_token")==lease && !tutorFlag(task,"cancel_requested")
}

func taskPreparationFailure(db: Database, task: JsonObject, reason: String): Unit {
    let view=taskStoppedView("暂时未能准备题目，内容已保留，可以重试")
    let actions=JsonArray(); actions.add(JsonString("resume")); view.put("secondary_actions",actions)
    let photo=tutorObject(tutorObject(task,"student_view"),"handwriting")
    if (!photo.getFields().isEmpty()) { view.put("handwriting",photo) }
    db.query("UPDATE learning_tasks SET status='failed',version=version+1,student_view=?,exit_reason=?,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(view.toString()),Some(reason),sqlValue(task["id"])])
    db.query("UPDATE learning_task_actions SET status='failed',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",[sqlValue(task["id"])])
}

func claimLearningTask(id: String, budget: TaskBudget): Option<JsonObject> {
    try (db=Database.fromEnvironment()) {
        let rows=db.query("SELECT user_id,question_id FROM learning_tasks WHERE id=?",[Some(id)]).rows
        if (rows.isEmpty()) { return None }
        let owner=rowText(rows[0],"user_id"); let questionId=rowText(rows[0],"question_id")
        return db.transaction<Option<JsonObject>>({ tx =>
            let snapshot=taskSnapshot(tx,questionId,owner); let task=taskRow(tx,id,owner,lock:true)
            let claimable=tx.query("SELECT id FROM learning_tasks WHERE id=? AND cancel_requested=0 AND (status='queued' OR (status='running' AND lease_until<UTC_TIMESTAMP(6)))",[Some(id)]).rows
            if (claimable.isEmpty() || !taskValidateVersion(tx,task,snapshot)) { return None }
            if (taskAtLimit(task)) { stopTaskAtLimit(tx,task,if (tutorNumber(task,"run_count")>=72) { "retry_budget" } else { "round_budget" }); return None }
            tx.query("UPDATE learning_tasks SET run_count=run_count+1 WHERE id=?",[Some(id)])
            let lease=newId()
            var source=JsonObject()
            try { source=taskSource(tx,task,snapshot) }
            catch (error: TaskSourceError) {
                tx.query("UPDATE learning_tasks SET status='failed',version=version+1,student_view=?,exit_reason=?,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(taskStoppedView("任务来源无法核对，请结束本次学习后回原题重开；旧记录仍保留").toString()),Some(error.reason),Some(id)])
                tx.query("UPDATE learning_task_actions SET status='failed',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",[Some(id)])
                return None
            }
            var domain=JsonObject()
            try {
                domain=taskContext(tx,source,owner); domain.put("source_snapshot_id",task["id"])
                domain.put("action_id",JsonString(id+":"+tutorText(task,"active_request")))
            } catch (error: DatabaseException) {
                taskPreparationFailure(tx,task,"prepare_database_"+error.code.toString()); return None
            } catch (_: Exception) {
                taskPreparationFailure(tx,task,"prepare_context_invalid"); return None
            }
            try { budget.check("prepare") } catch (_: TaskBudgetExceeded) {
                stopTaskAtLimit(tx,task,"prepare_budget"); return None
            }
            tx.query("UPDATE learning_tasks SET status='running',lease_token=?,lease_until=UTC_TIMESTAMP(6)+INTERVAL 90 SECOND,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(lease),Some(id)])
            let result=JsonObject(); result.put("task",task); result.put("context",domain); result.put("lease",JsonString(lease)); return Some(result)
        })
    }
    return None
}

func taskFailure(id: String, owner: String, questionId: String, lease: String, reason!: String="computation_unavailable"): Unit {
    try (db=Database.fromEnvironment()) {
        db.transaction<Unit>({ tx =>
            let snapshot=taskSnapshot(tx,questionId,owner); let task=taskRow(tx,id,owner,lock:true)
            if (!taskLeaseValid(task,lease) || !taskValidateVersion(tx,task,snapshot)) { return }
            let view=taskStoppedView("这次没能核对完成，内容已保留，可以稍后继续")
            let photo=tutorObject(tutorObject(task,"student_view"),"handwriting")
            if (!photo.getFields().isEmpty()) { view.put("handwriting",photo) }
            let actions=JsonArray(); actions.add(JsonString("resume")); if (tutorText(tutorObject(task,"pending_action"),"kind")=="recognize_handwriting") { actions.add(JsonString("use_text")) }; view.put("secondary_actions",actions)
            tx.query("UPDATE learning_tasks SET status='failed',version=version+1,student_view=?,lease_token=NULL,lease_until=NULL,exit_reason=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(view.toString()),Some(reason),Some(id)])
            tx.query("UPDATE learning_task_actions SET status='failed',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND request_id=? AND status='pending'",[Some(id),sqlValue(task["active_request"])])
            ()
        })
    } catch (_: Exception) { /* No upstream or database credentials enter logs. Lease expiry permits recovery. */ }
}

func saveLearningTaskResult(db: Database, task: JsonObject, result: JsonObject, budget: TaskBudget, memory: JsonObject, domain: JsonObject): Unit {
    let id=jsonText(task,"id"); let owner=jsonText(task,"user_id"); let requestId=jsonText(task,"active_request"); let traces=tutorArray(result,"traces").getItems()
    if (traces.size>3 || !["waiting_student","needs_review","completed"].contains(jsonText(result,"status"))) { throw ApiError(503,"学习任务结果格式不正确") }
    validateTaskRecommendation(result,domain)
    let manifest=JsonArray(); let validRefs=JsonArray()
    for (raw in tutorArray(memory,"entries").getItems()) {
        let entry=(raw as JsonObject).getOrThrow(); let item=JsonObject()
        for (key in ["ref","version","classification","observed_at","expires_at","question_id","source_refs"]) { item.put(key,entry[key]) }
        manifest.add(item); validRefs.add(entry["ref"])
    }
    for (raw in traces) {
        let trace=(raw as JsonObject).getOrThrow()
        for (ref in tutorArray(trace,"memory_refs").getItems()) {
            var found=false
            for (valid in validRefs.getItems()) { if (jsonEquivalent(ref,valid)) { found=true } }
            if (!found) { throw ApiError(503,"学习规划引用了无效记忆") }
        }
    }
    let boundAttempt=result.get("attempt") ?? JsonNull()
    if (boundAttempt is JsonObject) {
        let answer=(boundAttempt as JsonObject).getOrThrow(); let source=taskAttemptSource(db,task,tutorText(answer,"phase"))
        answer.put("source",source)
        for (raw in traces) {
            let trace=(raw as JsonObject).getOrThrow()
            if (["check_step","grade_answer"].contains(tutorText(trace,"tool_name"))) { let evidence=tutorObject(trace,"evidence"); evidence.put("source",source); trace.put("evidence",evidence) }
        }
    }
    for (index in 0..traces.size) {
        let trace=(traces[index] as JsonObject).getOrThrow(); let tool=jsonText(trace,"tool_name"); let validation=jsonText(trace,"validation")
        if (!["check_step","grade_answer","knowledge_search","step_alignment","compare_variant","recognize_handwriting","inspect_figure","visualization"].contains(tool) || !["verified","rejected","needs_review","not_applicable"].contains(validation)) { throw ApiError(503,"学习任务工具结果不正确") }
        let runId=newId(); let run=JsonObject(); run.put("task_id",JsonString(id)); run.put("request_id",JsonString(requestId)); run.put("trace",trace)
        run.put("native_elapsed_ms",JsonInt(budget.elapsedMs())); run.put("elapsed_ms",result["elapsed_ms"]); run.put("usage",result["usage"]); run.put("memory_rule",JsonString("learning-memory-v1")); run.put("memory_manifest",manifest)
        db.query("INSERT INTO agent_runs (id,session_id,agent_name,status,result,created_at,updated_at) VALUES (?,?,'learning_task','completed',?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(runId),sqlValue(task["session_id"]),Some(run.toString())])
        let input=JsonObject(); input.put("task_id",JsonString(id)); input.put("request_id",JsonString(requestId)); input.put("student_action",task["pending_action"])
        db.query("INSERT INTO agent_tool_calls (id,agent_run_id,tool_name,input_json,output_json,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(newId()),Some(runId),Some(tool),Some(input.toString()),Some(trace.toString())])
        db.query("INSERT INTO learning_task_steps (id,task_id,request_id,step_no,plan_version,tool_name,validation,agent_run_id,trace,created_at) VALUES (?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(6))",[Some(newId()),Some(id),Some(requestId),Some(index.toString()),Some((tutorNumber(task,"version")*3+index).toString()),Some(tool),Some(validation),Some(runId),Some(trace.toString())])
    }
    let attempt=result.get("attempt") ?? JsonNull(); let state=tutorObject(result,"checkpoint")
    var eligible=tutorFlag(result,"learning_eligible") && !tutorFlag(task,"learning_applied") && jsonText(result,"status")=="completed"
    let contrast=tutorText(tutorObject(state,"contrast"),"question")
    if (!contrast.isEmpty() && (tutorFlag(state,"contrast_passed") || tutorFlag(tutorObject(state,"assistance"),"contrast"))) {
        let subject=db.query("SELECT subject FROM questions WHERE id=?",[sqlValue(task["question_id"])]).rows
        let contrastHash=sha256((rowText(subject[0],"subject")+"|"+contrast).toArray())
        // A unique claim also serializes equal contrasts in different notebook entries.
        // It commits with the result/evidence; a rollback must release the claim too.
        db.query("INSERT IGNORE INTO learning_task_exposures (user_id,contrast_hash,task_id,created_at) VALUES (?,?,?,UTC_TIMESTAMP(6))",[Some(owner),Some(contrastHash),Some(id)])
        let exposure=db.query("SELECT task_id FROM learning_task_exposures WHERE user_id=? AND contrast_hash=? FOR UPDATE",[Some(owner),Some(contrastHash)]).rows
        if (exposure.isEmpty() || rowText(exposure[0],"task_id")!=id) { eligible=false }
    }
    if (eligible && !db.query("SELECT t.id FROM learning_tasks t JOIN questions q ON q.id=t.question_id WHERE t.user_id=? AND q.subject=(SELECT subject FROM questions WHERE id=?) AND JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast.question'))=? AND (JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast_passed'))='true' OR JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.assistance.contrast'))='true') LIMIT 1",[Some(owner),sqlValue(task["question_id"]),sqlValue(tutorObject(state,"contrast")["question"])]).rows.isEmpty()) { eligible=false }
    if (eligible) {
        if (tutorText(tutorObject(task,"pending_action"),"kind")!="answer") { throw ApiError(503,"缺少学生确认的实际作答") }
        if (!(attempt is JsonObject)) { throw ApiError(503,"缺少学习证据") }
        let answer=(attempt as JsonObject).getOrThrow(); let grading=tutorObject(answer,"grading")
        if (jsonText(answer,"phase")!="contrast" || jsonText(answer,"verdict")!="confirmed_correct" || tutorFlag(answer,"assisted") || !tutorFlag(grading,"can_update_learning") || !tutorFlag(state,"contrast_passed")) { throw ApiError(503,"学习证据未达到更新条件") }
        let question=rowJson("questions",db.query("SELECT * FROM questions WHERE id=? AND user_id=?",[sqlValue(task["question_id"]),Some(owner)]).rows[0])
        let evidence=JsonObject(); evidence.put("near_transfer",JsonBool(true)); evidence.put("hint_level",JsonInt(0)); evidence.put("strategy",JsonString("verified_condition_contrast")); evidence.put("learning_task_id",JsonString(id)); evidence.put("action_request_id",JsonString(requestId))
        if (tutorText(state,"workflow_version")!="langgraph-learning-v1") {
            budget.check("before_learning"); applyLearningEvidence(db,owner,question,evidence,computeTimeoutSeconds:budget.timeoutSeconds(5,reserveSeconds:1)); budget.check("after_learning")
        }
        // A single contrast is near-transfer evidence, never a claim of full mastery.
        if (db.query("SELECT id FROM review_plans WHERE user_id=? AND question_id=? AND status='pending' LIMIT 1",[Some(owner),sqlValue(task["question_id"])]).rows.isEmpty()) {
            db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP()+INTERVAL 3 DAY,3,'单条件对照已独立完成，稍后再确认稳定性','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(owner),sqlValue(task["question_id"])])
        }
    }
    applyTaskAemt(db,task,result,budget,eligible)
    if (requestId!="__initial__") {
        db.query("UPDATE learning_task_actions SET result=?,status='applied',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND request_id=? AND status='pending'",[Some(result.toString()),Some(id),Some(requestId)])
    }
    budget.check("before_checkpoint")
    let nextStep=newId(); let view=tutorObject(result,"student_view"); saveTaskImageResult(db,task,view,nextStep); retainTaskImageForSupport(db,task,result,view,nextStep)
    db.query("UPDATE learning_tasks SET status=?,version=version+1,step_id=?,checkpoint=?,student_view=?,learning_applied=?,lease_token=NULL,lease_until=NULL,exit_reason=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[sqlValue(result["status"]),Some(nextStep),Some(state.toString()),Some(view.toString()),Some(if (eligible || tutorFlag(task,"learning_applied")) { "1" } else { "0" }),sqlValue(result["exit_reason"]),Some(id)])
    budget.check("after_checkpoint")
    db.query("UPDATE agent_runs r JOIN learning_task_steps s ON s.agent_run_id=r.id SET r.result=JSON_SET(r.result,'$.native_elapsed_ms',CAST(? AS UNSIGNED)) WHERE s.task_id=? AND s.request_id=?",[Some(budget.elapsedMs().toString()),Some(id),Some(requestId)])
    budget.check("after_audit")
}

func runLearningTask(id: String): Unit {
    var owner=""; var questionId=""; var lease=""; var stage="claim"
    let budget=TaskBudget()
    try {
        let claimed=claimLearningTask(id,budget)
        if (claimed.isNone()) { return }
        let prepared=claimed.getOrThrow(); let before=tutorObject(prepared,"task"); owner=jsonText(before,"user_id"); questionId=jsonText(before,"question_id"); lease=jsonText(prepared,"lease")
        budget.check("claimed"); stage="image_input"
        let input=JsonObject(); input.put("operation",JsonString("learning_task")); input.put("task_context",prepared["context"]); input.put("task_checkpoint",before["checkpoint"]); input.put("task_action",taskImageComputeAction(before))
        stage="compute"
        let computeSeconds=budget.timeoutSeconds(40,reserveSeconds:5)
        if (computeSeconds<2) { throw TaskBudgetExceeded("compute_reserve") }
        input.put("task_budget_ms",JsonInt(if (computeSeconds>38) { 38000 } else { (computeSeconds-1)*1000 }))
        let result=algorithmCompute(input,timeoutSeconds:computeSeconds,taskBudget:Some(budget))
        budget.check("computed")
        stage="commit"
        let stableOwner=owner; let stableQuestion=questionId; let stableLease=lease
        try (db=Database.fromEnvironment()) {
            db.transaction<Unit>({ tx =>
                let snapshot=taskSnapshot(tx,stableQuestion,stableOwner); let current=taskRow(tx,id,stableOwner,lock:true)
                if (!taskLeaseValid(current,stableLease) || !taskValidateVersion(tx,current,snapshot)) { return }
                let domain=taskContext(tx,taskSource(tx,current,snapshot),stableOwner); domain.put("source_snapshot_id",current["id"])
                domain.put("action_id",JsonString(id+":"+tutorText(current,"active_request")))
                if (!jsonEquivalent(prepared["context"],domain)) { throw ApiError(409,"学习依据已更新，需要重新核对") }
                budget.check("validated")
                saveLearningTaskResult(tx,current,result,budget,tutorObject(domain,"memory_snapshot"),domain); budget.check("before_commit"); ()
            })
        }
    } catch (error: TaskBudgetExceeded) { if (!lease.isEmpty()) { taskFailure(id,owner,questionId,lease,reason:"budget_"+error.stage) } }
    catch (error: DatabaseException) { if (!lease.isEmpty()) { taskFailure(id,owner,questionId,lease,reason:stage+"_database_"+error.code.toString()) } }
    catch (error: ApiError) { if (!lease.isEmpty()) { taskFailure(id,owner,questionId,lease,reason:stage+"_api_"+error.status.toString()) } }
    catch (_: Exception) { if (!lease.isEmpty()) { taskFailure(id,owner,questionId,lease,reason:stage+"_runtime") } }
}

public func learningTaskWorker(): Unit {
    while (true) {
        try (db=Database.fromEnvironment()) {
            let rows=db.query("SELECT id FROM learning_tasks WHERE cancel_requested=0 AND (status='queued' OR (status='running' AND lease_until<UTC_TIMESTAMP(6))) ORDER BY created_at,id LIMIT 1").rows
            if (!rows.isEmpty()) { runLearningTask(rowText(rows[0],"id")) }
            else { sleep(Duration.second) }
        } catch (_: Exception) { sleep(Duration.second * 2) }
    }
}
