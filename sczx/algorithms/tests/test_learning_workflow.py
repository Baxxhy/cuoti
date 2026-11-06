import asyncio

import pytest
from test_learning_task_compute import context

from grading_compute import UnavailableGradingProvider
from learning_planner import PlanCandidate
from learning_task_compute import Checkpoint, TaskAction
from learning_workflow import build_learning_graph, run_learning_workflow
from mastery_tracker import KnowledgeState


def run(checkpoint=None, kind="start", text="", **extra):
    return asyncio.run(
        run_learning_workflow(
            UnavailableGradingProvider(),
            context(**extra),
            checkpoint or Checkpoint(),
            TaskAction(kind=kind, text=text),
        )
    )


def test_real_graph_has_three_algorithm_nodes_and_conditional_confirmation():
    graph = build_learning_graph(UnavailableGradingProvider()).get_graph()
    assert {"eced", "aemt", "arpp", "confirm", "student_action"} <= set(graph.nodes)
    assert any(edge.source == "eced" and edge.conditional for edge in graph.edges)


def test_diagnose_repair_independent_transfer_and_next_recommendation():
    started = run()
    assert started.checkpoint.evidence_diagnosis.verified
    repaired = run(started.checkpoint, "answer", "11-3")
    assert repaired.checkpoint.next_recommendation.action == "retry"
    assert not repaired.checkpoint.mastery_update.changed
    independent = run(repaired.checkpoint, "answer", "x=4")
    assert independent.checkpoint.mastery_update.state.evidence_count == 1
    assert independent.checkpoint.next_recommendation.action == "practice"
    restored = Checkpoint.model_validate_json(independent.checkpoint.model_dump_json())
    resumed = run(restored, "resume")
    assert resumed.checkpoint.mastery_update.state.evidence_count == 1
    done = run(
        resumed.checkpoint,
        "answer",
        "x=7",
        practice_candidates=[PlanCandidate(id="next-1", subject="数学", due=True)],
    )
    assert done.status == "completed"
    assert done.student_view.diagnosis_evidence is None
    assert done.checkpoint.mastery_update.state.evidence_count == 2
    assert done.student_view.recommendation.action == "review"
    assert done.student_view.recommendation.question_id == "next-1"
    replay = run(done.checkpoint, "answer", "x=7")
    assert replay.checkpoint.mastery_update.state.evidence_count == 2


def test_unsupported_diagnosis_asks_for_real_work_without_mastery_update():
    result = run(
        question_text="证明三角形全等",
        expected="全等",
        student_steps=["看图可得全等"],
        reference_steps=["需要满足全等条件"],
    )
    assert result.status == "needs_review"
    assert result.exit_reason == "diagnosis_needs_confirmation"
    assert result.student_view.input_kind == "none"
    assert "请补充" in result.student_view.prompt_blocks[0].text
    assert result.checkpoint.mastery_update is None


def test_source_conflict_cannot_award_mastery():
    result = run(expected="x=99")
    assert result.exit_reason == "source_conflict"
    assert result.checkpoint.mastery_update is None


def test_verified_eced_location_drives_repair_instead_of_stale_default_index():
    started = run(student_steps=["2x=8", "x=5"], student_step_ids=["s0", "s1"])
    assert started.checkpoint.evidence_diagnosis.first_error_step == 1
    repaired = run(
        started.checkpoint,
        "answer",
        "x=4",
        student_steps=["2x=8", "x=5"],
        student_step_ids=["s0", "s1"],
    )
    assert repaired.checkpoint.repair_passed
    assert repaired.traces[0].evidence["student_step_id"] == "s1"


def test_repair_evidence_does_not_automatically_reveal_the_final_reference_answer():
    result = run(student_steps=["2x=8", "x=5"])
    assert any(
        item.text == "x=4" for item in result.checkpoint.evidence_diagnosis.evidence
    )
    assert "x=4" not in result.student_view.model_dump_json()
    assert result.student_view.diagnosis_evidence.candidates == []


def test_revealed_answer_stays_assisted_even_after_a_hint():
    original = run(run().checkpoint, "answer", "11-3")
    revealed = run(original.checkpoint, "reveal")
    hinted = run(revealed.checkpoint, "hint")
    result = run(hinted.checkpoint, "answer", "x=4")
    assert result.checkpoint.mastery_update.evidence_weight == 0
    assert result.checkpoint.mastery_update.state.evidence_count == 0


def test_independent_view_does_not_expose_reference_answer_via_evidence():
    independent = run(run().checkpoint, "answer", "11-3")
    assert independent.student_view.diagnosis_evidence is None
    assert "expected" not in independent.student_view.model_dump_json()


def test_completing_current_task_consumes_the_remaining_goal_and_time():
    started = run()
    repaired = run(started.checkpoint, "answer", "11-3")
    original = run(repaired.checkpoint, "answer", "x=4")
    done = run(
        original.checkpoint,
        "answer",
        "x=7",
        goal_remaining=1,
        available_minutes=3,
        practice_candidates=[PlanCandidate(id="next-1", subject="数学")],
    )
    assert done.student_view.recommendation.action == "stop"
    assert done.student_view.recommendation.question_id is None


@pytest.mark.parametrize("has_snapshot", [False, True])
def test_resumed_recommendation_uses_current_persisted_mastery(has_snapshot):
    started = run()
    repaired = run(started.checkpoint, "answer", "11-3")
    original = run(repaired.checkpoint, "answer", "x=4")
    done = run(original.checkpoint, "answer", "x=7")
    snapshot = done.checkpoint.model_copy(deep=True)
    if has_snapshot:
        snapshot.mastery_update.state.mastery = 0.2
    else:
        snapshot.mastery_update = None
    resumed = run(
        snapshot,
        "resume",
        mastery_state=KnowledgeState(mastery=0.9),
        practice_candidates=[
            PlanCandidate(id="next-1", subject="数学", knowledge_points=["等式的性质"])
        ],
    )
    assert resumed.attempt is None
    ranking = resumed.student_view.recommendation.ranking
    assert ranking[0]["components"]["weakness"] == pytest.approx(0.1)


def test_current_answer_recommendation_uses_the_fresh_mastery_update():
    started = run()
    repaired = run(started.checkpoint, "answer", "11-3")
    original = run(repaired.checkpoint, "answer", "x=4")
    done = run(
        original.checkpoint,
        "answer",
        "x=7",
        mastery_state=KnowledgeState(mastery=0.4),
        practice_candidates=[
            PlanCandidate(id="next-1", subject="数学", knowledge_points=["等式的性质"])
        ],
    )
    assert done.attempt is not None
    updated = done.checkpoint.mastery_update.state.mastery
    assert updated > 0.4
    assert done.student_view.recommendation.ranking[0]["components"][
        "weakness"
    ] == pytest.approx(1 - updated)
