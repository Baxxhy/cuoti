package zhiwei

import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class DatasetImageLayoutTest {
    @TestCase
    func questionOptionsAndSolutionsHaveSeparateSignedUrls() {
        let source=(JsonValue.fromStr(##"{"id":"figures","question_text":"如图<ImageHere>求值","options":[{"key":"A","text":"<ImageHere>"},{"key":"B","text":"2"}],"answer":"答案<ImageHere>","solution":"解析<ImageHere>","image_paths":["q.png","a.png","answer.png","solution.png"]}"##) as JsonObject).getOrThrow()
        @Expect(datasetImageMarkers("<ImageHere>"),1)
        @Expect(datasetImageMarkers(""),0)
        @Expect(datasetImageMarkers("普通题目"),0)
        @Expect(datasetImageMarkers("前<ImageHere>中<ImageHere>后"),2)
        let accounts=Accounts("01234567890123456789012345678901")
        let visible=datasetQuestionImages(source,accounts)
        @Expect(tutorFlag(visible,"image_layout_review"),false)
        @Expect(tutorArray(visible,"image_urls").getItems().size,1)
        @Expect(tutorArray(visible,"preview_image_urls").getItems().size,2)
        @Expect(visible.toString().contains("/images/2"),false)
        @Expect(visible.toString().contains("/images/3"),false)
        @Expect(tutorArray((tutorArray(visible,"options")[0] as JsonObject).getOrThrow(),"image_urls").getItems().size,1)
        let after=datasetSolutionImages(source,accounts)
        @Expect(tutorArray(after,"answer_image_urls").getItems().size,1)
        @Expect(tutorArray(after,"solution_image_urls").getItems().size,1)
        @Expect(after.toString().contains("/images/2"),true)
        @Expect(after.toString().contains("/images/3"),true)
        @Expect(tutorArray(source,"image_paths").getItems().size,4)
    }

    @TestCase
    func legacyFiguresRemainAndAmbiguousSourceFiguresAreNotExposed() {
        let source=(JsonValue.fromStr(##"{"id":"legacy","question_text":"如图求值","options":[],"answer":"2","solution":"","image_paths":["q.png"]}"##) as JsonObject).getOrThrow()
        let accounts=Accounts("01234567890123456789012345678901")
        @Expect(tutorArray(datasetQuestionImages(source,accounts),"image_urls").getItems().size,1)
        source.put("source_metadata",JsonValue.fromStr(##"{"has_visual":true}"##))
        let visible=datasetQuestionImages(source,accounts)
        @Expect(tutorFlag(visible,"image_layout_review"),true)
        @Expect(tutorArray(visible,"image_urls").getItems().isEmpty(),true)
        source.put("image_paths",JsonArray())
        source.put("answer",JsonString("答案图<ImageHere>"))
        @Expect(tutorFlag(datasetImageLayout(source),"review"),true)
    }
}
