package zhiwei

import std.convert.*
import stdx.encoding.json.*

class TaskSourceError <: Exception {
    let reason: String
    init(reason: String) { super("任务来源校验未通过"); this.reason=reason }
}

// Insert once. Legacy tasks may only acquire a snapshot after the live source
// is revalidated; never reconstruct a stale task from today's question.
func taskSource(db: Database, task: JsonObject, current: JsonObject, origin!: String="legacy_revalidated"): JsonObject {
    let rows=db.query("SELECT * FROM learning_task_sources WHERE task_id=?",[sqlValue(task["id"])]).rows
    if (!rows.isEmpty()) {
        let row=try { rowJson("learning_task_sources",rows[0]) } catch (_: Exception) { throw TaskSourceError("source_parse") }
        let source=tutorObject(row,"source")
        if (tutorText(row,"input_fingerprint")!=tutorText(task,"input_fingerprint")) { throw TaskSourceError("source_fingerprint") }
        let old=diagnosisFingerprint(source); let fresh=diagnosisFingerprint(current)
        for (index in 0..old.getItems().size) {
            if (!taskSourceEqual(old[index],fresh[index])) { throw TaskSourceError("source_field_"+index.toString()) }
        }
        return source
    }
    if (tutorText(task,"input_fingerprint")!=taskFingerprint(current)) { throw TaskSourceError("source_legacy_stale") }
    db.query("INSERT INTO learning_task_sources (task_id,schema_version,input_fingerprint,origin,source,created_at) VALUES (?,'1.0',?,?,?,UTC_TIMESTAMP(6))",[sqlValue(task["id"]),sqlValue(task["input_fingerprint"]),Some(origin),Some(current.toString())])
    return current
}

func taskStepIds(snapshot: JsonObject, key: String): JsonArray {
    let ids=JsonArray()
    for (item in tutorArray(snapshot,key).getItems()) { ids.add((item as JsonObject).getOrThrow()["id"]) }
    return ids
}

// Public history is built from the immutable source, never from client IDs.
func taskAttemptSource(db: Database, task: JsonObject, phase: String): JsonObject {
    let result=JsonObject(); result.put("snapshot_id",task["id"]); result.put("student_step_id",JsonNull()); result.put("step_index",JsonNull()); result.put("student_step_text",JsonString(""))
    let rows=db.query("SELECT source FROM learning_task_sources WHERE task_id=?",[sqlValue(task["id"])]).rows
    if (rows.isEmpty()) { return JsonObject() }
    let source=(JsonValue.fromStr(rowText(rows[0],"source")) as JsonObject).getOrThrow()
    result.put("student_work_id",JsonString(tutorText(tutorObject(source,"work"),"id")))
    if (phase=="repair") {
        let steps=tutorArray(source,"steps").getItems()
        if (!steps.isEmpty()) {
            let assessment=tutorObject(tutorObject(task,"checkpoint"),"evidence_diagnosis")
            let first=if (tutorFlag(assessment,"verified") && assessment.get("first_error_step").isSome() && !(assessment["first_error_step"] is JsonNull)) { tutorNumber(assessment,"first_error_step") } else { tutorNumber(tutorObject(source,"diagnosis"),"first_error_step") }
            let index=if (first<0 || first>99) { 0 } else if (first>=steps.size) { steps.size-1 } else { first }
            let step=(steps[index] as JsonObject).getOrThrow()
            result.put("student_step_id",step["id"]); result.put("step_index",JsonInt(index)); result.put("student_step_text",step["text"])
        }
    }
    return result
}

func taskSourcePublic(db: Database, taskId: String): JsonValue {
    let rows=db.query("SELECT * FROM learning_task_sources WHERE task_id=?",[Some(taskId)]).rows
    if (rows.isEmpty()) { return JsonNull() }
    let record=rowJson("learning_task_sources",rows[0]); let question=tutorObject(tutorObject(record,"source"),"question"); let result=JsonObject()
    result.put("snapshot_id",JsonString(taskId)); result.put("origin",record["origin"]); result.put("captured_at",record["created_at"])
    for (key in ["subject","grade","question_text","options"]) { result.put(key,question[key]) }
    return result
}

// MySQL JSON may store 1.0 as 1. Numeric transport representation is not a
// source change; bools/strings, object keys and array order remain distinct.
func taskSourceEqual(left: JsonValue, right: JsonValue): Bool {
    if ((left is JsonInt || left is JsonFloat) && (right is JsonInt || right is JsonFloat)) {
        if (left is JsonInt && right is JsonInt) { return left.toString()==right.toString() }
        return Float64.parse(left.toString())==Float64.parse(right.toString())
    }
    if (let Some(a) <- (left as JsonObject)) {
        if (let Some(b) <- (right as JsonObject)) {
            if (a.getFields().size!=b.getFields().size) { return false }
            for ((key,value) in a.getFields()) {
                if (let Some(other) <- b.get(key)) { if (!taskSourceEqual(value,other)) { return false } }
                else { return false }
            }
            return true
        }
        return false
    }
    if (let Some(a) <- (left as JsonArray)) {
        if (let Some(b) <- (right as JsonArray)) {
            if (a.getItems().size!=b.getItems().size) { return false }
            for (i in 0..a.getItems().size) { if (!taskSourceEqual(a[i],b[i])) { return false } }
            return true
        }
        return false
    }
    return left.toString()==right.toString()
}
