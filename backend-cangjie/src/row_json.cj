package zhiwei

import std.collection.*
import std.convert.*
import std.fs.*
import stdx.encoding.json.*

// Static contract snapshot, generated from the original schema during migration.
// No Python process or original database is involved in request serialization.
let columnTypes = (JsonValue.fromStr(String.fromUtf8(File.readFrom("schema/column_types.json"))) as JsonObject).getOrThrow()
let taskColumnTypes = (JsonValue.fromStr(String.fromUtf8(File.readFrom("schema/task_column_types.json"))) as JsonObject).getOrThrow()

public func rowJson(table: String, row: HashMap<String, Option<String>>): JsonObject {
    let types = ((columnTypes.get(table) ?? taskColumnTypes[table]) as JsonObject).getOrThrow()
    let result = JsonObject()
    for ((key, value) in row) {
        let kind = (types[key] as JsonString).getOrThrow().getValue()
        if (let Some(raw) <- value) {
            let parsed: JsonValue = match (kind) {
                case "json" => JsonValue.fromStr(raw)
                case "bool" => JsonBool(raw != "0")
                case "int" => JsonInt(Int64.parse(raw))
                case "float" => JsonFloat(Float64.parse(raw))
                case "datetime" => JsonString(raw.replace(" ", "T") + "+00:00")
                case _ => JsonString(raw)
            }
            result.put(key, parsed)
        } else { result.put(key, JsonNull()) }
    }
    return result
}
