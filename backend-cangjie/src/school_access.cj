package zhiwei

import std.collection.*
import std.convert.*
import std.time.*
import stdx.encoding.json.*

enum SchoolAction {
    CreateClass | AddStudent | RemoveStudent | UpdatePlan | CreateQuestion | CreateAssignment | ReviewDecision | ReviewRevoke | ReviewRegrade | ReviewTransfer
    func wire(): String {
        match (this) {
            case CreateClass => "class.create"
            case AddStudent => "class.student.add"
            case RemoveStudent => "class.student.remove"
            case UpdatePlan => "plan.update"
            case CreateQuestion => "question.create"
            case CreateAssignment => "assignment.create"
            case ReviewRevoke => "review.revoke"
            case ReviewRegrade => "review.regrade"
            case ReviewTransfer => "review.transfer"
            case ReviewDecision => "review.decision"
        }
    }
    func target(): String { match (this) { case UpdatePlan => "review_plan"; case CreateQuestion => "question"; case CreateAssignment => "assignment"; case ReviewDecision | ReviewRevoke | ReviewRegrade | ReviewTransfer => "teacher_review_task"; case CreateClass | AddStudent | RemoveStudent => "class" } }
}

// A scope can only be constructed from an authenticated teacher. Every class
// and student lookup derives ownership from this actor, never the request body.
class TeacherScope {
    let db: Database
    let actor: String
    init(db: Database, user: HashMap<String,Option<String>>) {
        if (rowText(user,"role")!="teacher") { throw ApiError(403,"当前账号不是教师") }
        this.db=db; actor=rowText(user,"id")
    }
    func classroom(id: String, lock!: Bool=false): JsonObject {
        let rows=db.query("SELECT * FROM teacher_classes WHERE id=? AND teacher_id=?"+if (lock) { " FOR UPDATE" } else { "" },[Some(id),Some(actor)]).rows
        if (rows.isEmpty()) { throw ApiError(404,"班级不存在或无权访问") }
        return rowJson("teacher_classes",rows[0])
    }
    func student(classId: String, studentId: String): JsonObject {
        classroom(classId,lock:true)
        let rows=db.query("SELECT u.* FROM users u JOIN teacher_class_students l ON l.student_id=u.id WHERE l.class_id=? AND u.id=? AND u.role='student'",[Some(classId),Some(studentId)]).rows
        if (rows.isEmpty()) { throw ApiError(404,"学生不在该班级") }
        return userJson(rows[0])
    }
    func audit(action: SchoolAction, target: String, before: JsonObject, after: JsonObject, reason: String): Unit {
        db.query("INSERT INTO teacher_audit_logs (id,teacher_id,action,target_type,target_id,before_json,after_json,reason,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(actor),Some(action.wire()),Some(action.target()),Some(target),Some(before.toString()),Some(after.toString()),Some(reason)])
    }
}

func schoolCount(db: Database, sql: String, params: Array<Option<String>>): Int64 {
    return Int64.parse(rowText(db.query(sql,params).rows[0],"count"))
}

func schoolAverage(db: Database, studentId: String): Float64 {
    let rows=db.query("SELECT AVG(mastery_score) AS score FROM mastery_states WHERE user_id=?",[Some(studentId)]).rows
    if (let Some(score) <- rows[0]["score"]) { return schoolRound(Float64.parse(score),1000.0) }
    return 0.0
}

func schoolRound(value: Float64, scale: Float64): Float64 {
    let scaled=value*scale; let lower=Int64(scaled); let fraction=scaled-Float64(lower)
    let rounded=if (fraction>0.5 || (fraction==0.5 && lower%2!=0)) { lower+1 } else { lower }
    return Float64(rounded)/scale
}

func schoolText(body: JsonObject, key: String, fallback: String, maximum: Int64, nonempty!: Bool=false): String {
    var text=fallback
    if (let Some(value) <- body.get(key)) {
        if (let Some(raw) <- (value as JsonString)) { text=raw.getValue() }
        else { throw ApiError(422,"${key} 必须是文字") }
    }
    if (runeCount(text)>maximum || (nonempty && stripWhitespace(text).isEmpty())) { throw ApiError(422,"${key} 长度不正确") }
    return text
}

// Native calendar/timezone validation; naive browser datetime-local values use
// the same UTC interpretation as the original parse_timestamp helper.
func schoolDeadline(value: String): String {
    try {
        var text=value.replace(" ","T")
        if (text.size==10) { text+="T00:00:00" }
        if (text.size==16) { text+=":00" }
        if (text.size<19) { throw IllegalArgumentException("时间不完整") }
        let suffix=text[10..]
        if (!suffix.contains("+") && !suffix.contains("-") && !text.endsWith("Z")) { text+="Z" }
        return DateTime.parse(text).toUnixTimeStamp().toSeconds().toString()
    } catch (_: Exception) { throw ApiError(422,"请选择有效的截止时间") }
}
