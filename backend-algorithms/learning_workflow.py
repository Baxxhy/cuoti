"""One LangGraph coordinator. Each invocation ends before waiting for a student.

The existing Cangjie checkpoint/lease transaction remains the only persistence
mechanism. The graph has no database checkpointer, credentials or write tools.
"""

from types import SimpleNamespace
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from diagnosis_alignment import polynomial_alignment
from diagnosis_compute import StepRecord
from error_diagnosis import assess_diagnosis
from grounded_knowledge import build_knowledge_evidence
from inequality_compute import inequality_alignment
from learning_planner import PlannerInput, plan_learning
from learning_task_compute import (
    Checkpoint,
    ContentBlock,
    StudentView,
    TaskAction,
    TaskContext,
    TaskResult,
    execute_task,
)
from mastery_tracker import AnswerEvidence, KnowledgeState, update_mastery


class WorkflowState(TypedDict, total=False):
    context: TaskContext
    checkpoint: Checkpoint
    action: TaskAction
    diagnosis: dict
    result: TaskResult
    route: str


def _diagnosed_context(context, diagnosis):
    if not diagnosis.verified:
        return context
    if diagnosis.first_error_step is not None:
        if not 0 <= diagnosis.first_error_step < len(context.student_steps):
            raise ValueError("diagnosis outside actual student work")
        return context.model_copy(
            update={"first_error_step": diagnosis.first_error_step}
        )
    if diagnosis.error_type == "exact":
        return context.model_copy(update={"diagnosed_correct": True})
    return context


def _diagnose(state: WorkflowState):
    context, checkpoint = state["context"], state["checkpoint"]
    if checkpoint.evidence_diagnosis is not None:
        return {
            "context": _diagnosed_context(context, checkpoint.evidence_diagnosis),
            "diagnosis": checkpoint.evidence_diagnosis.model_dump(),
            "route": "execute",
        }
    students = [
        StepRecord(
            id=context.student_step_ids[i]
            if i < len(context.student_step_ids)
            else f"student-{i}",
            text=text,
        )
        for i, text in enumerate(context.student_steps)
    ]
    references = [
        StepRecord(
            id=context.reference_step_ids[i]
            if i < len(context.reference_step_ids)
            else f"reference-{i}",
            text=text,
        )
        for i, text in enumerate(context.reference_steps)
    ]
    alignment = []
    checked = None
    if context.subject == "数学":
        checked = polynomial_alignment(
            context.question_text, references, students, None
        )
        if checked is None:
            checked = inequality_alignment(
                context.question_text, references, students, None
            )
        if checked is not None:
            alignment = checked[0]
    diagnosis = assess_diagnosis(
        students=students,
        references=references,
        alignment=alignment,
        diagnosis=SimpleNamespace(root_misconception=context.diagnosis_hypothesis),
        knowledge=build_knowledge_evidence(
            context.cards, context.subject, context.grade
        ),
    )
    checkpoint = checkpoint.model_copy(deep=True)
    checkpoint.evidence_diagnosis = diagnosis
    checkpoint.workflow_version = "langgraph-learning-v1"
    # Unsupported student work requires confirmation instead of fabricating a
    # repair target. A blank original answer can still start independent work.
    route = (
        "confirm"
        if students
        and checked is None
        and not context.diagnosed_correct
        and not context.diagnosis_confirmed
        else "execute"
    )
    return {
        "context": _diagnosed_context(context, diagnosis),
        "checkpoint": checkpoint,
        "diagnosis": diagnosis.model_dump(),
        "route": route,
    }


def _confirm(state: WorkflowState):
    checkpoint = state["checkpoint"].model_copy(deep=True)
    diagnosis = checkpoint.evidence_diagnosis
    message = diagnosis.question or (
        diagnosis.reason + "请补充这一步用到的题目条件或判断依据，再继续订正。"
    )
    checkpoint.feedback = message
    # Resume rechecks the context; confirmed edits create a new version through
    # the original question page and Cangjie's existing source checks.
    checkpoint.evidence_diagnosis = None
    return {
        "result": TaskResult(
            checkpoint=checkpoint,
            student_view=StudentView(
                title="先核对原作答",
                input_kind="none",
                prompt_blocks=[ContentBlock(kind="text", text=message)],
                primary_action="查看原题",
                secondary_actions=[],
                diagnosis_evidence=diagnosis,
            ),
            status="needs_review",
            traces=[],
            exit_reason="diagnosis_needs_confirmation",
            elapsed_ms=0,
        )
    }


async def _execute(state: WorkflowState, provider):
    result = await execute_task(
        provider, state["context"], state["checkpoint"], state["action"]
    )
    return {"result": result}


def _track(state: WorkflowState):
    result = state["result"].model_copy(deep=True)
    context = state["context"]
    attempt = result.attempt
    if attempt is not None:
        phase = attempt["phase"]
        # Reveals and hints have different evidence weights. Legacy assistance
        # without a retained hint is conservatively treated as answer exposure.
        assisted = attempt["assisted"]
        hints = bool(state["checkpoint"].hints.get(phase))
        event = AnswerEvidence(
            event_id=context.action_id
            or f"{context.question_id}:{result.checkpoint.rounds}",
            verdict=attempt["verdict"]
            if attempt["verdict"] in {"confirmed_correct", "confirmed_incorrect"}
            else "review_required",
            scope=attempt["scope"],
            hint_used=assisted and hints,
            solution_seen=phase in state["checkpoint"].revealed_phases
            or (assisted and not hints),
            option_count=len(context.options),
            grading_reliable=attempt["verdict"]
            in {"confirmed_correct", "confirmed_incorrect"},
        )
        prior = context.mastery_state
        if prior is None:
            prior = (
                state["checkpoint"].mastery_update.state
                if state["checkpoint"].mastery_update
                else KnowledgeState()
            )
        result.checkpoint.mastery_update = update_mastery(prior, event)
    return {"result": result}


def _plan(state: WorkflowState):
    result = state["result"].model_copy(deep=True)
    context = state["context"]
    points = context.knowledge_points
    completed_now = result.status == "completed" and state["checkpoint"].phase != "done"
    remaining_goal = max(0, context.goal_remaining - int(completed_now))
    remaining_minutes = max(0, context.available_minutes - (3 if completed_now else 0))
    # A new answer uses _track's result; reopening a task uses the current
    # persisted state, which may have changed through other learning sessions.
    mastery_state = context.mastery_state
    if result.checkpoint.mastery_update and (
        result.attempt is not None or mastery_state is None
    ):
        mastery_state = result.checkpoint.mastery_update.state
    mastery = (mastery_state or KnowledgeState()).mastery
    plan = plan_learning(
        PlannerInput(
            candidates=context.practice_candidates,
            mastery={f"{context.subject}:{point}": mastery for point in points},
            knowledge_points=points,
            knowledge_card_ids=context.prerequisite_card_ids
            or [str(card["id"]) for card in context.cards if card.get("id")],
            phase=result.checkpoint.phase,
            prerequisite_missing=bool(context.prerequisite_card_ids),
            repeated_error=result.checkpoint.attempts >= 2,
            consecutive_failures=result.checkpoint.attempts,
            minutes_remaining=remaining_minutes,
            goal_remaining=remaining_goal,
            current_subject=context.subject,
            evidence_sufficient=result.exit_reason
            not in {"source_conflict", "round_budget"}
            and (
                result.attempt is None
                or result.attempt["verdict"]
                in {"confirmed_correct", "confirmed_incorrect"}
            ),
        )
    )
    result.checkpoint.next_recommendation = plan
    result.student_view.recommendation = plan
    # Reference evidence remains in the server checkpoint. Do not leak the
    # reference answer through the independent/contrast answer-entry view.
    result.student_view.diagnosis_evidence = (
        result.checkpoint.evidence_diagnosis
        if result.checkpoint.phase == "repair"
        else None
    )
    if result.checkpoint.phase == "repair" and result.student_view.diagnosis_evidence:
        # A final erroneous step can align directly with the reference answer.
        # Do not display that answer automatically and then score its repetition
        # as unaided work. Full evidence stays in the server checkpoint/detail.
        safe = result.student_view.diagnosis_evidence.model_copy(deep=True)
        safe.evidence = [
            item for item in safe.evidence if item.source in {"student_step", "rule"}
        ]
        safe.candidates = []
        result.student_view.diagnosis_evidence = safe
    return {"result": result}


def build_learning_graph(provider):
    graph = StateGraph(WorkflowState)
    graph.add_node("eced", _diagnose)
    graph.add_node("confirm", _confirm)

    async def run_step(state):
        return await _execute(state, provider)

    graph.add_node("student_action", run_step)
    graph.add_node("aemt", _track)
    graph.add_node("arpp", _plan)
    graph.add_edge(START, "eced")
    graph.add_conditional_edges(
        "eced",
        lambda state: state["route"],
        {"confirm": "confirm", "execute": "student_action"},
    )
    graph.add_edge("confirm", END)
    graph.add_edge("student_action", "aemt")
    graph.add_edge("aemt", "arpp")
    graph.add_edge("arpp", END)
    return graph.compile()


async def run_learning_workflow(provider, context, checkpoint, action):
    # The caller's existing wall-clock timeout and model budgets wrap the full
    # graph. Six nodes maximum; no recursive autonomous student actions.
    result = await build_learning_graph(provider).ainvoke(
        {"context": context, "checkpoint": checkpoint, "action": action},
        config={"recursion_limit": 8},
    )
    return result["result"]
