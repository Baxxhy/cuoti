package zhiwei

import std.collection.*
import std.fs.*
import stdx.encoding.json.*

enum SchoolTable {
    Question | TeacherQuestion | Assignment | StudentAssignment | Attempt | ReviewTask | ReviewResult
    func name(): String {
        match (this) {
            case Question => "questions"
            case TeacherQuestion => "teacher_questions"
            case Assignment => "question_assignments"
            case StudentAssignment => "assignment_students"
            case Attempt => "assignment_attempts"
            case ReviewTask => "teacher_review_tasks"
            case ReviewResult => "teacher_review_results"
        }
    }
}

let schoolDefaults=(JsonValue.fromStr(String.fromUtf8(File.readFrom("schema/school_defaults.json"))) as JsonObject).getOrThrow()

// Only internal, typed table names and schema-known columns form SQL identifiers.
// Values are always bound. No request object is used as a record wholesale.
class SchoolRecord {
    let table: SchoolTable
    let id: String
    let fields: JsonObject
    init(table: SchoolTable) {
        this.table=table; id=newId()
        fields=(JsonValue.fromStr(schoolDefaults[table.name()].toString()) as JsonObject).getOrThrow()
        fields.put("id",JsonString(id))
    }
    func put(key: String,value: JsonValue): Unit {
        if (!(columnTypes[table.name()] as JsonObject).getOrThrow().getFields().contains(key) || key=="created_at" || key=="updated_at") { throw IllegalArgumentException("无效业务列") }
        fields.put(key,value)
    }
    func save(db: Database): JsonObject {
        let columns=StringBuilder(); let placeholders=StringBuilder(); let params=ArrayList<Option<String>>()
        for ((key,value) in fields.getFields()) {
            if (!params.isEmpty()) { columns.append(","); placeholders.append(",") }
            columns.append("`${key}`"); placeholders.append("?"); params.add(sqlValue(value))
        }
        db.query("INSERT INTO ${table.name()} (${columns},created_at,updated_at) VALUES (${placeholders},UTC_TIMESTAMP(),UTC_TIMESTAMP())",params.toArray())
        return schoolRow(db,table,id)
    }
}

func schoolRow(db: Database, table: SchoolTable, id: String): JsonObject {
    let rows=db.query("SELECT * FROM ${table.name()} WHERE id=?",[Some(id)]).rows
    if (rows.isEmpty()) { throw ApiError(409,"业务记录已不存在") }
    return rowJson(table.name(),rows[0])
}

func assignmentContext(db: Database, id: String, owner: String, lock!: Bool=false): JsonObject {
    let rows=db.query("SELECT * FROM assignment_students WHERE id=? AND student_id=?"+if (lock) { " FOR UPDATE" } else { "" },[Some(id),Some(owner)]).rows
    if (rows.isEmpty()) { throw ApiError(404,"布置任务不存在") }
    let link=rowJson("assignment_students",rows[0]); let assignment=schoolRow(db,SchoolTable.Assignment,jsonText(link,"assignment_id"))
    let question=schoolRow(db,SchoolTable.Question,jsonText(assignment,"question_id"))
    let metaRows=db.query("SELECT * FROM teacher_questions WHERE question_id=?",[sqlValue(question["id"])]).rows
    if (metaRows.isEmpty()) { throw ApiError(409,"题目判题配置已不存在") }
    let result=JsonObject(); result.put("link",link); result.put("assignment",assignment); result.put("question",question); result.put("meta",rowJson("teacher_questions",metaRows[0])); return result
}

func requireAssignmentPending(snapshot: JsonObject): Unit {
    let link=tutorObject(snapshot,"link"); let status=jsonText(link,"status")
    let repeat=status=="completed" && tutorFlag(tutorObject(tutorObject(snapshot,"assignment"),"settings"),"allow_repeat")
    if (status!="pending" && !repeat) { throw ApiError(409,"当前任务暂不能再次作答") }
}
