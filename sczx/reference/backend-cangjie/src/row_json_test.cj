package zhiwei

import std.collection.*
import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class RowJsonTest {
    @TestCase
    func historicalFormulaTitleUsesCompleteQuestion() {
        let row = HashMap<String, Option<String>>()
        row.add("title", Some("求 $x^")); row.add("question_text", Some("求 $x^2+1$ 的最小值"))
        @Expect(jsonText(rowJson("questions", row), "title"), "求 $x^2+1$ 的最小值")
        row["title"] = Some("我的题目 $x$")
        @Expect(jsonText(rowJson("questions", row), "title"), "我的题目 $x$")
        @Expect(academicSummary("求 $x^2+1$ 的最小值", 5), "求 $x^2+1$ 的最小值")
        @Expect(shortTitle("求 $x^2+1$ 的最小值", 5), "求 …")
        @Expect(shortTitle("$x^2+1$", 3), "题目详情")
        @Expect(shortTitle("普通标题", 2), "普通")
    }

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
