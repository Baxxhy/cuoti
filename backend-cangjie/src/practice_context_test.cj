package zhiwei

import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class PracticeContextTest {
    @TestCase
    func pythonCompatibleFingerprint() {
        let value=JsonValue.fromStr(##"{"题目": "x=\"\\\n中文😀", "options": [{"text": "选项甲", "key": "A"}], "student_work_revisions": ["a", "b"], "empty": null}"##)
        @Expect(sha256(learningFingerprintJson(value).toArray()), "74c903ec10726de023bff49559f627c703eee2e5dc3d57d8973d16c70c3dac9a")
    }
    @TestCase
    func restoredReceiptRenewsSolutionImageLinks() {
        let question=(JsonValue.fromStr(##"{"id":"image-question","question_text":"求解","options":[],"answer":"2","solution":"<ImageHere>","image_paths":["uploads/diagram.png"]}"##) as JsonObject).getOrThrow()
        let receipt=JsonObject(); let old=JsonArray(); old.add(JsonString("/expired")); receipt.put("solution_image_urls",old)
        let refreshed=refreshedPracticeReceipt(Accounts("test-secret-at-least-thirty-two-characters"),question,receipt)
        let urls=tutorArray(refreshed,"solution_image_urls")
        @Expect(urls.getItems().size,1)
        @Expect(tutorAnswerText(urls[0]).startsWith("/api/v1/practice/questions/image-question/images/0?expires="),true)
        @Expect(tutorAnswerText(urls[0]).contains("signature="),true)
    }

}
