"""Do not turn different explanation lengths into student mistakes."""

import asyncio

import diagnosis_compute as compute
import pytest
from app.schemas import DiagnosisOutput
from app.services.ai_pipeline import diagnose_steps
from diagnosis_compute import StepRecord


@pytest.mark.parametrize(
    "subject,text,steps,index,kind",
    [
        (
            "英语",
            "She ___ to school every day.",
            ["第三人称单数填goes。"],
            None,
            "exact",
        ),
        ("生物", "光合作用的气体交换", ["吸收二氧化碳，释放氧气。"], None, "exact"),
        ("物理", "72km/h行驶10秒的路程", ["s=vt", "s=72*10=720m"], 1, "unit_error"),
        (
            "数学",
            "解方程：sqrt(x+2)=x",
            ["x+2=x^2", "x=-1或x=2"],
            1,
            "condition_omission",
        ),
    ],
)
def test_semantic_location_uses_actual_student_rows_without_false_proof(
    monkeypatch, subject, text, steps, index, kind
):
    async def diagnose(*args, **kwargs):
        return DiagnosisOutput(first_error_step=index, error_type=kind)

    async def repair(*args, **kwargs):
        rows = kwargs["alignment"]
        assert len(rows) == len(steps)
        assert not any(row["math_valid"] for row in rows)
        assert not any(row["reference_step_id"] for row in rows)
        assert [row["index"] for row in rows if row["is_first_error"]] == (
            [] if index is None else [index]
        )
        return {
            "status": "confirmed" if index is not None else "not_needed",
            "root_cause_confirmed": index is not None,
        }

    monkeypatch.setattr(compute, "diagnose_steps", diagnose)
    monkeypatch.setattr(compute, "validate_first_error_counterfactual", repair)
    result = asyncio.run(
        compute.compute_diagnosis(
            None,
            text=text,
            subject=subject,
            question_type="综合题",
            student_answer="测试答案",
            options=[],
            references=[StepRecord(id="r", text="分成更多行、不同措辞的参考解释。")],
            students=[
                StepRecord(id=f"s{i}", text=value) for i, value in enumerate(steps)
            ],
            images=[],
        )
    )
    assert result["diagnosis"]["first_error_step"] == index
    assert not result["counterfactual"]["root_cause_confirmed"]
    if index is not None:
        assert result["diagnosis"]["first_error_text"] == steps[index]
        assert result["counterfactual"]["status"] == "inconclusive"


@pytest.mark.parametrize(
    "index,kind,expected",
    [
        (1, "unit_error", 1),
        (99, "unit_error", None),
        (0, "exact", None),
        (None, "unknown", None),
    ],
)
def test_pipeline_keeps_semantic_location_and_rejects_invented_steps(
    index, kind, expected
):
    class Provider:
        async def generate_structured(self, prompt, schema):
            return DiagnosisOutput(
                first_error_step=index,
                first_error_text="模型虚构的文本",
                error_type=kind,
            )

    result = asyncio.run(
        diagnose_steps(
            Provider(),
            "物理题",
            ["先换单位", "再代公式", "计算"],
            ["s=vt", "s=72*10"],
            "物理",
        )
    )
    assert result.first_error_step == expected
    assert result.first_error_text == ("s=72*10" if expected == 1 else "")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("missing_verification", "condition_omission"),
        ("missing_condition_check", "condition_omission"),
        ("incomplete_solution", "condition_omission"),
        ("invalid_assumption", "reasoning_gap"),
        ("unit_mismatch", "unit_error"),
        ("conceptual_error", "concept_error"),
        ("invented_category", "unknown"),
    ],
)
def test_model_categories_remain_compatible_with_manual_confirmation(raw, expected):
    class Provider:
        async def generate_structured(self, prompt, schema):
            return DiagnosisOutput(first_error_step=0, error_type=raw)

    result = asyncio.run(diagnose_steps(Provider(), "题目", ["参考"], ["学生作答"]))
    assert result.error_type == expected
