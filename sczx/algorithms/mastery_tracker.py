"""AEMT: assistance-aware, source-bound Bayesian evidence updates.

This computes proposals only. Cangjie validates ownership/version and commits
one event per request in its existing task transaction. No database is opened.
"""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from adaptive_practice import entropy, posterior


class MasteryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    hint_weight: float = Field(default=0.35, gt=0, lt=1)
    learning_rate: float = Field(default=0.08, ge=0, le=0.2)
    retention_weight: float = Field(default=1.25, ge=1, le=2)
    retention_days: float = Field(default=1, ge=1, le=30)
    forgetting_days: float = Field(default=30, ge=1, le=365)


class KnowledgeState(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    mastery: float = Field(default=0.35, ge=0, le=1)
    evidence_count: int = Field(default=0, ge=0)
    independent_count: int = Field(default=0, ge=0)
    independent_correct: int = Field(default=0, ge=0)
    hinted_count: int = Field(default=0, ge=0)
    solution_count: int = Field(default=0, ge=0)
    last_event_id: str = Field(default="", max_length=100)
    last_effective_at: str = Field(default="", max_length=64)


class AnswerEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    event_id: str = Field(min_length=1, max_length=100)
    occurred_at: str = Field(default="", max_length=64)
    verdict: Literal["confirmed_correct", "confirmed_incorrect", "review_required"]
    scope: Literal["local_step", "original_question", "contrast_question"]
    hint_used: bool = False
    solution_seen: bool = False
    source_current: bool = True
    student_confirmed: bool = True
    grading_reliable: bool = True
    delayed_similar: bool = False
    days_since_last: float = Field(default=0, ge=0, le=36500)
    option_count: int = Field(default=0, ge=0, le=26)


class MasteryUpdate(BaseModel):
    algorithm: Literal["aemt-v1"] = "aemt-v1"
    state: KnowledgeState
    changed: bool
    reason: str
    evidence_weight: float = Field(ge=0, le=2)
    uncertainty: float = Field(ge=0, le=1)
    forgetting_risk: float = Field(ge=0, le=1)
    event_id: str


def update_mastery(
    state: KnowledgeState, event: AnswerEvidence, config: MasteryConfig | None = None
) -> MasteryUpdate:
    config = config or MasteryConfig()
    updated = state.model_copy(deep=True)
    weight = 0.0
    reliable = (
        event.source_current
        and event.student_confirmed
        and event.grading_reliable
        and event.verdict != "review_required"
    )
    if event.event_id == state.last_event_id:
        reason = "本次作答已记录，不重复计入。"
    elif not reliable:
        reason = "作答或题目来源尚未核实，掌握状态保持不变。"
    elif event.scope == "local_step":
        reason = "已记录局部订正，待完整作答后再判断掌握情况。"
    elif event.solution_seen:
        updated.solution_count += 1
        updated.last_event_id = event.event_id
        reason = "本次看过完整答案，记录辅助学习，不增加掌握证据。"
    else:
        correct = event.verdict == "confirmed_correct"
        weight = config.hint_weight if event.hint_used else 1.0
        retention = (
            correct
            and not event.hint_used
            and event.delayed_similar
            and event.days_since_last >= config.retention_days
        )
        if retention:
            weight = config.retention_weight
        guess = 1 / max(2, event.option_count) if event.option_count else 0.05
        value = posterior(
            min(1 - 1e-6, max(1e-6, state.mastery)), correct, guess, weight
        )
        # A failed response never earns a learning-transition bonus.
        if correct:
            value += (1 - value) * config.learning_rate * min(weight, 1)
        updated.mastery = min(1 - 1e-6, max(1e-6, value))
        updated.evidence_count += 1
        if event.hint_used:
            updated.hinted_count += 1
        else:
            updated.independent_count += 1
            updated.independent_correct += int(correct)
        updated.last_event_id = event.event_id
        updated.last_effective_at = event.occurred_at or state.last_effective_at
        reason = (
            "间隔后独立答对类似题，增加保持与迁移证据。"
            if retention
            else "借助提示完成，按较弱证据更新。"
            if event.hint_used and correct
            else "独立作答正确，增加掌握证据。"
            if correct
            else "本次作答错误，需要继续检查薄弱步骤。"
        )
    elapsed = 0 if weight else event.days_since_last
    risk = 1 - updated.mastery * math.exp(-elapsed / config.forgetting_days)
    return MasteryUpdate(
        state=updated,
        changed=updated != state,
        reason=reason,
        evidence_weight=weight,
        uncertainty=entropy(updated.mastery),
        forgetting_risk=min(1, max(0, risk)),
        event_id=event.event_id,
    )


def compute_aemt_cognition(mastery_values, misconception_values, evidence, label=None):
    """Adapt proposals to the existing cognition_update storage projection.

    Opt-in only: legacy evidence retains its original calculation. The native
    task transaction supplies the validated event and provides durable dedupe.
    """
    from learning_core.services.cognition_rules import compute_cognition

    event = AnswerEvidence.model_validate(evidence["aemt_event"])
    state = KnowledgeState(
        mastery=mastery_values["mastery_score"]
        if mastery_values["evidence_count"]
        else 0.35,
        evidence_count=mastery_values["evidence_count"],
    )
    update = update_mastery(state, event)
    if not update.evidence_weight:
        unchanged = dict(mastery_values)
        unchanged["update_reason"] = update.reason
        unchanged["forgetting_risk"] = update.forgetting_risk
        return unchanged, dict(misconception_values)
    # Keep existing rate/strategy fields and schema; override evidence arithmetic
    # with the Bayesian update, never an additional additive mastery award.
    mastery, misconception = compute_cognition(
        mastery_values, misconception_values, evidence, label
    )
    mastery["mastery_score"] = (
        update.state.mastery
        if update.evidence_weight
        else mastery_values["mastery_score"]
    )
    mastery["evidence_count"] = update.state.evidence_count
    mastery["confidence"] = (
        (1 - update.uncertainty)
        if update.evidence_weight
        else mastery_values["confidence"]
    )
    mastery["forgetting_risk"] = update.forgetting_risk
    mastery["update_reason"] = update.reason
    delta = update.state.mastery - state.mastery if update.evidence_weight else 0
    misconception["probability"] = min(
        1, max(0, misconception_values["probability"] - delta * 0.8)
    )
    misconception["evidence_count"] = misconception_values["evidence_count"] + int(
        update.evidence_weight > 0
    )
    misconception["status"] = "improving" if delta > 0 else "active"
    return mastery, misconception
