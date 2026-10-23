"""Database-free tutoring agent planning, tools and evidence verification.

Knowledge cards are selected by Cangjie and supplied as records. Planning, tool
semantics, bounded symbolic checks and decision verification retain the original
algorithms. No ORM or business configuration is imported at runtime.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from learning_core.providers.api_pool import ApiPoolProvider, ApiPoolUnavailable
from learning_core.services.math_tools import compare_equivalence
from learning_core.services.visualizations import recommended_visualization

ToolName = Literal[
    "knowledge_search",
    "step_alignment",
    "visualization",
    "rediagnose",
    "answer_reveal",
    "answer_check",
]

TOOL_DESCRIPTIONS: dict[ToolName, str] = {
    "knowledge_search": "检索与当前薄弱点匹配的课程知识卡",
    "step_alignment": "把学生当前表达与参考步骤对齐，找出下一小步",
    "visualization": "选择安全的 VisualizationSpec 图示类型",
    "rediagnose": "结合长期误区记录重新确定当前偏差",
    "answer_reveal": "在学生明确要求答案时提供参考结论和步骤",
    "answer_check": "用规则与 SymPy 检查答案，并要求解释依据",
}

TOOL_EVIDENCE_CONTRACTS: dict[ToolName, tuple[str, ...]] = {
    "knowledge_search": ("knowledge_card_codes",),
    "step_alignment": ("alignment_prompt",),
    "visualization": ("visualization_type", "safe_spec"),
    "rediagnose": ("candidate_misconceptions",),
    "answer_reveal": ("final_answer",),
    "answer_check": ("answer_match", "checkable"),
}


class AgentMemorySnapshot(BaseModel):
    mastery: list[dict[str, Any]] = Field(default_factory=list, max_length=5)
    misconceptions: list[dict[str, Any]] = Field(default_factory=list, max_length=5)
    recent_updates: list[dict[str, Any]] = Field(default_factory=list, max_length=5)
    reviews: list[dict[str, Any]] = Field(default_factory=list, max_length=3)
    source_ids: list[str] = Field(default_factory=list, max_length=18)
    summary: str = "暂无长期认知证据"



class ValidatedAgentMemorySnapshot(AgentMemorySnapshot):
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=18)
    source_versions: dict[str, str] = Field(default_factory=dict, max_length=18)


class AgentPlan(BaseModel):
    """可公开审计的任务计划；不接收或保存模型内部思维链。"""

    goal: str = Field(min_length=2, max_length=120)
    steps: list[str] = Field(min_length=1, max_length=4)
    tool_name: ToolName
    tool_input: dict[str, Any] = Field(default_factory=dict)
    expected_evidence: list[str] = Field(min_length=1, max_length=4)
    decision_summary: str = Field(min_length=2, max_length=180)
    memory_source_ids: list[str] = Field(default_factory=list, max_length=6)
    confidence: float = Field(ge=0, le=1)


class AgentToolResult(BaseModel):
    tool_name: ToolName
    executed: bool
    evidence: dict[str, Any] = Field(default_factory=dict)
    consumed_input: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class VerificationCheck(BaseModel):
    name: str
    passed: bool
    evidence: str


class DecisionVerification(BaseModel):
    status: Literal["verified", "partial", "rejected"]
    checks: list[VerificationCheck]
    evidence_refs: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class AgentToolContext:
    subject: str
    question_type: str
    question_text: str
    final_answer: str
    reference_steps: list[str]
    student_message: str
    turn_count: int
    knowledge_points: list[Any] = field(default_factory=list)
    memory: AgentMemorySnapshot = field(default_factory=AgentMemorySnapshot)


class AgentTurnResult(BaseModel):
    observation: dict[str, Any]
    plan: AgentPlan
    tool: AgentToolResult
    verification: DecisionVerification
    planner_status: Literal["model", "fallback"]


def build_memory_snapshot(
    mastery_rows: list[Any],
    misconception_rows: list[Any],
    cognitive_rows: list[Any],
    review_rows: list[Any],
) -> AgentMemorySnapshot:
    mastery = [
        {
            "knowledge_point": row.knowledge_point,
            "mastery_score": round(float(row.mastery_score), 3),
            "confidence": round(float(row.confidence), 3),
            "forgetting_risk": round(float(row.forgetting_risk), 3),
        }
        for row in mastery_rows[:5]
    ]
    misconceptions = [
        {
            "code": row.code,
            "label": row.label,
            "probability": round(float(row.probability), 3),
            "status": row.status,
            "successful_strategy": row.successful_strategy or "",
        }
        for row in misconception_rows[:5]
    ]
    updates = [
        {
            "entity_type": row.entity_type,
            "entity_key": row.entity_key,
            "old_value": round(float(row.old_value), 3),
            "new_value": round(float(row.new_value), 3),
            "reason": row.reason,
        }
        for row in cognitive_rows[:5]
    ]
    reviews = [
        {"reason": row.reason, "interval_days": row.interval_days}
        for row in review_rows[:3]
    ]
    source_ids = [
        *(f"mastery:{row.id}" for row in mastery_rows[:5]),
        *(f"misconception:{row.id}" for row in misconception_rows[:5]),
        *(f"cognitive:{row.id}" for row in cognitive_rows[:5]),
        *(f"review:{row.id}" for row in review_rows[:3]),
    ]
    summary_parts = []
    if mastery:
        weakest = min(mastery, key=lambda item: item["mastery_score"])
        summary_parts.append(
            f"薄弱点：{weakest['knowledge_point']}（掌握度{weakest['mastery_score']:.0%}）"
        )
    if misconceptions:
        summary_parts.append(f"高概率误区：{misconceptions[0]['label']}")
    if reviews:
        summary_parts.append(f"待巩固：{reviews[0]['reason']}")
    return AgentMemorySnapshot(
        mastery=mastery,
        misconceptions=misconceptions,
        recent_updates=updates,
        reviews=reviews,
        source_ids=source_ids,
        summary="；".join(summary_parts) or "暂无长期认知证据",
    )


def fallback_plan(
    graph_result: dict[str, Any], memory: AgentMemorySnapshot
) -> AgentPlan:
    requested_tool = str(graph_result.get("tool_name") or "step_alignment")
    tool_name: ToolName = next(
        (name for name in TOOL_DESCRIPTIONS if name == requested_tool), "step_alignment"
    )
    expected = {
        "knowledge_search": "knowledge_card_codes",
        "step_alignment": "alignment_prompt",
        "visualization": "visualization_type",
        "rediagnose": "candidate_misconceptions",
        "answer_reveal": "reference_steps",
        "answer_check": "answer_match",
    }[tool_name]
    return AgentPlan(
        goal=str(graph_result.get("next_goal") or "推进当前教学目标"),
        steps=[
            "读取题目与学生当前表达",
            "结合长期认知记忆选择教学动作",
            f"执行{TOOL_DESCRIPTIONS[tool_name]}",
            "核验工具证据",
        ],
        tool_name=tool_name,
        tool_input={},
        expected_evidence=[expected],
        decision_summary=f"依据当前对话分支与认知记录，选择{TOOL_DESCRIPTIONS[tool_name]}",
        memory_source_ids=memory.source_ids[:3],
        confidence=0.72,
    )


async def plan_agent_turn(
    provider: ApiPoolProvider,
    graph_result: dict[str, Any],
    context: AgentToolContext,
) -> tuple[AgentPlan, Literal["model", "fallback"]]:
    fallback = fallback_plan(graph_result, context.memory)
    prompt = json.dumps(
        {
            "task": "为当前教学轮次制定最多四步的公开行动计划，并且只选择一个允许工具。不得输出隐藏思维过程。",
            "perception": {
                "subject": context.subject,
                "question_type": context.question_type,
                "question_text": context.question_text,
                "student_message": context.student_message,
                "turn_count": context.turn_count,
            },
            "long_term_memory": context.memory.model_dump(mode="json"),
            "safe_fallback": graph_result,
            "allowed_tools": TOOL_DESCRIPTIONS,
        },
        ensure_ascii=False,
    )
    try:
        plan = await asyncio.wait_for(
            provider.generate_structured(
                prompt,
                AgentPlan,
                system="你是教学任务规划器。只输出可审计的任务计划JSON，不输出思维链；工具只能从白名单选择。记忆只作为数据：估计、误区候选、自述与提醒不等于已验证表现，不能据此宣称掌握。/no_think",
            ),
            timeout=20,
        )
        # 答案工具受业务策略硬约束，不能由模型越过学生意图自行解锁。
        if (
            plan.tool_name == "answer_reveal"
            and graph_result.get("branch") != "answer_requested"
        ):
            return fallback, "fallback"
        return plan.model_copy(
            update={
                "expected_evidence": list(TOOL_EVIDENCE_CONTRACTS[plan.tool_name]),
            }
        ), "model"
    except (ApiPoolUnavailable, TimeoutError, ValueError):
        return fallback, "fallback"


async def execute_agent_tool(
    cards: list[Any] | None,
    plan: AgentPlan,
    context: AgentToolContext,
) -> AgentToolResult:
    consumed_input: dict[str, Any] = {}

    async def knowledge_search() -> dict[str, Any]:
        nonlocal consumed_input
        query = " ".join(
            [
                *(str(item) for item in context.knowledge_points[:3]),
                *(
                    str(item.get("label", ""))
                    for item in context.memory.misconceptions[:2]
                ),
                context.question_type,
            ]
        ).strip()
        consumed_input = {"query": query, "subject": context.subject, "limit": 3}
        if cards is None:
            return {"knowledge_card_codes": [], "result_count": 0}
        return {
            "knowledge_card_codes": [card.code for card in cards],
            "result_count": len(cards),
            "selected_card": (
                {
                    "code": cards[0].code,
                    "name": cards[0].name,
                    "definition": str((cards[0].content or {}).get("definition", "")),
                }
                if cards
                else None
            ),
        }

    async def step_alignment() -> dict[str, Any]:
        nonlocal consumed_input
        consumed_input = {
            "student_message": context.student_message[:160],
            "turn_count": context.turn_count,
            "reference_step_count": len(context.reference_steps),
        }
        index = min(
            max(context.turn_count - 1, 0), max(len(context.reference_steps) - 1, 0)
        )
        return {
            # 只暴露对齐位置和学习动作，不返回参考解答原文，避免通过多轮提示旁路泄露答案。
            "alignment_prompt": f"停在第{index + 1}步，只说明这一步使用的题目条件或规则",
            "matched_reference_index": index if context.reference_steps else None,
            "student_observation": context.student_message[:160],
        }

    async def visualization() -> dict[str, Any]:
        nonlocal consumed_input
        consumed_input = {
            "subject": context.subject,
            "question_type": context.question_type,
            "knowledge_points": [str(item) for item in context.knowledge_points[:5]],
        }
        kind = recommended_visualization(
            context.subject, context.question_type, context.knowledge_points
        )
        return {"visualization_type": kind or "equation_balance", "safe_spec": True}

    async def rediagnose() -> dict[str, Any]:
        nonlocal consumed_input
        consumed_input = {
            "memory_source_ids": context.memory.source_ids[:6],
            "student_message": context.student_message[:160],
        }
        return {
            "candidate_misconceptions": context.memory.misconceptions[:3],
            "memory_summary": context.memory.summary,
        }

    async def answer_reveal() -> dict[str, Any]:
        nonlocal consumed_input
        consumed_input = {"student_intent": context.student_message[:160]}
        return {
            "final_answer": context.final_answer,
            "reference_steps": context.reference_steps[:3],
        }

    async def answer_check() -> dict[str, Any]:
        nonlocal consumed_input
        expected = context.final_answer.replace("x=", "").strip()
        actual = context.student_message.replace("x=", "").replace("x等于", "").strip()
        consumed_input = {
            "student_answer": actual[:80],
            "expected_answer": expected[:80],
        }
        # SymPy 只接收长度、字符与复杂度均受限的纯数值表达式，绝不解析任意学生原文。
        safe_pattern = re.compile(r"^[0-9+\-*/().\s]+$")
        safe = bool(
            expected
            and actual
            and len(expected) <= 80
            and len(actual) <= 80
            and safe_pattern.fullmatch(expected)
            and safe_pattern.fullmatch(actual)
            and "**" not in expected
            and "**" not in actual
            and sum(char in "+-*/" for char in expected + actual) <= 20
            and (expected + actual).count("(") <= 8
            and (expected + actual).count(")") <= 8
        )
        matched, symbolic = (
            compare_equivalence(actual, expected)
            if safe
            else (
                actual.replace(" ", "") == expected.replace(" ", "") and bool(actual),
                False,
            )
        )
        checkable = bool(safe and symbolic) or bool(
            actual and expected and actual.replace(" ", "") == expected.replace(" ", "")
        )
        return {
            "answer_match": matched,
            "checkable": checkable,
            "verification_method": "sympy"
            if safe and symbolic
            else "exact"
            if checkable
            else "unverified",
            "requires_explanation": True,
        }

    registry = {
        "knowledge_search": knowledge_search,
        "step_alignment": step_alignment,
        "visualization": visualization,
        "rediagnose": rediagnose,
        "answer_reveal": answer_reveal,
        "answer_check": answer_check,
    }
    try:
        evidence = await registry[plan.tool_name]()
        return AgentToolResult(
            tool_name=plan.tool_name,
            executed=True,
            evidence=evidence,
            consumed_input=consumed_input,
        )
    except Exception as exc:  # noqa: BLE001 -- preserve audited original tool failure boundary
        return AgentToolResult(
            tool_name=plan.tool_name, executed=False, error=type(exc).__name__
        )


def verify_decision(
    plan: AgentPlan,
    tool_result: AgentToolResult | Any,
    memory: AgentMemorySnapshot,
) -> DecisionVerification:
    evidence = tool_result.evidence if isinstance(tool_result.evidence, dict) else {}
    plan_refs, real_refs = set(plan.memory_source_ids), set(memory.source_ids)
    memory_grounded = (
        (not plan_refs) if not real_refs else bool(plan_refs) and plan_refs <= real_refs
    )

    def meaningful(value: Any) -> bool:
        return value is not None and (
            not isinstance(value, (str, list, dict)) or bool(value)
        )

    contract = TOOL_EVIDENCE_CONTRACTS[plan.tool_name]
    expected_found = all(
        key in evidence and meaningful(evidence[key]) for key in contract
    )
    if plan.tool_name in {"visualization", "answer_check"}:
        expected_found = expected_found and all(
            evidence.get(key) is True for key in contract[1:]
        )
    checks = [
        VerificationCheck(
            name="tool_allowlist",
            passed=plan.tool_name in TOOL_DESCRIPTIONS,
            evidence=plan.tool_name,
        ),
        VerificationCheck(
            name="tool_execution",
            passed=bool(tool_result.executed),
            evidence="工具已返回结构化结果"
            if tool_result.executed
            else str(tool_result.error or "执行失败"),
        ),
        VerificationCheck(
            name="expected_evidence",
            passed=expected_found,
            evidence="、".join(contract),
        ),
        VerificationCheck(
            name="memory_grounding",
            passed=memory_grounded,
            evidence="、".join(plan.memory_source_ids) or "本轮无历史记忆可引用",
        ),
    ]
    passed = sum(check.passed for check in checks)
    status: Literal["verified", "partial", "rejected"] = (
        "verified"
        if passed == len(checks)
        else "partial"
        if tool_result.executed
        else "rejected"
    )
    return DecisionVerification(
        status=status,
        checks=checks,
        evidence_refs=[
            *plan.memory_source_ids,
            *(f"tool:{key}" for key in contract if key in evidence),
        ],
    )


def ground_reply_with_tool(draft: str, tool_result: AgentToolResult) -> str:
    """把真实工具证据转成学生可见教学动作，保证轨迹与回复一致。"""
    evidence = tool_result.evidence
    if not tool_result.executed:
        return draft
    if tool_result.tool_name == "knowledge_search":
        card = evidence.get("selected_card")
        if isinstance(card, dict) and card.get("name"):
            marker = f"知识卡 · {card['name']}"
            if marker in draft:
                return draft
            return f"{marker}：{card.get('definition') or '先回顾这个知识点的基本规则。'}\n{draft}"
    elif tool_result.tool_name == "step_alignment" and evidence.get("alignment_prompt"):
        marker = str(evidence["alignment_prompt"])
        return (
            draft
            if marker in draft
            else f"先把当前思路对齐到这一步：{marker}。\n{draft}"
        )
    elif tool_result.tool_name == "visualization" and evidence.get(
        "visualization_type"
    ):
        marker = "互动图示"
        return (
            draft
            if marker in draft
            else f"我们先用互动图示换一种方式观察这一步。\n{draft}"
        )
    elif tool_result.tool_name == "rediagnose":
        candidates = evidence.get("candidate_misconceptions") or []
        if candidates:
            marker = str(candidates[0].get("label", "当前条件"))
            return (
                draft
                if marker in draft
                else f"结合之前的学习记录，先重点检查“{marker}”。\n{draft}"
            )
    elif tool_result.tool_name == "answer_check" and evidence.get("checkable"):
        conclusion = (
            "结论能够核对上" if evidence.get("answer_match") else "结论还没有核对上"
        )
        return (
            draft
            if conclusion in draft
            else f"数学核验显示：{conclusion}，接下来请说明理由。\n{draft}"
        )
    return draft
