package zhiwei

import std.collection.*
import stdx.net.http.*
import stdx.encoding.json.*

public class ApiError <: Exception {
    public let status: UInt16
    public init(status: UInt16, message: String) { super(message); this.status = status }
}

public func jsonResponse(context: HttpContext, value: JsonValue, status!: UInt16 = 200): Unit {
    context.responseBuilder.status(status).header("Content-Type", "application/json; charset=utf-8")
        .header("Cache-Control", "no-store").body(value.toString())
}

public func envelope(data: JsonValue): JsonObject {
    let result = JsonObject()
    result.put("success", JsonBool(true))
    result.put("data", data)
    result.put("error", JsonNull())
    result.put("request_id", JsonString(newId()))
    return result
}

public func guarded(context: HttpContext, work: () -> JsonValue, wrap!: Bool = true, successStatus!: UInt16 = 200): Unit {
    try { let result=work(); jsonResponse(context, if (wrap) { envelope(result) } else { result }, status:successStatus) }
    catch (error: ApiError) {
        let result = JsonObject()
        result.put("detail", JsonString(error.message))
        jsonResponse(context, result, status: error.status)
    } catch (_: DatabaseException) {
        let result = JsonObject()
        result.put("detail", JsonString("数据库暂时不可用，请稍后重试"))
        jsonResponse(context, result, status: 503)
    } catch (_: Exception) {
        let result = JsonObject()
        result.put("detail", JsonString("请求未完成，请稍后重试"))
        jsonResponse(context, result, status: 500)
    }
}

public func requireMethod(context: HttpContext, expected: String): Unit {
    if (context.request.method != expected) {
        context.responseBuilder.header("Allow", expected)
        throw ApiError(405, "请求方法不支持")
    }
}

public func readJson(context: HttpContext, maxBytes!: Int64 = 65536, defaultEmpty!: Bool = false): JsonObject {
    let bytes = Array<UInt8>(maxBytes + 1, repeat: 0)
    var length: Int64 = 0
    while (true) {
        let count = context.request.body.read(bytes[length..])
        if (count == 0) { break }
        length += count
        if (length > maxBytes) { throw ApiError(413, "请求内容过大") }
    }
    if (length == 0 && defaultEmpty) { return JsonObject() }
    try {
        return (JsonValue.fromStr(String.fromUtf8(bytes[..length])) as JsonObject).getOrThrow()
    } catch (_: Exception) { throw ApiError(422, "请输入有效的 JSON 对象") }
}

public func textField(data: JsonObject, key: String, limit: Int64, trim!: Bool = true,
    fallback!: Option<String> = None): String {
    var value = ""
    if (let Some(item) <- data.get(key)) {
        if (let Some(text) <- (item as JsonString)) { value = text.getValue() }
        else { throw ApiError(422, "${key} 必须是文字") }
    } else if (let Some(text) <- fallback) { value = text }
    else { throw ApiError(422, "缺少 ${key}") }
    if (trim) { value = stripWhitespace(value) }
    var count: Int64 = 0
    for (_ in value.runes()) { count++ }
    if (count == 0 || count > limit) { throw ApiError(422, "${key} 长度不正确") }
    return value
}

public func emailField(data: JsonObject): String {
    let email = textField(data, "email", 190).toAsciiLower()
    let parts = email.split("@")
    if (parts.size != 2 || parts[0].isEmpty() || parts[1].isEmpty() ||
        !parts[1].contains(".") || parts[1].startsWith(".") || parts[1].endsWith(".")) {
        throw ApiError(422, "请输入正确的邮箱")
    }
    for (space in [" ", "\t", "\r", "\n", "\u{b}", "\u{c}", "\u{85}", "\u{a0}", "\u{1680}",
        "\u{2000}", "\u{2001}", "\u{2002}", "\u{2003}", "\u{2004}", "\u{2005}", "\u{2006}",
        "\u{2007}", "\u{2008}", "\u{2009}", "\u{200a}", "\u{2028}", "\u{2029}", "\u{202f}", "\u{205f}", "\u{3000}"]) {
        if (email.contains(space)) { throw ApiError(422, "请输入正确的邮箱") }
    }
    return email
}

public func rowText(row: HashMap<String, Option<String>>, key: String): String {
    return row[key].getOrThrow()
}

public func userJson(row: HashMap<String, Option<String>>): JsonObject {
    let result = JsonObject()
    for (key in ["id", "email", "name", "role", "created_at", "updated_at"]) {
        var value = rowText(row, key)
        if (key == "created_at" || key == "updated_at") { value = value.replace(" ", "T") + "+00:00" }
        result.put(key, JsonString(value))
    }
    return result
}
