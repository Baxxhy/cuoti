package zhiwei

import std.collection.*
import std.fs.*
import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

func teachingTestStrings(value: JsonValue): Array<String> {
    let result = ArrayList<String>()
    for (item in (value as JsonArray).getOrThrow().getItems()) { result.add((item as JsonString).getOrThrow().getValue()) }
    return result.toArray()
}

@Test
class TutorActivitiesTest {
    @TestCase
    func originalPythonLessonParity() {
        let fixtures = (JsonValue.fromStr(String.fromUtf8(File.readFrom("tests/teaching_parity.json"))) as JsonArray).getOrThrow()
        for (value in fixtures.getItems()) {
            let fixture = (value as JsonObject).getOrThrow()
            let input = (fixture["input"] as JsonObject).getOrThrow()
            let plan = buildUnderstandingPlan(jsonText(input,"question_text"),jsonText(input,"subject"),jsonText(input,"question_type"),
                teachingTestStrings(input["knowledge_points"]),teachingTestStrings(input["reference_steps"]))
            @Expect(jsonEquivalent(plan,fixture["plan"]),true)
            let publicPlan = JsonArray()
            for (activity in plan.getItems()) { publicPlan.add(publicTutorActivity((activity as JsonObject).getOrThrow(),2,feedback: "再试一次")) }
            @Expect(jsonEquivalent(publicPlan,fixture["public"]),true)
        }
    }

    @TestCase
    func publicActivityNeverIncludesGradingKeys() {
        let source = tutorActivity("check","检查","问题",[("A","选项")],["A"],"秘密提示","讲解")
        source.put("private_future",JsonString("secret")); source.put("variant_id",JsonString("variant-1"))
        let result = publicTutorActivity(source,3,teaching: "覆盖讲解")
        @Expect(result.getFields().contains("correct_answers"),false)
        @Expect(result.getFields().contains("hint"),false)
        @Expect(result.getFields().contains("private_future"),false)
        @Expect(jsonText(result,"teaching"),"覆盖讲解")
        @Expect(jsonText(result,"variant_id"),"variant-1")
        @Expect(result.getFields().contains("feedback"),false)
        @Expect(source.getFields().contains("correct_answers"),true)
        @Expect(tutorTopic(["　"],"proof"),"错题学习")
        @Expect(tutorTopic([],"choice"),"单选题")
    }
}
