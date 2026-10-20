package zhiwei

import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class KnowledgeLessonVersionTest {
    func sample(): JsonArray {
        return (JsonValue.fromStr(##"[{"id":"row-1","code":"equation","subject":"数学","name":"等式性质","updated_at":"2026-01-01","content":{"definition":"两边同时加同一个数，等式仍成立。","formulas":["a=b"]}}]"##) as JsonArray).getOrThrow()
    }
    @TestCase
    func metadataIsNotNewTeachingMaterial() {
        let first=sample(); let second=sample(); let card=(second[0] as JsonObject).getOrThrow()
        card.put("id",JsonString("imported-row")); card.put("updated_at",JsonString("2026-10-20"))
        @Expect(lessonSourceVersion(first),lessonSourceVersion(second))
        let content=(card["content"] as JsonObject).getOrThrow(); content.put("definition",JsonString("除以同一个非零数，等式仍成立。"))
        @Expect(lessonSourceVersion(first)==lessonSourceVersion(second),false)
    }
    @TestCase
    func dependencyChangesAndLegacyReplayAreChecked() {
        let original=sample(); let added=sample(); let dependent=JsonObject(); dependent.put("code",JsonString("addition")); dependent.put("retrieval_role",JsonString("prerequisite")); dependent.put("anchor_code",JsonString("equation")); added.add(dependent)
        @Expect(lessonSourceVersion(original)==lessonSourceVersion(added),false)
        for (source in [lessonSourceVersion(original),sha256(original.toString().toArray())]) {
            let record=JsonObject(); record.put("input_fingerprint",JsonString(source+":"+sha256("为什么".toArray())))
            @Expect(lessonVersionMatches(record,original,"为什么"),true)
            @Expect(lessonVersionMatches(record,original,"另一个问题"),false)
            @Expect(lessonVersionMatches(record,added,"为什么"),false)
        }
    }
}
