"""ARPP: bounded action planning and interpretable candidate ranking."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from adaptive_practice import PracticeCandidate, information_gain, skills

Action = Literal[
    "explain", "hint", "repair", "prerequisite", "retry", "practice", "review", "stop"
]


class PlanCandidate(PracticeCandidate):
    source: Literal["dataset", "notebook"] = "dataset"
    difficulty: float = Field(default=0.5, ge=0, le=1)
    error_relevance: float = Field(default=0, ge=0, le=1)
    due: bool = False
    recent_exposures: int = Field(default=0, ge=0, le=10000)
    just_mastered: bool = False
    estimated_minutes: int = Field(default=3, ge=1, le=120)


class PlannerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    error: float = Field(default=0.2, ge=0, le=1)
    weakness: float = Field(default=0.2, ge=0, le=1)
    gain: float = Field(default=0.15, ge=0, le=1)
    due: float = Field(default=0.2, ge=0, le=1)
    difficulty: float = Field(default=0.15, ge=0, le=1)
    time: float = Field(default=0.1, ge=0, le=1)
    repetition: float = Field(default=0.3, ge=0, le=1)


class PlannerInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    candidates: list[PlanCandidate] = Field(default_factory=list, max_length=200)
    mastery: dict[str, float] = Field(default_factory=dict, max_length=400)
    knowledge_points: list[str] = Field(default_factory=list, max_length=100)
    knowledge_card_ids: list[str] = Field(default_factory=list, max_length=6)
    phase: Literal["repair", "independent", "contrast", "done"] = "repair"
    evidence_sufficient: bool = True
    prerequisite_missing: bool = False
    repeated_error: bool = False
    consecutive_failures: int = Field(default=0, ge=0, le=24)
    minutes_remaining: int = Field(default=10, ge=0, le=120)
    goal_remaining: int = Field(default=3, ge=0, le=20)
    current_subject: str = Field(default="", max_length=30)


class LearningPlan(BaseModel):
    algorithm: Literal["arpp-v1"] = "arpp-v1"
    action: Action
    question_id: str | None = None
    question_source: Literal["dataset", "notebook"] | None = None
    knowledge_points: list[str] = Field(default_factory=list)
    reason: str
    estimated_minutes: int = Field(default=0, ge=0, le=120)
    alternatives: list[str] = Field(default_factory=list, max_length=2)
    knowledge_card_ids: list[str] = Field(default_factory=list, max_length=6)
    ranking: list[dict] = Field(default_factory=list, max_length=3)


def plan_learning(
    data: PlannerInput, config: PlannerConfig | None = None
) -> LearningPlan:
    config = config or PlannerConfig()
    common = {
        "knowledge_points": data.knowledge_points,
        "knowledge_card_ids": data.knowledge_card_ids,
    }

    def simple(action, reason, minutes=1):
        return LearningPlan(
            action=action,
            reason=reason,
            estimated_minutes=min(minutes, data.minutes_remaining),
            **common,
        )

    if data.minutes_remaining == 0 or data.goal_remaining == 0:
        return simple(
            "stop",
            "今天的学习量已完成，可以结束本轮学习。"
            if data.goal_remaining == 0
            else "这轮先到这里，剩下的内容可以下次继续。",
            0,
        )
    if not data.evidence_sufficient:
        return simple("explain", "先核对原题和作答，确认后再订正。")
    if data.prerequisite_missing:
        return simple("prerequisite", "先复习这一步用到的基础知识，再回来作答。", 2)
    if data.repeated_error and data.phase != "done":
        return simple("repair", "这一步再次出错，先把对应的计算拆开订正。", 2)
    if data.consecutive_failures >= 2 and data.phase != "done":
        return simple("hint", "先看这一步的提示，再完成一个小步骤。")
    if data.phase == "repair":
        return simple("repair", "先订正出错的这一步。", 2)
    if data.phase == "independent":
        return simple("retry", "现在重新作答，检查是否能自己完成。", 3)
    if data.phase == "contrast":
        return simple("practice", "换一道相近的题，检查这一步是否掌握。", 3)

    ranked = []
    for candidate in {item.id: item for item in data.candidates}.values():
        if (
            candidate.estimated_minutes > data.minutes_remaining
            or candidate.just_mastered
            or (data.current_subject and candidate.subject != data.current_subject)
        ):
            continue
        keys, _ = skills(candidate)
        prior = sum(min(1, max(0, data.mastery.get(key, 0.35))) for key in keys) / len(
            keys
        )
        guess = 1 / max(2, len(candidate.options)) if candidate.options else 0.05
        target = max(0.15, prior - min(0.3, data.consecutive_failures * 0.1))
        parts = {
            "error": candidate.error_relevance,
            "weakness": 1 - prior,
            "gain": min(1, information_gain(prior, guess)),
            "due": float(candidate.due),
            "difficulty": 1 - abs(candidate.difficulty - target),
            "time": 1 - candidate.estimated_minutes / max(1, data.minutes_remaining),
            "repetition": min(1, candidate.recent_exposures / 3),
        }
        score = (
            sum(
                getattr(config, key) * value
                for key, value in parts.items()
                if key != "repetition"
            )
            - config.repetition * parts["repetition"]
        )
        ranked.append((candidate, score, parts))
    # Reserve priority for an eligible due review; new items cannot starve it.
    ranked.sort(key=lambda item: (-int(item[0].due), -item[1], item[0].id))
    if not ranked:
        return simple(
            "prerequisite" if data.knowledge_card_ids else "stop",
            "暂时没有合适的练习题，可以先查看相关知识。"
            if data.knowledge_card_ids
            else "暂时没有符合学科和时间要求的练习题。",
            2 if data.knowledge_card_ids else 0,
        )
    selected = ranked[0][0]
    return LearningPlan(
        action="review" if selected.due else "practice",
        question_id=selected.id,
        question_source=selected.source,
        reason="这道错题到了复习时间，先重新做一次。"
        if selected.due
        else "练一道相关题，巩固刚才出错的知识。",
        estimated_minutes=selected.estimated_minutes,
        alternatives=[item[0].id for item in ranked[1:3]],
        ranking=[
            {"question_id": item.id, "score": round(score, 6), "components": parts}
            for item, score, parts in ranked[:3]
        ],
        **common,
    )
