package zhiwei

import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class DialogueKnowledgeTest {
    @TestCase
    func naturalLanguageAndAliasesMatchWithoutArbitraryFallback() {
        let card=(JsonValue.fromStr(##"{"name":"等式基本性质","code":"math.equation_property","content":{"grade":"初一","related_knowledge":["等式的性质"]}}"##) as JsonObject).getOrThrow()
        @Expect(dialogueCardScore(card,"为什么等式基本性质允许两边同除非零数？","初一")>100,true)
        @Expect(dialogueCardScore(card,"能解释等式的性质吗","初一")>0,true)
        @Expect(dialogueCardScore(card,"文言文中的词义是什么","初一"),0)
        @Expect(dialogueCardScore(card,"等式基本性质","高一")>0,true)
        tutorObject(card,"content").put("grade",JsonString("高一"))
        @Expect(dialogueCardScore(card,"等式基本性质","初一"),0)
    }

    @TestCase
    func analysisLabelsAndNullableGradeRemainUsable() {
        let snapshot=(JsonValue.fromStr(##"{"memory_snapshot":null,"question":{"subject":"数学","grade":null,"question_type":"综合题","question_text":"2x+1=2","student_answer":"2","knowledge_points":[]},"analysis":{"knowledge_points":["等式基本性质"]},"session":{"state":{},"turn_count":0,"hint_level":0},"references":[],"steps":[],"turns":[]}"##) as JsonObject).getOrThrow()
        let context=dialogueContext(snapshot,"为什么要除以2")
        @Expect(jsonText(context,"grade"),"")
        @Expect(tutorArray(context,"knowledge_points").getItems().size,1)
    }
}
