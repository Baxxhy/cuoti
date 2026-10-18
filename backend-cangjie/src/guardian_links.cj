package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

// Student consent is the only public way to grant report access. Lock the
// student row for all mutations so duplicate grants and revocations serialize.
func studentGuardianLinks(context: HttpContext, accounts: Accounts): JsonValue {
    let method=context.request.method
    if (method!="GET" && method!="POST") { context.responseBuilder.header("Allow","GET, POST"); throw ApiError(405,"请求方法不支持") }
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        if (rowText(user,"role")!="student") { throw ApiError(403,"请使用学生账号管理查看权限") }
        return db.transaction<JsonValue>({ tx =>
            if (method=="GET") {
                let result=JsonArray()
                for (row in tx.query("SELECT DISTINCT u.id,u.name,u.email FROM guardian_student_links l JOIN users u ON u.id=l.guardian_id WHERE l.student_id=? AND u.role='guardian' ORDER BY u.id",[user["id"]]).rows) {
                    let item=JsonObject(); for (key in ["id","name","email"]) { item.put(key,JsonString(rowText(row,key))) }; result.getItems().add(item)
                }
                return result
            }
            let body=readJson(context)
            if (!(body.get("confirmed").getOrDefault({ => JsonNull() }) is JsonBool) || !tutorFlag(body,"confirmed")) { throw ApiError(422,"请确认允许该家长查看学习报告") }
            let email=stripWhitespace(schoolText(body,"email","",190,nonempty:true)).toAsciiLower()
            tx.query("SELECT id FROM users WHERE id=? FOR UPDATE",[user["id"]])
            let guardians=tx.query("SELECT id,name,email FROM users WHERE email=? AND role='guardian'",[Some(email)]).rows
            if (guardians.isEmpty()) { throw ApiError(404,"未找到该家长账号，请核对邮箱和账号身份") }
            let guardian=guardians[0]
            if (tx.query("SELECT id FROM guardian_student_links WHERE student_id=? AND guardian_id=?",[user["id"],guardian["id"]]).rows.isEmpty()) {
                if (schoolCount(tx,"SELECT COUNT(DISTINCT guardian_id) AS count FROM guardian_student_links WHERE student_id=?",[user["id"]])>=5) { throw ApiError(409,"最多允许5位家长查看，请先解除不再使用的关联") }
                tx.query("INSERT INTO guardian_student_links (id,guardian_id,student_id,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(newId()),guardian["id"],user["id"]])
            }
            let result=JsonObject(); for (key in ["id","name","email"]) { result.put(key,JsonString(rowText(guardian,key))) }; return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}

func removeGuardianLink(context: HttpContext, accounts: Accounts, studentSide: Bool): JsonValue {
    requireMethod(context,"DELETE")
    let parts=context.request.url.path.split("/"); let otherId=parts[parts.size-1]
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        if (rowText(user,"role")!=if (studentSide) { "student" } else { "guardian" }) { throw ApiError(403,"当前账号不能执行该操作") }
        let studentId=if (studentSide) { rowText(user,"id") } else { otherId }
        let guardianId=if (studentSide) { otherId } else { rowText(user,"id") }
        return db.transaction<JsonValue>({ tx =>
            tx.query("SELECT id FROM users WHERE id=? FOR UPDATE",[Some(studentId)])
            // Repeating removal is safe and does not reveal another user's links.
            tx.query("DELETE FROM guardian_student_links WHERE student_id=? AND guardian_id=?",[Some(studentId),Some(guardianId)])
            let result=JsonObject(); result.put("removed",JsonBool(true)); return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
