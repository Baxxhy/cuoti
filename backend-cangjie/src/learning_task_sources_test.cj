package zhiwei

import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class TaskSourcesTest {
    @TestCase
    func mysqlJsonNumericRepresentationIsNotAChange() {
        let original=JsonValue.fromStr(##"{"steps":[{"id":"s1","confidence":1.0,"confirmed":true}]}"##)
        let stored=JsonValue.fromStr(##"{"steps":[{"confirmed":true,"confidence":1,"id":"s1"}]}"##)
        @Expect(taskSourceEqual(original,stored),true)
        for (changed in [##"{"steps":[{"id":"s2","confidence":1,"confirmed":true}]}"##,##"{"steps":[{"id":"s1","confidence":0.9,"confirmed":true}]}"##,##"{"steps":[{"id":"s1","confidence":1,"confirmed":1}]}"##]) {
            @Expect(taskSourceEqual(original,JsonValue.fromStr(changed)),false)
        }
    }
}
