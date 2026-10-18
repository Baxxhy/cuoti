from __future__ import annotations

from typing import Any

TUTOR_STAGES = (
    "understanding",
    "teach_back",
    "near_transfer",
    "far_transfer",
    "finished",
)

LEGACY_STAGE_ALIASES = {
    "teach_back_retry": "teach_back",
    "near_remediation": "near_transfer",
    "transfer_insufficient": "far_transfer",
}

LEGACY_UNDERSTANDING_STAGES = {
    "guided_question",
    "prerequisite",
    "local_hint",
    "strategy_switch",
    "replan",
    "answer_shown",
}


def canonical_tutor_stage(stage: str | None) -> str:
    value = str(stage or "").strip()
    if not value or value in LEGACY_UNDERSTANDING_STAGES:
        return "understanding"
    value = LEGACY_STAGE_ALIASES.get(value, value)
    return value if value in TUTOR_STAGES else "understanding"


def transition_tutor_stage(current: str | None, event: str, state: dict[str, Any] | None = None) -> str:
    stage = canonical_tutor_stage(current)
    flags = state or {}
    if event == "understanding_advance":
        if stage != "understanding":
            raise ValueError("当前不在理解阶段")
        if not bool(flags.get("understanding_passed")):
            raise ValueError("需要先通过理解检查")
        return "teach_back"
    transitions = {
        ("teach_back", "teach_back_pass"): "near_transfer",
        ("teach_back", "teach_back_fail"): "teach_back",
        ("near_transfer", "near_pass"): "far_transfer",
        ("near_transfer", "near_fail"): "near_transfer",
        ("far_transfer", "far_pass"): "finished",
        ("far_transfer", "far_fail"): "far_transfer",
    }
    target = transitions.get((stage, event))
    if target is None:
        raise ValueError(f"阶段 {stage} 不能执行事件 {event}")
    return target


def previous_tutor_stage(current: str | None) -> str:
    stage = canonical_tutor_stage(current)
    previous = {
        "teach_back": "understanding",
        "near_transfer": "teach_back",
        "far_transfer": "near_transfer",
    }.get(stage)
    if previous is None:
        raise ValueError(f"阶段 {stage} 不能返回上一步")
    return previous
