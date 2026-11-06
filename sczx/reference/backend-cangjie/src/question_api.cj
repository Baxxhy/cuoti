package zhiwei

import stdx.net.http.*
import stdx.encoding.json.*

public func questionRoute(context: HttpContext, accounts: Accounts): JsonValue {
    let parts = context.request.url.path.split("/")
    let id = parts[parts.size - 1]
    if (context.request.method == "GET") { return questionDetail(context, accounts, id) }
    if (context.request.method == "PATCH") { return questionEdit(context, accounts, id) }
    if (context.request.method != "DELETE") {
        context.responseBuilder.header("Allow", "GET, PATCH, DELETE")
        throw ApiError(405, "请求方法不支持")
    }
    try (db = Database.fromEnvironment()) {
        let user = accounts.currentUser(context, db)
        db.transaction<Unit>({ tx =>
            let owned = tx.query("SELECT id FROM questions WHERE id = ? AND user_id = ? FOR UPDATE",
                [Some(id), user["id"]])
            if (owned.rows.isEmpty()) { throw ApiError(404, "内容不存在或无权访问") }
            tx.query("UPDATE questions SET status = 'archived', updated_at = UTC_TIMESTAMP() WHERE id = ?",
                [Some(id)])
            tx.query("UPDATE review_plans SET status = 'cancelled', updated_at = UTC_TIMESTAMP() WHERE question_id = ? AND status = 'pending'",
                [Some(id)])
            ()
        })
        let result = JsonObject()
        result.put("deleted", JsonBool(true))
        return result
    }
    throw ApiError(503, "数据库暂时不可用")
}
