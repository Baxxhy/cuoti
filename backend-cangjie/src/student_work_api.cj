package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

public func submitStudentWork(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"POST")
    let parts = context.request.url.path.split("/")
    let id = parts[parts.size - 2]
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context,db)
        let body = readJson(context,maxBytes: 8 * 1024 * 1024)
        let answer = (editText(body.get("answer") ?? JsonString(""),12000) as JsonString).getOrThrow().getValue()
        let explanation = (editText(body.get("explanation") ?? JsonString(""),12000) as JsonString).getOrThrow().getValue()
        let steps = manualArray(body,"steps",100)
        for (step in steps.getItems()) { editText(step,12000) }
        return db.transaction<JsonValue>({ tx =>
            let rows = tx.query("SELECT status FROM questions WHERE id = ? AND user_id = ? FOR UPDATE",[Some(id),user["id"]]).rows
            if (rows.isEmpty()) { throw ApiError(404,"题目不存在或无权访问") }
            if (rowText(rows[0],"status") == "archived") { throw ApiError(409,"题目已归档，不能提交作答") }
            invalidateQuestionLearning(tx,id)
            tx.query("UPDATE processing_jobs SET status = 'cancelled',error = '已提交新作答，旧识别结果未应用',updated_at = UTC_TIMESTAMP() WHERE question_id = ? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running')",[Some(id)])
            tx.query("UPDATE questions SET student_answer = ?,status = IF(confirmed,'confirmed','needs_confirmation'),updated_at = UTC_TIMESTAMP() WHERE id = ?",[if (answer.isEmpty()) { None } else { Some(answer) },Some(id)])
            let workId = newId()
            tx.query("INSERT INTO student_works (id,question_id,user_id,answer,explanation,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[Some(workId),Some(id),user["id"],Some(answer),Some(explanation)])
            for (index in 0..steps.getItems().size) {
                let text = (steps[index] as JsonString).getOrThrow().getValue()
                tx.query("INSERT INTO student_steps (id,work_id,step_index,text,bbox,raw_text,normalized_text,formula,confidence,source,user_confirmed,created_at,updated_at) VALUES (?,?,?,?,JSON_ARRAY(),?,?,?,1,'user',1,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),Some(workId),Some(index.toString()),Some(text),Some(text),Some(collapseWhitespace(text)),Some(if (text.contains("=")) { text } else { "" })])
            }
            return rowJson("student_works",tx.query("SELECT * FROM student_works WHERE id = ?",[Some(workId)]).rows[0])
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
