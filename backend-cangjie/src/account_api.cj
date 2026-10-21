package zhiwei

import std.collection.*
import std.convert.*
import stdx.net.http.*
import stdx.encoding.json.*
import stdx.encoding.hex.*
import stdx.encoding.url.*

public class Accounts {
    private let secret: String
    public init(secret: String) {
        if (secret.size < 32) { throw IllegalArgumentException("CANGJIE_AUTH_SECRET 至少需要 32 个字符") }
        this.secret = secret
    }

    public func mediaUrl(path: String): String {
        if (!path.startsWith("/uploads/") && !path.startsWith("/reports/") && !path.startsWith("/api/v1/practice/questions/")) { return path }
        let expires = unixNow() + 14400
        let signature = toHexString(hmac256(secret, "media:v1:${expires}:${path}")).toAsciiLower()
        let encoded = StringBuilder()
        for (byte in path.toArray()) {
            if ((byte >= 65 && byte <= 90) || (byte >= 97 && byte <= 122) ||
                (byte >= 48 && byte <= 57) || byte == 45 || byte == 46 || byte == 95 || byte == 126 || byte == 47) {
                encoded.append(String.fromUtf8([byte]))
            } else { encoded.append("%" + toHexString([byte]).toAsciiUpper()) }
        }
        return encoded.toString() + "?expires=${expires}&signature=${signature}"
    }

    public func validMedia(context: HttpContext): Bool {
        try {
            let form = Form(context.request.url.rawQuery ?? "")
            let expires = Int64.parse(form.get("expires") ?? "")
            let now = unixNow()
            if (expires <= now || expires > now + 14400) { return false }
            let expected = toHexString(hmac256(secret, "media:v1:${expires}:${context.request.url.path}")).toAsciiLower()
            return constantEqual(expected.toArray(), (form.get("signature") ?? "").toArray())
        } catch (_: Exception) { return false }
    }

    public func currentUser(context: HttpContext, db: Database): HashMap<String, Option<String>> {
        let authorization = context.request.headers.getFirst("Authorization") ?? ""
        if (!authorization.startsWith("Bearer ")) { throw ApiError(401, "请先使用账号和密码登录") }
        let token = authorization[7..].trimAscii()
        if (let Some(id) <- readToken(token, secret, None)) {
            let rows = db.query("SELECT * FROM users WHERE id = ?", [Some(id)]).rows
            if (rows.size == 1 && ["student","admin"].contains(rowText(rows[0],"role")) && readToken(token, secret, rows[0]["password_hash"]) == Some(id)) { return rows[0] }
        }
        throw ApiError(401, "请先使用账号和密码登录")
    }

    private func session(row: HashMap<String, Option<String>>): JsonObject {
        let result = userJson(row)
        result.put("access_token", JsonString(createToken(rowText(row, "id"), secret,
            rowText(row, "password_hash"), unixNow() + 2592000)))
        return result
    }

    public func register(context: HttpContext): JsonValue {
        requireMethod(context, "POST")
        let body = readJson(context)
        let email = emailField(body)
        let password = textField(body, "password", 256, trim: false)
        let name = textField(body, "name", 100, fallback: Some("智维同学"))
        let grade = textField(body, "grade", 30, fallback: Some("初二"))
        let hash = hashPassword(password)
        let id = newId()
        try (db = Database.fromEnvironment()) {
            try {
                db.transaction<Unit>({ tx =>
                    tx.query("INSERT INTO users (id,email,name,role,password_hash,created_at,updated_at) VALUES (?,?,?,'student',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                        [Some(id), Some(email), Some(name), Some(hash)])
                    tx.query("INSERT INTO student_profiles (id,user_id,grade,learning_goal,preferences,created_at,updated_at) VALUES (?,?,?,'修复错误思维',JSON_OBJECT(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                        [Some(newId()), Some(id), Some(grade)])
                    ()
                })
            } catch (error: DatabaseException) {
                if (error.code == 1062) { throw ApiError(409, "这个邮箱已经注册，请直接登录") }
                throw error
            }
            return session(db.query("SELECT * FROM users WHERE id = ?", [Some(id)]).rows[0])
        }
        throw ApiError(503, "数据库暂时不可用")
    }

    public func login(context: HttpContext): JsonValue {
        requireMethod(context, "POST")
        let body = readJson(context)
        let email = emailField(body)
        let password = textField(body, "password", 256, trim: false)
        try (db = Database.fromEnvironment()) {
            let rows = db.query("SELECT * FROM users WHERE email = ?", [Some(email)]).rows
            if (rows.isEmpty() || !["student","admin"].contains(rowText(rows[0],"role")) || !verifyPassword(password, rowText(rows[0], "password_hash"))) {
                throw ApiError(401, "账号或密码不正确")
            }
            return session(rows[0])
        }
        throw ApiError(503, "数据库暂时不可用")
    }

    public func resetPassword(context: HttpContext): JsonValue {
        requireMethod(context, "POST")
        let body = readJson(context)
        let email = emailField(body)
        let current = textField(body, "current_password", 256, trim: false)
        let replacement = textField(body, "new_password", 256, trim: false)
        let hash = hashPassword(replacement)
        try (db = Database.fromEnvironment()) {
            db.transaction<Unit>({ tx =>
                let rows = tx.query("SELECT * FROM users WHERE email = ? FOR UPDATE", [Some(email)]).rows
                if (rows.isEmpty() || !verifyPassword(current, rowText(rows[0], "password_hash"))) {
                    throw ApiError(401, "账号或当前密码不正确，无法修改密码")
                }
                tx.query("UPDATE users SET password_hash = ?, updated_at = UTC_TIMESTAMP() WHERE id = ?",
                    [Some(hash), rows[0]["id"]])
                ()
            })
        }
        let result = JsonObject()
        result.put("email", JsonString(email))
        result.put("reset", JsonBool(true))
        return result
    }

    public func me(context: HttpContext): JsonValue {
        if (context.request.method != "GET" && context.request.method != "PATCH") {
            context.responseBuilder.header("Allow", "GET, PATCH")
            throw ApiError(405, "请求方法不支持")
        }
        try (db = Database.fromEnvironment()) {
            let user = currentUser(context, db)
            if (context.request.method == "PATCH") {
                let body = readJson(context)
                taskStrict(body,["name","email","grade","current_password"])
                let name=if (body.get("name").isSome()) { textField(body,"name",100) } else { rowText(user,"name") }
                let email=if (body.get("email").isSome()) { emailField(body) } else { rowText(user,"email") }
                let grade=if (body.get("grade").isSome()) { textField(body,"grade",30) } else { "" }
                if (!grade.isEmpty() && (rowText(user,"role")!="student" || !["初一","初二","初三","高一","高二","高三"].contains(grade))) { throw ApiError(422,"请选择有效年级") }
                try {
                    return db.transaction<JsonValue>({ tx =>
                        let current=tx.query("SELECT * FROM users WHERE id=? FOR UPDATE",[user["id"]]).rows[0]
                        if (email!=rowText(current,"email")) {
                            let password=textField(body,"current_password",256,trim:false)
                            if (!verifyPassword(password,rowText(current,"password_hash"))) { throw ApiError(422,"当前密码不正确，邮箱未修改") }
                        }
                        tx.query("UPDATE users SET name=?,email=?,updated_at=UTC_TIMESTAMP() WHERE id=?",[Some(name),Some(email),user["id"]])
                        if (!grade.isEmpty()) {
                            tx.query("UPDATE student_profiles SET grade=?,preferences=JSON_SET(COALESCE(preferences,JSON_OBJECT()),'$.experience_version',COALESCE(JSON_EXTRACT(preferences,'$.experience_version'),0)+1),updated_at=UTC_TIMESTAMP() WHERE user_id=?",[Some(grade),user["id"]])
                        }
                        userJson(tx.query("SELECT * FROM users WHERE id=?",[user["id"]]).rows[0])
                    })
                } catch (error: DatabaseException) {
                    if (error.code==1062) { throw ApiError(409,"这个邮箱已被使用，请换一个邮箱") }
                    throw error
                }
            }
            return userJson(user)
        }
        throw ApiError(503, "数据库暂时不可用")
    }

    public func routes(server: Server): Unit {
        server.distributor.register("/api/v1/auth/register", { ctx => guarded(ctx, { => register(ctx) }) })
        server.distributor.register("/api/v1/auth/login", { ctx => guarded(ctx, { => login(ctx) }) })
        server.distributor.register("/api/v1/auth/reset-password", { ctx => guarded(ctx, { => resetPassword(ctx) }) })
        server.distributor.register("/api/v1/auth/me", { ctx => guarded(ctx, { => me(ctx) }) })
    }
}
