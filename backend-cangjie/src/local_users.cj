package zhiwei

import std.env.*
import stdx.encoding.json.*

// Local deployment command only. Never registered as an HTTP handler.
func createLocalUser(body: JsonObject): JsonObject {
    let email=emailField(body)
    let role=textField(body,"role",30)
    if (role!="teacher" && role!="guardian" && role!="admin") { throw ApiError(422,"本地命令只创建教师、家长或管理员账号；学生请使用注册页面") }
    let name=textField(body,"name",100)
    let flag=body.get("check_only").getOrDefault({ => JsonBool(false) })
    if (!(flag is JsonBool)) { throw ApiError(422,"check_only 必须是布尔值") }
    let checkOnly=(flag as JsonBool).getOrThrow().getValue()
    let hash=if (checkOnly) { "" } else {
        let password=textField(body,"password",256,trim:false)
        var length: Int64=0; for (_ in password.runes()) { length++ }
        if (length<12 || password.contains("\n") || password.contains("\r")) { throw ApiError(422,"角色账号密码至少12个字符") }
        hashPassword(password)
    }
    let database=getVariable("CANGJIE_DB_NAME") ?? ""
    if (database.isEmpty()) { throw ApiError(422,"请显式设置 CANGJIE_DB_NAME，命令不会选择默认数据库") }
    try (db=Database.fromEnvironment()) {
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version='009_task_sources'").rows.size!=1) { throw ApiError(409,"请先完成仓颉数据库升级，命令不会自动初始化或升级") }
        let result=JsonObject(); result.put("database",JsonString(database)); result.put("email",JsonString(email)); result.put("role",JsonString(role))
        if (checkOnly) {
            let rows=db.query("SELECT role FROM users WHERE email=?",[Some(email)]).rows
            result.put("available",JsonBool(rows.isEmpty()))
            if (!rows.isEmpty()) { result.put("existing_role",JsonString(rowText(rows[0],"role"))) }
            result.put("created",JsonBool(false)); return result
        }
        let id=newId()
        try {
            db.transaction<Unit>({ tx =>
                tx.query("INSERT INTO users (id,email,name,role,password_hash,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(id),Some(email),Some(name),Some(role),Some(hash)])
                ()
            })
        } catch (error: DatabaseException) {
            if (error.code==1062) { throw ApiError(409,"邮箱已存在；未修改身份、密码或学习记录，请使用专用的新邮箱") }
            throw error
        }
        result.put("id",JsonString(id)); result.put("created",JsonBool(true)); return result
    }
    throw ApiError(503,"数据库暂时不可用")
}

func localUserCommand(): Int64 {
    try {
        let raw=getStdIn().readln() ?? ""
        if (raw.size>8192 || raw.isEmpty()) { throw ApiError(422,"请输入一行有效的账号配置") }
        let body: JsonObject
        try { body=(JsonValue.fromStr(raw) as JsonObject).getOrThrow() }
        catch (_: Exception) { throw ApiError(422,"请输入有效的账号配置JSON对象") }
        println(createLocalUser(body).toString()); return 0
    } catch (error: ApiError) {
        let result=JsonObject(); result.put("code",JsonInt(Int64(error.status))); result.put("message",JsonString(error.message)); println(result.toString()); return 1
    } catch (_: Exception) {
        // Parser/DB exceptions may contain user input or operational detail.
        let result=JsonObject(); result.put("code",JsonInt(503)); result.put("message",JsonString("账号未创建，请检查仓颉运行环境、独立数据库和当前版本")); println(result.toString()); return 1
    }
}
