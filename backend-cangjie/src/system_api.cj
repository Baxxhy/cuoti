package zhiwei

import stdx.encoding.json.*
import stdx.net.http.*

func systemState(probe!: Bool=false): JsonObject {
    let input=JsonObject(); input.put("operation",JsonString("system_state")); input.put("probe_provider",JsonBool(probe)); return algorithmCompute(input)
}

func systemApi(context: HttpContext, kind: String): JsonValue {
    requireMethod(context,if (kind=="probe") { "POST" } else { "GET" })
    if (kind=="probe") { return systemState(probe:true)["provider"] }
    if (kind=="providers") { return systemState()["provider"] }
    if (kind=="voice") { return systemState()["voice"] }
    try (db=Database.fromEnvironment()) {
        db.query("SELECT COUNT(*) AS total FROM users")
        let state=systemState(); let provider=tutorObject(state,"provider"); let result=JsonObject()
        result.put("status",JsonString("healthy")); result.put("database",JsonString("mysql")); result.put("ai",provider["last_status"]); result.put("image_recognition",JsonBool(tutorNumber(provider,"vision_entries")>0)); return result
    }
    throw ApiError(503,"数据库暂时不可用")
}
