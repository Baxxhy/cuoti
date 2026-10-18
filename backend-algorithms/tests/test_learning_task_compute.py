import asyncio
import base64
import io

import pytest
from grading_compute import UnavailableGradingProvider
from learning_task_compute import (
    Checkpoint,
    ContentBlock,
    SupportPlan,
    TaskAction,
    TaskContext,
    execute_task,
    linear_source,
    make_contrast,
    verify_contrast,
)
from PIL import Image
from pydantic import ValidationError


def context(**extra):
    values = {
        "question_id": "q1",
        "question_text": "解方程：2x+3=11",
        "expected": "x=4",
        "student_steps": ["2x=11+3", "x=7"],
        "reference_steps": ["2x=8", "x=4"],
        "knowledge_points": ["等式的性质"],
        "grade": "初一",
    }
    return TaskContext(**(values | extra))


def step(state=None, kind="start", text="", ctx=None, provider=None):
    return asyncio.run(
        execute_task(
            provider or UnavailableGradingProvider(),
            ctx or context(),
            state or Checkpoint(),
            TaskAction(kind=kind, text=text),
        )
    )


def test_local_correction_then_original_then_verified_single_condition():
    start = step()
    assert start.status == "waiting_student" and start.checkpoint.phase == "repair"
    corrected = step(start.checkpoint, "answer", "11-3")
    assert (
        corrected.checkpoint.repair_passed
        and corrected.checkpoint.phase == "independent"
    )
    assert (
        not corrected.learning_eligible and corrected.attempt["scope"] == "local_step"
    )
    original = step(corrected.checkpoint, "answer", "x=4")
    assert original.checkpoint.phase == "contrast" and not original.learning_eligible
    assert "expected" not in original.student_view.model_dump_json()
    assert original.checkpoint.contrast.expected == "x=7"
    assert verify_contrast(context(), original.checkpoint.contrast)
    completed = step(original.checkpoint, "answer", "x=7")
    assert completed.status == "completed" and completed.learning_eligible
    assert completed.checkpoint.contrast_passed
    assert step(completed.checkpoint, "answer", "x=7").learning_eligible is False


def test_handwriting_transcription_requires_student_confirmation_and_is_not_grading():
    class Reader:
        async def generate_multimodal(self, prompt, images, schema, **kwargs):
            assert "2x+3=11" in prompt and len(images) == 1
            return schema(
                final_answer="x=7",
                steps=["2x=14"],
                transcription="2x=14\nx=7",
                uncertain=True,
                confidence=0.4,
            )

    output = io.BytesIO()
    Image.new("RGB", (30, 20), "red").save(output, format="PNG")
    raw = output.getvalue()
    action = TaskAction(
        kind="recognize_handwriting",
        handwriting_id="photo-1",
        image_base64=base64.b64encode(raw).decode(),
    )
    recognized = asyncio.run(execute_task(Reader(), context(), Checkpoint(), action))
    assert (
        recognized.checkpoint.phase == "repair"
        and not recognized.checkpoint.repair_passed
    )
    assert recognized.attempt is None and not recognized.learning_eligible
    assert recognized.checkpoint.attempts == 0
    draft = recognized.student_view.handwriting
    assert draft.id == "photo-1" and draft.suggested_text == "2x=14"
    assert (
        draft.recognition.uncertain
        and recognized.traces[0].validation == "needs_review"
    )
    assert recognized.traces[0].scope.startswith("手写转写")
    with pytest.raises(ValueError, match="confirm"):
        asyncio.run(
            execute_task(
                Reader(),
                context(),
                recognized.checkpoint,
                TaskAction(
                    kind="answer",
                    text="2x=8",
                    handwriting_id="photo-1",
                    handwriting_recognition=draft.recognition,
                ),
            )
        )
    corrected = asyncio.run(
        execute_task(
            Reader(),
            context(),
            recognized.checkpoint,
            TaskAction(
                kind="answer",
                text="2x=8",
                handwriting_id="photo-1",
                handwriting_recognition=draft.recognition,
                handwriting_confirmed=True,
            ),
        )
    )
    assert (
        corrected.checkpoint.phase == "independent" and not corrected.learning_eligible
    )
    assert corrected.attempt["handwriting"] == {
        "id": "photo-1",
        "student_confirmed": True,
        "recognition_uncertain": True,
        "text_edited": True,
    }
    assert output.getvalue() == raw


@pytest.mark.parametrize(
    "image", ["not-base64!", base64.b64encode(b"not an image").decode()]
)
def test_invalid_handwriting_cannot_create_an_attempt(image):
    with pytest.raises(ValueError):
        asyncio.run(
            execute_task(
                UnavailableGradingProvider(),
                context(),
                Checkpoint(),
                TaskAction(
                    kind="recognize_handwriting",
                    handwriting_id="photo-1",
                    image_base64=image,
                ),
            )
        )


def test_empty_transcription_is_not_reported_as_verified_or_correct():
    class EmptyReader:
        async def generate_multimodal(self, prompt, images, schema, **kwargs):
            return schema()

    output = io.BytesIO()
    Image.new("RGB", (30, 20), "white").save(output, format="PNG")
    result = asyncio.run(
        execute_task(
            EmptyReader(),
            context(),
            Checkpoint(),
            TaskAction(
                kind="recognize_handwriting",
                handwriting_id="empty-photo",
                image_base64=base64.b64encode(output.getvalue()).decode(),
            ),
        )
    )
    assert not result.learning_eligible and result.attempt is None
    assert result.student_view.handwriting.suggested_text == ""
    assert result.student_view.handwriting.recognition.uncertain
    assert result.traces[0].validation == "needs_review"
    assert "没有识别到" in result.student_view.feedback


def test_incorrect_observation_causes_bounded_replan_after_zero_hit():
    result = step(kind="answer", text="2x=14")
    assert result.checkpoint.phase == "repair" and not result.learning_eligible
    assert [t.tool_name for t in result.traces] == [
        "check_step",
        "knowledge_search",
        "step_alignment",
    ]
    assert result.traces[1].validation == "rejected"
    assert result.traces[2].planner_source == "verification"
    assert result.attempt["verdict"] == "confirmed_incorrect"


def test_hint_exposure_on_contrast_prevents_independent_learning_update():
    state = Checkpoint(phase="contrast", contrast=make_contrast(context()))
    hinted = step(state, "hint")
    assert hinted.checkpoint.assistance["contrast"]
    done = step(hinted.checkpoint, "answer", "7")
    assert done.status == "completed" and not done.learning_eligible
    assert done.attempt["assisted"]


def test_reveal_is_explicit_and_never_automatically_counts_as_mastery():
    revealed = step(Checkpoint(phase="independent"), "reveal")
    assert "x=4" in revealed.student_view.feedback
    assert not revealed.learning_eligible and revealed.attempt is None
    checked = step(revealed.checkpoint, "answer", "x=4")
    assert checked.attempt["assisted"]


def test_plausible_but_mathematically_wrong_reference_is_rejected():
    result = step(ctx=context(expected="x=7"))
    assert result.status == "needs_review"
    assert result.exit_reason == "source_conflict"
    assert result.student_view.input_kind == "none"
    assert result.traces[0].validation == "rejected" and not result.learning_eligible


def test_model_can_choose_alternative_tool_but_cannot_invent_memory_sources():
    class Planner:
        def __init__(self, refs):
            self.refs = refs

        async def generate_structured(self, *args, **kwargs):
            return SupportPlan(
                goal="检查等式关系",
                tool_name="step_alignment",
                decision_summary="使用原题的等式关系",
                memory_refs=self.refs,
            )

    valid = step(kind="hint", provider=Planner([]))
    assert valid.traces[0].tool_name == "step_alignment"
    assert valid.traces[0].planner_source == "model"
    invalid = step(kind="hint", provider=Planner(["mastery:someone-else"]))
    assert invalid.traces[0].planner_source == "rule"
    assert invalid.traces[0].planner_reason == "invalid_plan_or_source"
    assert not any(t.memory_refs for t in invalid.traces)


def test_only_relevant_grade_appropriate_knowledge_is_used():
    cards = [
        {
            "code": "K",
            "name": "等式的性质",
            "subject": "数学",
            "content": {"grade": ["初一"], "definition": "等式两边同时作相同运算。"},
        },
        {
            "code": "wrong",
            "name": "等式的性质",
            "subject": "数学",
            "content": {"grade": ["高三"], "definition": "不应出现"},
        },
    ]
    result = step(kind="hint", ctx=context(cards=cards))
    assert result.traces[0].evidence["knowledge_card_codes"] == ["K"]
    assert "不应出现" not in result.student_view.feedback


def test_unverifiable_student_self_report_does_not_advance():
    result = step(kind="answer", text="我已经会了")
    assert result.status == "needs_review" and not result.learning_eligible
    assert not result.checkpoint.repair_passed


def test_forged_contrast_and_multiple_changes_are_rejected():
    item = make_contrast(context())
    assert item is not None
    assert not verify_contrast(context(), item.model_copy(update={"expected": "x=99"}))
    assert not verify_contrast(
        context(), item.model_copy(update={"equation": "3*x-3=11"})
    )
    assert not verify_contrast(
        context(),
        item.model_copy(update={"question": item.question + "，把分数改成100"}),
    )


@pytest.mark.parametrize(
    "text", ["已知2x+3=11，求x²", "解方程：x+x=2且x=1", "解方程：1/x=2", "解方程：x²=4"]
)
def test_unsupported_source_is_not_reinterpreted_as_a_linear_question(text):
    assert linear_source(text) is None
    assert make_contrast(context(question_text=text)) is None


def test_numeric_reference_and_complete_content_contract():
    assert step(ctx=context(expected="4")).status == "waiting_student"
    formula = r"$\frac{2x+3}{x}=2+\frac{3}{x}$"
    assert ContentBlock(kind="formula", text=formula).text == formula
    with pytest.raises(ValidationError):
        ContentBlock(kind="javascript", text="alert(1)")
    with pytest.raises(ValidationError):
        TaskAction(kind="set_mastery", text="100")
    with pytest.raises(ValidationError):
        SupportPlan(
            goal="越权测试", tool_name="delete_database", decision_summary="不可执行"
        )


def test_round_budget_stops_without_losing_checkpoint():
    state = Checkpoint(rounds=24, phase="repair")
    result = step(state, "resume")
    assert result.exit_reason == "round_budget" and result.status == "needs_review"
    assert result.checkpoint.rounds == 24 and not result.traces


def test_local_target_follows_the_actual_error_line_not_always_ax():
    ctx = context(student_steps=["2x=8", "x=7"], first_error_step=1)
    result = step(kind="answer", text="x=4", ctx=ctx)
    assert result.checkpoint.repair_passed and result.checkpoint.phase == "independent"


def test_repeated_solved_contrast_is_practice_not_new_independent_transfer():
    prior = make_contrast(context())
    ctx = context(seen_contrasts=[prior.question])
    ready = step(Checkpoint(phase="independent"), "answer", "x=4", ctx=ctx)
    assert ready.checkpoint.assistance["contrast"]
    result = step(ready.checkpoint, "answer", "x=7", ctx=ctx)
    assert result.status == "completed" and not result.learning_eligible


@pytest.mark.parametrize(
    "text",
    ["解方程：x/x+x=1", "解方程：x/(x-1)-x/(x-1)+x=0", "解方程：log(x)-log(x)+x=0"],
)
def test_domain_conditions_are_not_erased_by_symbolic_simplification(text):
    assert linear_source(text) is None


def test_undefined_zero_over_zero_is_not_accepted_as_a_correct_step_or_answer():
    ctx = context(question_text="解方程：2x=0", expected="x=0", student_steps=["2x=1"])
    local = step(kind="answer", text="2x=0*x/x", ctx=ctx)
    assert local.status == "needs_review" and not local.checkpoint.repair_passed
    final = step(Checkpoint(phase="independent"), "answer", "x=0*x/x", ctx=ctx)
    assert final.status == "needs_review" and not final.checkpoint.independent_passed


def test_local_checker_retains_selected_original_step_identity():
    ctx = context(
        source_snapshot_id="snapshot-1",
        student_work_id="work-1",
        student_step_ids=["s0", "s1"],
        reference_step_ids=["r0", "r1"],
        first_error_step=1,
    )
    result = step(kind="answer", text="x=4", ctx=ctx)
    evidence = result.traces[0].evidence
    assert evidence["source_snapshot_id"] == "snapshot-1"
    assert evidence["student_step_id"] == "s1"
    assert result.attempt["scope"] == "local_step"
    assert result.checkpoint.phase == "independent" and not result.learning_eligible


def test_planner_timeout_returns_bounded_rule_support():
    class SlowPlanner:
        cancelled = False

        async def generate_structured(self, *args, **kwargs):
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    provider = SlowPlanner()
    result = step(kind="hint", provider=provider)
    assert provider.cancelled
    assert result.traces[0].planner_reason == "planner_timeout"
    assert result.traces[0].planner_source == "rule"
    assert not result.learning_eligible and result.attempt is None


def test_no_error_diagnosis_does_not_ask_to_repair_a_correct_step():
    result = step(ctx=context(student_steps=["2x=8", "x=4"], diagnosed_correct=True))
    assert (
        result.status == "waiting_student" and result.checkpoint.phase == "independent"
    )
    assert result.student_view.title == "独立完成这道题"
    assert not result.learning_eligible and not result.checkpoint.repair_passed


def test_probably_correct_is_reviewable_feedback_not_a_confirmed_wrong_answer(
    monkeypatch,
):
    async def uncertain(*args, **kwargs):
        return {
            "verdict": "probably_correct",
            "correct": True,
            "can_update_learning": False,
            "feedback": "答案可能正确，请补充单位或依据。",
            "confidence": 0.8,
            "evidence": [],
        }

    monkeypatch.setattr("learning_task_compute.grade_answer", uncertain)
    result = step(Checkpoint(phase="independent"), "answer", "x=4")
    assert result.status == "needs_review" and not result.learning_eligible
    assert result.student_view.feedback == "答案可能正确，请补充单位或依据。"
    assert not result.checkpoint.independent_passed
