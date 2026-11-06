package zhiwei

import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class TutorPolicyTest {
    @TestCase
    func shortQuestionsAndMissingWork() {
        for (kind in ["choice", "单选题", "选择题", "multiple_choice", "multiple-choice", "多选题", "填空题"]) {
            let policy = adaptiveTeachingPolicy(kind, false, true, "A")
            @Expect(jsonText(policy, "mode"), "compressed")
            @Expect(policy["skip_teach_back"].toString(), "true")
            @Expect(policy["max_understanding_checks"].toString(), "1")
        }
        for (hasWorking in [true, false]) {
            let policy = adaptiveTeachingPolicy("证明题", false, hasWorking, "成立")
            @Expect(jsonText(policy, "mode"), if (hasWorking) { "full" } else { "compressed" })
            @Expect(policy["has_working"].toString(), if (hasWorking) { "true" } else { "false" })
        }
    }

    @TestCase
    func missingAnswersNeverSkipLearningGates() {
        for (kind in ["choice", "proof", "other"]) {
            for (hasWorking in [true, false]) {
                let policy = adaptiveTeachingPolicy(kind, true, hasWorking, "　\t\n")
                @Expect(jsonText(policy, "mode"), "full")
                @Expect(policy["show_answer_immediately"].toString(), "false")
                @Expect(policy["skip_teach_back"].toString(), "false")
                @Expect(policy["skip_far_transfer"].toString(), "false")
                @Expect(policy["max_understanding_checks"].toString(), "3")
            }
        }
    }

    @TestCase
    func normalizeLegacyQuestionTypes() {
        for (kind in ["", "other", "综合题"]) {
            @Expect(normalizedTutorQuestionType(kind, true), "choice")
        }
        @Expect(normalizedTutorQuestionType("　CHOICE　", false), "choice")
        @Expect(normalizedTutorQuestionType("", false), "other")
        @Expect(normalizedTutorQuestionType("计算题", true), "calculation")
        @Expect(normalizedTutorQuestionType("主观题", false), "subjective")
        @Expect(normalizedTutorQuestionType("custom", true), "custom")
    }

    @TestCase
    func onlyProgressIsPublic() {
        let state = (JsonValue.fromStr(##"{"understood":false,"understanding_passed":true,"teach_back":null,"understanding_index":0,"question_changed":true,"understanding_plan":[{"correct_answers":["secret"]}],"teaching_brief":{"check":{"correct_answers":["secret"]}},"retrieved_solution":"secret","future_private_field":"secret"}"##) as JsonObject).getOrThrow()
        let expected = JsonValue.fromStr(##"{"understood":false,"understanding_passed":true,"teach_back":null,"understanding_index":0,"question_changed":true}"##)
        @Expect(jsonEquivalent(publicTutorProgress(state), expected), true)
        @Expect(state.getFields().contains("understanding_plan"), true)
        @Expect(publicTutorProgress(JsonObject()).getFields().size, 0)
    }
}
