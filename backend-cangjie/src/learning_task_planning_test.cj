package zhiwei

import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class TaskPlanningTest {
    @TestCase
    func recommendationMustRemainInsideNativeCandidateSet() {
        let domain=(JsonValue.fromStr(##"{"practice_candidates":[{"id":"q1","source":"dataset","just_mastered":false}]}"##) as JsonObject).getOrThrow()
        let good=(JsonValue.fromStr(##"{"student_view":{"recommendation":{"question_id":"q1","question_source":"dataset","alternatives":[]}}}"##) as JsonObject).getOrThrow()
        validateTaskRecommendation(good,domain)
        for (raw in [
            ##"{"student_view":{"recommendation":{"question_id":"outside","question_source":"dataset"}}}"##,
            ##"{"student_view":{"recommendation":{"question_id":"q1","question_source":"notebook"}}}"##,
            ##"{"student_view":{"recommendation":{"question_id":"q1","question_source":"dataset","alternatives":["outside"]}}}"##
        ]) {
            var rejected=false
            try { validateTaskRecommendation((JsonValue.fromStr(raw) as JsonObject).getOrThrow(),domain) }
            catch (_: ApiError) { rejected=true }
            @Expect(rejected,true)
        }
    }
}
