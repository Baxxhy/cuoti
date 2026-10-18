package zhiwei

import std.fs.*
import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class LearningJourneyTest {
    @TestCase
    func originalPythonProjectionParity() {
        let fixtures=(JsonValue.fromStr(String.fromUtf8(File.readFrom("tests/journey_parity.json"))) as JsonArray).getOrThrow()
        for (raw in fixtures.getItems()) {
            let fixture=(raw as JsonObject).getOrThrow()
            let result=buildLearningJourney(tutorObject(fixture,"input"),jsonText(fixture,"now"))
            @Expect(jsonEquivalent(result,fixture["expected"]),true)
        }
    }
}
