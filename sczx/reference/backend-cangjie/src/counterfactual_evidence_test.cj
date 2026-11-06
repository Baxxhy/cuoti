package zhiwei

import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class CounterfactualEvidenceTest {
    @TestCase
    func legacyReferenceIsNotSymbolicProof() {
        let result=(safeCounterfactual(JsonValue.fromStr(##"{"root_cause_confirmed":true,"status":"confirmed","verification_method":"qwen_proposal_sympy_check","confidence":0.95}"##)) as JsonObject).getOrThrow()
        @Expect(tutorFlag(result,"root_cause_confirmed"),false)
        @Expect(tutorFlag(result,"legacy_review_required"),true)
        @Expect(tutorText(result,"verification_method"),"legacy_reference_alignment")
    }

    @TestCase
    func sourceVerifiedAndCurrentEvidenceRetained() {
        for (text in [
            ##"{"root_cause_confirmed":true,"verification_method":"qwen_proposal_sympy_check","validation_scope":"polynomial_real_solution_set_and_preserved_prefix"}"##,
            ##"{"root_cause_confirmed":true,"verification_method":"qwen_proposal_sympy_check","preserved_prefix":true}"##
        ]) {
            let result=(safeCounterfactual(JsonValue.fromStr(text)) as JsonObject).getOrThrow()
            @Expect(tutorFlag(result,"root_cause_confirmed"),true)
            @Expect(tutorFlag(result,"legacy_review_required"),false)
        }
    }

    @TestCase
    func changedManualStepDoesNotReusePreviousProof() {
        let proof=##"{"root_cause_confirmed":true,"status":"confirmed","suspected_step":0,"verification_method":"qwen_proposal_sympy_check","validation_scope":"polynomial_real_solution_set_and_preserved_prefix"}"##
        let diagnosis=(JsonValue.fromStr(##"{"user_confirmed":true,"first_error_step":1}"##) as JsonObject).getOrThrow()
        let result=(safeCounterfactual(JsonValue.fromStr(proof),diagnosis:Some(diagnosis)) as JsonObject).getOrThrow()
        @Expect(tutorFlag(result,"root_cause_confirmed"),false)
        @Expect(tutorFlag(result,"stale_after_correction"),true)
        diagnosis.put("first_error_step",JsonInt(0))
        let same=(safeCounterfactual(JsonValue.fromStr(proof),diagnosis:Some(diagnosis)) as JsonObject).getOrThrow()
        @Expect(tutorFlag(same,"root_cause_confirmed"),true)
        diagnosis.put("first_error_step",JsonNull())
        let cleared=(safeCounterfactual(JsonValue.fromStr(proof),diagnosis:Some(diagnosis)) as JsonObject).getOrThrow()
        @Expect(tutorFlag(cleared,"root_cause_confirmed"),false)
    }
}
