"""Pure cognition arithmetic and target resolution. No database imports or writes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)








def _reason(evidence: dict[str, Any]) -> str:
    labels = []
    for key, label in (("teach_back", "讲解思路"), ("near_transfer", "相似题"), ("far_transfer", "综合题")):
        if key in evidence:
            labels.append(f"{label}{'通过' if evidence[key] else '未通过'}")
    if evidence.get("hint_level"):
        labels.append(f"提示等级{evidence['hint_level']}")
    return "、".join(labels) or "根据本次学习更新"


def compute_cognition(
    mastery_values: dict[str, Any],
    misconception_values: dict[str, Any],
    evidence: dict[str, Any],
    misconception_label: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mastery = SimpleNamespace(**mastery_values)
    misconception = SimpleNamespace(**misconception_values)
    old_mastery = mastery.mastery_score
    old_probability = misconception.probability
    teach = evidence.get("teach_back")
    near = evidence.get("near_transfer")
    far = evidence.get("far_transfer")
    hint_level = int(evidence.get("hint_level", 0))
    delta = 0.08 if teach is True else -0.05 if teach is False else 0
    delta += 0.12 if near is True else -0.08 if near is False else 0
    delta += 0.18 if far is True else -0.06 if far is False else 0
    delta -= min(0.06, hint_level * 0.02)
    mastery.mastery_score = _clamp(old_mastery + delta)
    mastery.evidence_count += 1
    mastery.confidence = _clamp(0.35 + mastery.evidence_count * 0.08)
    if near is not None:
        mastery.near_transfer_rate = _clamp(
            (mastery.near_transfer_rate * max(0, mastery.evidence_count - 1) + int(bool(near)))
            / mastery.evidence_count
        )
    if far is not None:
        mastery.far_transfer_rate = _clamp(
            (mastery.far_transfer_rate * max(0, mastery.evidence_count - 1) + int(bool(far)))
            / mastery.evidence_count
        )
    mastery.forgetting_risk = _clamp(1 - mastery.mastery_score + (0.15 if far is False else 0))
    mastery.update_reason = _reason(evidence)

    probability_delta = -delta * 0.8
    misconception.probability = _clamp(old_probability + probability_delta)
    misconception.evidence_count += 1
    misconception.related_question_count = max(1, misconception.related_question_count)
    if misconception_label:
        misconception.label = misconception_label
    misconception.status = "improving" if misconception.probability < old_probability else "active"
    strategy = str(evidence.get("strategy", ""))
    if strategy:
        if any(value is True for value in (teach, near, far)):
            misconception.successful_strategy = strategy
        elif any(value is False for value in (teach, near, far)):
            misconception.failed_strategy = strategy

    return vars(mastery), vars(misconception)
