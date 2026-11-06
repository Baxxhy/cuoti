package zhiwei

import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class StudyBankReadingTest {
    @TestCase
    func passageIsPreservedAndAnswerIsNotExposed() {
        let source=(JsonValue.fromStr(##"{"id":"example","question_text":"The complete article.\n\nWho is the author?","answer":"A","source_metadata":{"passage_id":"reading-1"},"image_paths":[]}"##) as JsonObject).getOrThrow()
        let result=bankQuestion(source,Accounts("01234567890123456789012345678901"))
        @Expect(jsonText(result,"preview_text"),"阅读理解：Who is the author?")
        @Expect(jsonText(result,"question_text"),"The complete article.\n\nWho is the author?")
        @Expect(result.get("answer").isNone(),true)
        source.put("source_metadata",JsonObject())
        @Expect(bankQuestion(source,Accounts("01234567890123456789012345678901")).get("preview_text").isNone(),true)
    }
}
