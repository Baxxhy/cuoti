import asyncio

import pytest
from grading_compute import UnavailableGradingProvider
from learning_task_compute import (
    Checkpoint,
    SupportPlan,
    TaskAction,
    TaskContext,
    execute_task,
    make_contrast,
)
from pydantic import ValidationError


def context(**extra):
    return TaskContext(
        **(
            {
                "question_id": "q1",
                "subject": "数学",
                "question_text": "解方程：2x+3=17",
                "expected": "x=7",
                "student_steps": ["2x=17+3", "x=10"],
            }
            | extra
        )
    )


def run(state=None, kind="visualize", text="", values=None, ctx=None, provider=None):
    return asyncio.run(
        execute_task(
            provider or UnavailableGradingProvider(),
            ctx or context(),
            state or Checkpoint(),
            TaskAction(kind=kind, text=text, visual_values=values or {}),
        )
    )


def test_source_bound_balance_observe_close_reopen_without_grading():
    opened = run()
    visual = opened.student_view.visualization
    assert visual.spec.parameters["right"] == 17 and "17" in visual.source_equation_tex
    assert visual.values == {"delta": 0} and visual.spec.parameters["task_bound"]
    assert opened.checkpoint.assistance["repair"] and not opened.learning_eligible
    observed = run(
        opened.checkpoint, "observe_visualization", "我已经会了", {"delta": 3}
    )
    assert (
        observed.checkpoint.phase == "repair" and not observed.checkpoint.repair_passed
    )
    assert observed.attempt is None and not observed.learning_eligible
    assert observed.student_view.visualization.observation == "我已经会了"
    assert "14" in observed.student_view.visualization.current_equation_tex
    closed = run(observed.checkpoint, "close_visualization")
    assert (
        closed.student_view.visualization is None
        and closed.checkpoint.assistance["repair"]
    )
    reopened = run(closed.checkpoint)
    assert reopened.student_view.visualization.values == {"delta": 3}
    assert reopened.student_view.visualization.observation == "我已经会了"
    repaired = run(reopened.checkpoint, "answer", "2x=14")
    assert (
        repaired.checkpoint.phase == "independent"
        and repaired.student_view.visualization is None
    )
    assert not repaired.learning_eligible


@pytest.mark.parametrize(
    "text,kind",
    [
        ("函数：y=2x+1", "linear_function"),
        ("y=x^2+2x+1", "quadratic_function"),
        ("y=(x-2)^2-1", "quadratic_function"),
        ("y=100x+1", "linear_function"),
        ("y=2x+5", "linear_function"),
        ("y=0.5x+1.25", "linear_function"),
        ("y=x/3+1", "linear_function"),
        ("y=2(x-1000)^2+1000", "quadratic_function"),
    ],
)
def test_functions_bind_original_parameters(text, kind):
    ctx = context(question_text=text, expected="给定的函数", student_steps=[])
    opened = run(ctx=ctx)
    assert opened.student_view.visualization.spec.type == kind
    assert opened.student_view.visualization.scope == "function_expression"
    assert opened.checkpoint.assistance["independent"]
    assert opened.attempt is None and not opened.learning_eligible


@pytest.mark.parametrize(
    "text",
    [
        "已知2x+3=17，求x²",
        "y=x/x+x",
        "y=x**(-1)*x+x",
        "y=x+1，x>0",
        "y=sin(x)",
        "y=x^3",
        "y=100000x+1",
    ],
)
def test_unsupported_conditions_do_not_become_a_different_problem(text):
    ctx = context(question_text=text, expected="未知", student_steps=[])
    result = run(ctx=ctx)
    assert result.student_view.visualization is None
    assert result.traces[0].validation == "rejected"
    assert not result.learning_eligible and not result.checkpoint.assistance


@pytest.mark.parametrize(
    "values", [{"delta": 1.5}, {"delta": 100}, {"k": 1}, {"delta": float("nan")}]
)
def test_invalid_controls_are_rejected(values):
    state = run().checkpoint
    with pytest.raises((ValueError, ValidationError)):
        run(state, "observe_visualization", "观察", values)


def test_visualized_contrast_is_assisted_and_forged_source_rejected():
    ctx = context()
    state = Checkpoint(phase="contrast", contrast=make_contrast(ctx))
    opened = run(state, ctx=ctx)
    assert opened.checkpoint.assistance["contrast"]
    done = run(opened.checkpoint, "answer", "x=10", ctx=ctx)
    assert done.status == "completed" and not done.learning_eligible
    opened.checkpoint.visualization.source_question_id = "foreign"
    with pytest.raises(ValueError, match="source"):
        run(
            opened.checkpoint,
            "observe_visualization",
            "关系不变",
            {"delta": 0},
            ctx=ctx,
        )


def test_planner_can_choose_visual_tool_and_replans_when_not_applicable():
    class Planner:
        async def generate_structured(self, *args, **kwargs):
            return SupportPlan(
                goal="看清等式关系",
                tool_name="visualization",
                decision_summary="当前卡点适合用图看同操作",
            )

    supported = run(kind="answer", text="2x=20", provider=Planner())
    assert [trace.tool_name for trace in supported.traces] == [
        "check_step",
        "visualization",
    ]
    assert (
        supported.traces[-1].planner_source == "model"
        and supported.checkpoint.visual_open
    )
    unsupported = run(
        kind="hint",
        ctx=context(
            subject="语文",
            question_text="文章的主题是什么",
            expected="友情",
            student_steps=[],
        ),
        provider=Planner(),
    )
    assert [trace.tool_name for trace in unsupported.traces] == [
        "visualization",
        "step_alignment",
    ]
    assert (
        unsupported.traces[0].validation == "rejected"
        and unsupported.traces[1].planner_source == "verification"
    )
    assert unsupported.student_view.visualization is None


def test_zero_quadratic_parameter_is_labelled_as_degenerate():
    ctx = context(question_text="y=x^2", expected="函数", student_steps=[])
    state = run(ctx=ctx).checkpoint
    result = run(
        state, "observe_visualization", "变成直线", {"a": 0, "h": 0, "k": 0}, ctx=ctx
    )
    assert result.student_view.visualization.current_equation_tex == "y=0"
    assert (
        "不再是二次函数" in result.student_view.visualization.spec.expected_observation
    )


def test_python_visual_protocol_rejects_boolean_controls():
    with pytest.raises(ValidationError):
        TaskAction(
            kind="observe_visualization", text="观察", visual_values={"delta": True}
        )


def test_controls_keep_exact_fraction_source_and_large_values_do_not_break_task():
    ctx = context(question_text="y=x/3+1", expected="函数", student_steps=[])
    opened = run(ctx=ctx)
    packet = opened.student_view.visualization
    assert "3" in packet.source_equation_tex
    assert packet.source_equation_tex == packet.current_equation_tex
    values = dict(packet.values)
    v = packet.spec.interactive_variables[0]
    values[v.name] = v.min + (round((values[v.name] - v.min) / v.step) + 1) * v.step
    saved = run(opened.checkpoint, "observe_visualization", "斜率改变", values, ctx=ctx)
    assert saved.student_view.visualization.values == values
    for text in ["y=1000000x+1", "y=(x-1000000)^2", "2x+3=1000000000000"]:
        result = run(ctx=context(question_text=text, expected="未知", student_steps=[]))
        assert result.student_view.visualization is None


def test_constant_linear_contrast_is_labelled_and_review_can_still_offer_visuals():
    ctx = context(question_text="y=x+1", expected="函数", student_steps=[])
    opened = run(ctx=ctx)
    v = opened.student_view.visualization.spec.interactive_variables[0]
    assert v.min <= 0 <= v.max
    assert (
        "不再是一次函数" in opened.student_view.visualization.spec.expected_observation
    )
    result = run(Checkpoint(phase="independent", attempts=3), "answer", "未知", ctx=ctx)
    assert (
        result.status == "needs_review"
        and "visualize" in result.student_view.secondary_actions
    )
