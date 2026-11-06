import asyncio
import json

import pytest
from pydantic import ValidationError

from grading_compute import UnavailableGradingProvider
from learning_hint_compute import GuidedHint, HintDraft
from learning_task_compute import (
    Checkpoint,
    SupportPlan,
    TaskAction,
    TaskContext,
    execute_task,
)

QUESTION = r"若不论k为何值，直线$y=k(x-1)-\frac{k^2}{4}$与抛物线$y=ax^2+bx+c$有且仅有一个公共点，求a、b、c。"


def context(**changes):
    return TaskContext(
        **(
            {
                "question_id": "q-hint",
                "question_text": QUESTION,
                "expected": "a=1,b=-2,c=1",
                "reference_steps": ["联立方程，按二次项是否为零分类讨论。"],
                "subject": "数学",
            }
            | changes
        )
    )


def run(state=None, provider=None, text="先联立方程吗", ctx=None, kind="hint"):
    return asyncio.run(
        execute_task(
            provider or UnavailableGradingProvider(),
            ctx or context(),
            state or Checkpoint(phase="independent"),
            TaskAction(kind=kind, text=text),
        )
    )


class Teacher:
    def __init__(self, hints=None):
        self.inputs = []
        self.hints = hints or [
            "先将两个函数的表达式联立。题目强调‘不论k为何值’，你需要保留k并研究交点对应的根。",
            "把联立后的式子整理为关于x的方程。先检查二次项系数是否为零，再讨论二次情形的判别式。",
            "二次情形中，把判别式写成k的多项式；要让它对所有k都为零，各次项的系数应满足什么关系？退化情形也要检查是否仍只有一个交点。",
        ]

    async def generate_structured(self, prompt, schema, **kwargs):
        if schema is SupportPlan:
            return SupportPlan(
                goal="核对交点关系",
                tool_name="step_alignment",
                decision_summary="根据当前交点条件逐步提示",
            )
        self.inputs.append(json.loads(prompt))
        return GuidedHint(
            connection=self.hints[min(len(self.inputs) - 1, len(self.hints) - 1)],
            next_step=[
                "公共点同时满足哪两个方程？",
                "整理后的二次项系数是多少？",
                "恒等于零时，k的每次项系数应满足什么关系？",
            ][min(len(self.inputs) - 1, len(self.hints) - 1, 2)],
            source_quote="有且仅有一个公共点",
        )


def test_complex_question_receives_progressive_draft_aware_hints_and_stops_at_three():
    teacher = Teacher()
    state = Checkpoint(phase="independent")
    hints = []
    for level in range(1, 4):
        result = run(state, teacher)
        hints.append(result.student_view.feedback)
        assert result.student_view.hint_level == level
        assert result.checkpoint.assistance["independent"]
        assert result.attempt is None and not result.learning_eligible
        assert result.checkpoint.phase == "independent"
        assert teacher.inputs[-1]["student_draft"] == "先联立方程吗"
        assert teacher.inputs[-1]["previous_hints"] == hints[:-1]
        assert teacher.inputs[-1]["hint_level"] == level
        state = Checkpoint.model_validate_json(result.checkpoint.model_dump_json())
    assert len(set(hints)) == 3
    assert "hint" not in result.student_view.secondary_actions
    assert "reveal" in result.student_view.secondary_actions
    again = run(state, teacher)
    assert len(teacher.inputs) == 3
    assert again.student_view.feedback == hints[-1]


@pytest.mark.parametrize(
    "bad,quote",
    [
        ("先核对题目条件与参考知识，再说明你使用的依据。", "有且仅有一个公共点"),
        ("令判别式为零，最后得到a=1,b=-2,c=1。", "有且仅有一个公共点"),
        ("先假设图中这两个角相等，再列出关系。", "不存在的条件"),
        ("正确答案是B，你直接选择即可。", "有且仅有一个公共点"),
    ],
)
def test_invalid_hints_are_not_shown_or_consumed(bad, quote):
    class Invalid(Teacher):
        async def generate_structured(self, prompt, schema, **kwargs):
            if schema is SupportPlan:
                return await super().generate_structured(prompt, schema, **kwargs)
            return GuidedHint(
                connection=bad,
                next_step="你能先写出这一步对应的关系式吗？",
                source_quote=quote,
            )

    result = run(provider=Invalid())
    assert bad not in result.student_view.feedback
    assert "没能生成" in result.student_view.feedback
    assert result.student_view.hint_level == 0
    assert "hint" in result.student_view.secondary_actions
    assert result.traces[-1].evidence["hint_source"] == "hint_invalid"


def test_failed_provider_is_explicit_and_does_not_consume_hint_level():
    result = run()
    assert "没能生成" in result.student_view.feedback
    assert "先核对题目条件与参考知识" not in result.student_view.feedback
    assert result.student_view.hint_level == 0
    assert result.traces[-1].evidence["hint_source"] == "hint_unavailable"


def test_repeated_hint_is_rejected_but_retry_remains_available():
    teacher = Teacher(hints=[Teacher().hints[0]])
    first = run(provider=teacher)
    second = run(first.checkpoint, teacher)
    assert second.student_view.hint_level == 1
    assert len(second.checkpoint.hints["independent"]) == 1
    assert "没能生成" in second.student_view.feedback


def test_linear_hints_are_symbolically_bound_to_current_phase_and_legacy_state():
    ctx = context(
        question_text="解方程：2x+3=11", expected="x=4", student_steps=["2x=11+3"]
    )
    state = Checkpoint.model_validate({"phase": "repair"})
    for level in range(3):
        result = run(state, ctx=ctx, text="")
        assert result.student_view.hint_level == level + 1
        assert "2 x + 3=11" in result.student_view.feedback
        assert "x=4" not in result.student_view.feedback
        assert result.traces[-1].evidence["hint_source"] == "symbolic_linear_hint"
        state = result.checkpoint
    # A new step starts at level zero, while earlier assistance remains recorded.
    next_step = run(state, ctx=ctx, kind="answer", text="2x=8")
    assert next_step.checkpoint.phase == "independent"
    assert next_step.student_view.hint_level == 0
    assert "hint" in next_step.student_view.secondary_actions
    assert next_step.checkpoint.assistance["repair"]


def test_checkpoint_rejects_unbounded_hint_history():
    with pytest.raises(ValidationError):
        Checkpoint(hints={"independent": ["提示"] * 4})


def test_contrast_hint_uses_contrast_question_not_original_references():
    from learning_task_compute import make_contrast

    ctx = context(question_text="解方程：2x+3=11", expected="x=4")
    contrast = make_contrast(ctx)
    result = run(Checkpoint(phase="contrast", contrast=contrast), ctx=ctx, text="")
    assert result.student_view.hint_level == 1
    assert result.checkpoint.assistance["contrast"]
    assert "2 x - 3=11" in result.student_view.feedback


def test_last_submitted_draft_is_used_when_current_input_is_empty():
    teacher = Teacher()
    state = Checkpoint(
        phase="independent", last_answers={"independent": "联立后是不是要计算判别式"}
    )
    result = run(state, teacher, text="")
    assert teacher.inputs[-1]["student_draft"] == "联立后是不是要计算判别式"
    assert result.student_view.hint_level == 1


def test_hint_generation_timeout_does_not_consume_level(monkeypatch):
    import learning_hint_compute

    monkeypatch.setattr(learning_hint_compute, "HINT_TIMEOUT_SECONDS", 0.01)

    class SlowTeacher(Teacher):
        async def generate_structured(self, prompt, schema, **kwargs):
            if schema is SupportPlan:
                return await super().generate_structured(prompt, schema, **kwargs)
            await asyncio.sleep(1)

    result = run(provider=SlowTeacher())
    assert result.student_view.hint_level == 0
    assert result.traces[-1].evidence["hint_source"] == "hint_timeout"
    assert "没能生成" in result.student_view.feedback


def test_compute_http_contract_roundtrips_hints_without_external_provider(tmp_path):
    from fastapi.testclient import TestClient

    from service import create_app

    secret = "hint-test-secret-" * 3
    app = create_app(secret=secret, pool_path=tmp_path / "absent.json")

    class LocalTeacher(Teacher):
        async def close(self):
            pass

    with TestClient(app) as client:
        app.state.provider = LocalTeacher()
        checkpoint = {"phase": "independent"}
        for level in range(1, 4):
            reply = client.post(
                "/v1/compute",
                headers={"Authorization": "Bearer " + secret},
                json={
                    "operation": "learning_task",
                    "task_context": context().model_dump(mode="json"),
                    "task_checkpoint": checkpoint,
                    "task_action": {"kind": "hint", "text": "联立方程吗第一步"},
                },
            )
            assert reply.status_code == 200
            result = reply.json()["result"]
            checkpoint = result["checkpoint"]
            assert result["student_view"]["hint_level"] == level
            assert not result["learning_eligible"] and result["attempt"] is None
        assert "hint" not in result["student_view"]["secondary_actions"]


def test_linear_without_constant_does_not_ask_to_remove_zero():
    ctx = context(question_text="解方程：3x=12", expected="x=4")
    result = run(ctx=ctx, text="")
    assert "系数" in result.student_view.feedback
    assert "消去常数项" not in result.student_view.feedback
    assert "x=4" not in result.student_view.feedback


def test_numeric_final_answer_is_not_returned_as_a_hint():
    from learning_hint_compute import validate_hint

    with pytest.raises(ValueError, match="numeric result"):
        validate_hint(
            HintDraft(
                hint="先检查计算过程，得到x=4后代回原式即可。",
                source_quote="有且仅有一个公共点",
            ),
            question=QUESTION,
            expected="4",
            previous=[],
        )


def test_linear_hint_continues_from_verified_draft():
    ctx = context(question_text="解方程：2x+3=11", expected="x=4")
    state = Checkpoint(phase="independent")
    feedback = []
    for level in range(1, 4):
        result = run(state, ctx=ctx, text="2x=8")
        feedback.append(result.student_view.feedback)
        assert result.student_view.hint_level == level
        assert "x=4" not in result.student_view.feedback
        state = result.checkpoint
    assert "草稿已消去常数项" in feedback[0]
    assert len(set(feedback)) == 3


def test_linear_wrong_draft_explains_equality_instead_of_advancing():
    result = run(ctx=context(question_text="解方程：2x+3=11", expected="x=4"), text="2x=14")
    assert "与原式解不同" in result.student_view.feedback
    assert "相同运算" in result.student_view.feedback
    assert result.attempt is None


def test_guided_schema_requires_reason_and_answerable_question():
    with pytest.raises(ValidationError):
        GuidedHint(source_quote="公共点", connection="想一想", next_step="怎么做？")
    with pytest.raises(ValueError, match="concrete question"):
        GuidedHint(source_quote="公共点", connection="公共点的坐标需要同时满足两个函数表达式。", next_step="认真思考然后继续计算下去。").as_draft()


def test_generic_advice_is_rejected_even_with_valid_source():
    from learning_hint_compute import validate_hint
    with pytest.raises(ValueError, match="generic"):
        validate_hint(HintDraft(source_quote="公共点", hint="认真审题，回顾所学知识后套用相关公式。"), question=QUESTION, expected="", previous=[])


def test_same_question_is_rejected_even_when_explanation_changes():
    from learning_hint_compute import validate_hint
    with pytest.raises(ValueError, match="repeated"):
        validate_hint(
            HintDraft(source_quote="公共点", hint="这里先考虑公共点的两个坐标，它们分别满足题中两条关系。\n\n请写出消去y之后的方程是什么？"),
            question=QUESTION, expected="", previous=["一个交点同时在两条曲线上。\n\n请写出消去y之后的方程是什么？"],
        )


def test_invalid_candidate_is_rewritten_once_before_consuming_level():
    teacher = Teacher(hints=["认真审题，回顾所学知识后套用相关公式。", Teacher().hints[1]])
    result = run(provider=teacher)
    assert len(teacher.inputs) == 2
    assert "revision_instruction" in teacher.inputs[1]
    assert result.student_view.hint_level == 1
    assert len(result.checkpoint.hints["independent"]) == 1
