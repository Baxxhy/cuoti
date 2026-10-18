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
}
