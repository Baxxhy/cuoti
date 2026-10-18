from app.providers.api_pool import ApiPoolUnavailable
from app.schemas import AnalysisOutput, DiagnosisOutput
from fastapi.testclient import TestClient
from service import create_app

SECRET = "inequality-test-" + "x" * 32
QUESTION = "解不等式：x^2-5x+6≤0，写出解集。"


def test_internal_analysis_diagnosis_repair_and_grading_use_the_original_set(
    monkeypatch, tmp_path
):
    import diagnosis_compute
    import service

    async def analysis(*args, **kwargs):
        return AnalysisOutput(
            subject="数学",
            problem_type="综合题",
            final_answer="x<=2或x>=3",
            reference_steps=["观察开口与零点等参考说明", "(x-2)(x-3)<=0", "2<=x<=3"],
        )

    async def diagnosis(*args, **kwargs):
        return DiagnosisOutput(
            first_error_step=0,
            first_error_text="模型按行号选了错误位置",
            error_type="sign_error",
            root_misconception="区间选择需要核对",
        )

    async def repair(*args, **kwargs):
        return {
            "root_cause_confirmed": True,
            "corrected_step": "2<=x<=3",
            "repaired_steps": ["(x-2)(x-3)<=0", "2<=x<=3"],
            "status": "confirmed",
        }

    monkeypatch.setattr(service, "analyze_question", analysis)
    monkeypatch.setattr(diagnosis_compute, "diagnose_steps", diagnosis)
    monkeypatch.setattr(
        diagnosis_compute, "validate_first_error_counterfactual", repair
    )
    app = create_app(secret=SECRET, pool_path=tmp_path / "missing.json")

    class NoModelProvider:
        async def close(self):
            return None

    app.state.provider = NoModelProvider()
    with TestClient(app) as client:

        def compute(operation, **kwargs):
            response = client.post(
                "/v1/compute",
                headers={"Authorization": "Bearer " + SECRET},
                json={
                    "operation": operation,
                    "text": QUESTION,
                    "subject": "数学",
                    "question_type": "综合题",
                    **kwargs,
                },
            )
            assert response.status_code == 200
            return response.json()["result"]

        value = compute("analyze")
        assert value["analysis"]["answer_verified"]
        assert value["analysis"]["final_answer"] == "x ∈ [2, 3]"
        assert value["reference_math_valid"] == [False, True, True]
        value = compute(
            "diagnose",
            student_records=[
                {"id": "s-0", "text": "(x-2)(x-3)<=0"},
                {"id": "s-1", "text": "x<=2或x>=3"},
            ],
            student_answer="x<=2或x>=3",
            reference_steps=[{"id": "r-0", "text": "先找零点，再判断范围。"}],
        )
        assert value["diagnosis"]["first_error_step"] == 1
        assert (
            value["alignment"][0]["math_valid"]
            and not value["alignment"][0]["is_first_error"]
        )
        assert value["counterfactual"]["root_cause_confirmed"]
        assert (
            value["counterfactual"]["validation_scope"]
            == "polynomial_inequality_solution_set_and_preserved_prefix"
        )
        value = compute("grade_answer", answer="2<=x<=3", expected="x ∈ [2, 3]")
        assert value["verdict"] == "confirmed_correct" and value["can_update_learning"]
        value = compute("grade_answer", answer="(2,3)", expected="x ∈ [2, 3]")
        assert value["verdict"] == "confirmed_incorrect"
        value = compute("grade_answer", answer="(x-2)(x-3)<=0", expected="x ∈ [2, 3]")
        assert (
            value["verdict"] == "review_required" and not value["can_update_learning"]
        )
        value = compute("grade_answer", answer="[2,3]", expected="x<=2或x>=3")
        assert (
            value["verdict"] == "review_required" and not value["can_update_learning"]
        )
        value = compute(
            "diagnose",
            student_records=[
                {"id": "s-0", "text": "(x-2)(x-3)<=0"},
                {"id": "s-1", "text": "2<=x<=3"},
            ],
            student_answer="[2,3]",
        )
        assert (
            value["diagnosis"]["error_type"] == "exact"
            and value["diagnosis"]["first_error_step"] is None
        )

        async def unavailable(*args, **kwargs):
            raise ApiPoolUnavailable("测试上游不可用")

        monkeypatch.setattr(service, "analyze_question", unavailable)
        value = compute("analyze")
        assert (
            value["analysis"]["answer_verified"]
            and value["analysis"]["final_answer"] == "x ∈ [2, 3]"
        )
