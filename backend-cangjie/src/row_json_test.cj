package zhiwei

import std.collection.*
import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class RowJsonTest {
    @TestCase
    func questionResponseTypes() {
        let row = HashMap<String, Option<String>>()
        row.add("id", Some("000123"))
        row.add("confirmed", Some("1"))
        row.add("favorite", Some("0"))
        row.add("grade", None)
        row.add("question_text", Some("中文😀"))
        row.add("tags", Some("[\"代数\",\"方程\"]"))
        row.add("options", Some("[{\"label\":\"A\",\"text\":\"2\"}]"))
        row.add("created_at", Some("2026-10-15 01:02:03"))
        let json = rowJson("questions", row)
        @Expect((json["id"] as JsonString).getOrThrow().getValue(), "000123")
        @Expect(json["confirmed"].toString(), "true")
        @Expect(json["favorite"].toString(), "false")
        @Expect(json["grade"] is JsonNull, true)
        @Expect((json["tags"] as JsonArray).getOrThrow().getItems().size, 2)
        @Expect((json["options"] as JsonArray).getOrThrow().getItems()[0] is JsonObject, true)
        @Expect((json["created_at"] as JsonString).getOrThrow().getValue(), "2026-10-15T01:02:03+00:00")
    }
}
