package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.json.*

func queryCount(db: Database, sql: String, params: Array<Option<String>>): Int64 {
    return Int64.parse(rowText(db.query(sql,params).rows[0],"count"))
}

func optionalText(body: JsonObject, key: String, fallback: String, maximum: Int64, nonempty!: Bool=false): String {
    var text=fallback
    if (let Some(value) <- body.get(key)) {
        if (let Some(raw) <- (value as JsonString)) { text=raw.getValue() }
        else { throw ApiError(422,"${key} 必须是文字") }
    }
    if (runeCount(text)>maximum || (nonempty && stripWhitespace(text).isEmpty())) { throw ApiError(422,"${key} 长度不正确") }
    return text
}
