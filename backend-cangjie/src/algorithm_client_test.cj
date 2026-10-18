package zhiwei

import std.fs.*
import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class AlgorithmClientTest {
    @TestCase
    func realPythonMathService() {
        let input = (JsonValue.fromStr(##"{"operation":"math_compare","left":"2*(x+1)","right":"2*x+2"}"##) as JsonObject).getOrThrow()
        let result = algorithmCompute(input)
        @Expect(result["equivalent"].toString(), "true")
        @Expect(result["verified"].toString(), "true")
        let solve = (JsonValue.fromStr(##"{"operation":"math_solve","text":"解方程：2*x+3=11"}"##) as JsonObject).getOrThrow()
        @Expect(jsonText(algorithmCompute(solve), "answer"), "x=4")
    }

    @TestCase
    func analysisBoundaryValidation() {
        let input = JsonObject()
        input.put("operation", JsonString("analyze"))
        input.put("text", JsonString(""))
        var invalid = false
        try { algorithmCompute(input) } catch (error: ApiError) { invalid = error.status == 422 }
        @Expect(invalid, true)
        input.put("text", JsonString("说明物体受力情况"))
        input.put("subject", JsonString("物理"))
        var unavailable = false
        try { algorithmCompute(input) } catch (error: ApiError) { unavailable = error.status == 503 }
        @Expect(unavailable, true)
    }

    @TestCase
    func diagnosisBoundaryValidation() {
        for (operation in ["diagnose", "counterfactual", "generate_variant"]) {
            let input = JsonObject()
            input.put("operation", JsonString(operation)); input.put("text", JsonString(""))
            var invalid = false
            try { algorithmCompute(input) } catch (error: ApiError) { invalid = error.status == 422 }
            @Expect(invalid, true)
            input.put("text", JsonString("解方程 x+1=2"))
            var unavailable = false
            try { algorithmCompute(input) } catch (error: ApiError) { unavailable = error.status == 503 }
            @Expect(unavailable, true)
        }
    }

    @TestCase
    func teachingBriefBoundaryValidation() {
        let input = JsonObject()
        input.put("operation",JsonString("teaching_brief"))
        input.put("text",JsonString("哪个数没有倒数？"))
        var invalid = false
        try { algorithmCompute(input) } catch (error: ApiError) { invalid = error.status == 422 }
        @Expect(invalid,true)
        input.put("correct_answer",JsonString("0"))
        var unavailable = false
        try { algorithmCompute(input) } catch (error: ApiError) { unavailable = error.status == 503 }
        @Expect(unavailable,true)
    }

    @TestCase
    func answerGradingWithoutModelPool() {
        let input = (JsonValue.fromStr(##"{"operation":"grade_answer","text":"解方程 x+1=2","answer":"x=1","expected":"x=1","question_type":"short_answer"}"##) as JsonObject).getOrThrow()
        let correct = algorithmCompute(input)
        @Expect(correct["correct"].toString(),"true")
        @Expect(correct["can_update_learning"].toString(),"true")
        input.put("answer",JsonString("x=3"))
        let wrong = algorithmCompute(input)
        @Expect(wrong["correct"].toString(),"false")
        @Expect(wrong["can_update_learning"].toString(),"true")
        input.put("expected",JsonNull())
        var invalid = false
        try { algorithmCompute(input) } catch (error: ApiError) { invalid = error.status == 422 }
        @Expect(invalid,true)
    }

    @TestCase
    func realImageProcessingAndErrors() {
        let input = (JsonValue.fromStr(String.fromUtf8(File.readFrom("tests/algorithm_image.json"))) as JsonObject).getOrThrow()
        let result = algorithmCompute(input)
        @Expect(jsonText(result, "kind"), "crop")
        let geometry = (result["geometry"] as JsonObject).getOrThrow()
        @Expect(geometry["width"].toString(), "50")
        @Expect(geometry["height"].toString(), "40")
        @Expect(jsonText(result, "sha256").size, 64)
        input.put("operation", JsonString("recognize"))
        var unavailable = false
        try { algorithmCompute(input) } catch (error: ApiError) { unavailable = error.status == 503 }
        @Expect(unavailable, true)
        input.put("image_base64", JsonString("invalid"))
        var invalid = false
        try { algorithmCompute(input) } catch (error: ApiError) { invalid = error.status == 422 }
        @Expect(invalid, true)
    }
}
