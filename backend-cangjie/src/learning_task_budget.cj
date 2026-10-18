package zhiwei

import std.time.*
import stdx.encoding.json.*

class TaskBudgetExceeded <: Exception {
    let stage: String
    init(stage: String) { super("本次执行已到时限，结果未提交"); this.stage=stage }
}

public class TaskBudget {
    let started: MonoTime
    let limit: Duration
    init(started!: MonoTime=MonoTime.now(), limit!: Duration=Duration.second*45) {
        this.started=started; this.limit=limit
    }
    func elapsedMs(): Int64 { return (MonoTime.now()-started).toNanoseconds()/1000000 }
    func remaining(): Duration { return limit-(MonoTime.now()-started) }
    func check(stage: String): Unit { if (remaining()<=Duration.Zero) { throw TaskBudgetExceeded(stage) } }
    func timeoutSeconds(cap: Int64, reserveSeconds!: Int64=0): Int64 {
        let seconds=remaining().toSeconds()-reserveSeconds
        // A zero network timeout can mean unlimited; never pass it onward.
        if (seconds<1) { throw TaskBudgetExceeded("remaining_budget") }
        return if (seconds<cap) { seconds } else { cap }
    }
}

func taskAtLimit(task: JsonObject): Bool {
    return tutorNumber(task,"run_count")>=72 || tutorNumber(tutorObject(task,"checkpoint"),"rounds")>=24
}

func taskLimitView(): JsonObject {
    let view=taskStoppedView("已到本次学习上限。结束后可从原题重开，记录会保留。")
    view.put("title",JsonString("本次先停在这里")); return view
}

func stopTaskAtLimit(db: Database, task: JsonObject, reason: String): Unit {
    let recoverable=reason=="prepare_budget"
    let view=if (recoverable) { taskStoppedView("准备耗时较长，内容已保留，可以稍后继续") } else { taskLimitView() }
    if (recoverable) {
        let actions=JsonArray(); actions.add(JsonString("resume")); view.put("secondary_actions",actions)
        let photo=tutorObject(tutorObject(task,"student_view"),"handwriting")
        if (!photo.getFields().isEmpty()) { view.put("handwriting",photo) }
    }
    db.query("UPDATE learning_tasks SET status='failed',version=version+1,student_view=?,exit_reason=?,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[Some(view.toString()),Some(reason),sqlValue(task["id"])])
    db.query("UPDATE learning_task_actions SET status='failed',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",[sqlValue(task["id"])])
}
