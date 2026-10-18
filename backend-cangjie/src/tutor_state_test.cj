package zhiwei

import std.unittest.*
import std.unittest.testmacro.*

@Test
class TutorStateTest {
    @TestCase
    func completeLearningPath() {
        var stage = transitionTutorStage("understanding", "understanding_advance", true)
        @Expect(stage, "teach_back")
        stage = transitionTutorStage(stage, "teach_back_pass", false)
        @Expect(stage, "near_transfer")
        stage = transitionTutorStage(stage, "near_pass", false)
        @Expect(stage, "far_transfer")
        @Expect(transitionTutorStage(stage, "far_pass", false), "finished")
    }

    @TestCase
    func failuresRetainStage() {
        for ((stage, event) in [("teach_back", "teach_back_fail"),
            ("near_transfer", "near_fail"), ("far_transfer", "far_fail")]) {
            @Expect(transitionTutorStage(stage, event, false), stage)
        }
    }

    @TestCase
    func rejectMissingEvidenceAndSkippedStages() {
        for ((stage, event, passed) in [("understanding", "understanding_advance", false),
            ("understanding", "far_pass", true), ("finished", "near_pass", true),
            ("teach_back", "understanding_advance", true)]) {
            var rejected = false
            try {
                transitionTutorStage(stage, event, passed)
            } catch (_: IllegalArgumentException) {
                rejected = true
            }
            @Expect(rejected, true)
        }
    }

    @TestCase
    func legacySessionsAndBacktracking() {
        @Expect(canonicalTutorStage("teach_back_retry"), "teach_back")
        @Expect(canonicalTutorStage("near_remediation"), "near_transfer")
        @Expect(canonicalTutorStage("transfer_insufficient"), "far_transfer")
        @Expect(canonicalTutorStage("unknown"), "understanding")
        @Expect(previousTutorStage("teach_back"), "understanding")
        @Expect(previousTutorStage("near_transfer"), "teach_back")
        @Expect(previousTutorStage("far_transfer"), "near_transfer")
        var rejected = false
        try {
            previousTutorStage("finished")
        } catch (_: IllegalArgumentException) {
            rejected = true
        }
        @Expect(rejected, true)
    }
}
