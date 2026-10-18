from types import SimpleNamespace

import pytest

import app.services.agent_runtime as agent_runtime
from app.services.agent_runtime import (
    AgentMemorySnapshot,
    AgentPlan,
    AgentToolContext,
    build_memory_snapshot,
    execute_agent_tool,
    ground_reply_with_tool,
    plan_agent_turn,
    verify_decision,
)


def test_build_memory_snapshot_keeps_compact_traceable_learning_evidence():
    snapshot = build_memory_snapshot(
        mastery_rows=[
            SimpleNamespace(
                id="m1",
                knowledge_point="限制条件",
                mastery_score=0.42,
                confidence=0.8,
                forgetting_risk=0.71,
            )
        ],
        misconception_rows=[
            SimpleNamespace(
                id="e1",
                code="constraint_missed",
                label="遗漏限制条件",
                probability=0.76,
                status="active",
                successful_strategy="画条件表",
            )
        ],
        cognitive_rows=[
            SimpleNamespace(
                id="c1",
                entity_type="misconception",
                entity_key="constraint_missed",
                old_value=0.8,
                new_value=0.76,
                reason="相似题仍需提示",
            )
        ],
        review_rows=[SimpleNamespace(id="r1", reason="高遗忘风险", interval_days=2)],
    )

    assert snapshot.source_ids == ["mastery:m1", "misconception:e1", "cognitive:c1", "review:r1"]
    assert snapshot.mastery[0]["knowledge_point"] == "限制条件"
    assert snapshot.misconceptions[0]["successful_strategy"] == "画条件表"
    assert "遗漏限制条件" in snapshot.summary


@pytest.mark.asyncio
async def test_dynamic_tool_registry_executes_the_selected_allowlisted_tool():
    plan = AgentPlan(
        goal="换一种表示方式定位重复错误",
        steps=["读取历史误区", "生成适配图示", "检查是否提供证据"],
        tool_name="visualization",
        tool_input={"focus": "等量关系"},
        expected_evidence=["visualization_type"],
        decision_summary="重复出错时切换为图形化讲解",
        memory_source_ids=["misconception:e1"],
        confidence=0.86,
    )
    context = AgentToolContext(
        subject="数学",
        question_type="方程题",
        question_text="2x+1=5",
        final_answer="x=2",
        reference_steps=["移项", "求解"],
        student_message="我还是不会",
        turn_count=2,
        knowledge_points=["一元一次方程"],
        memory=AgentMemorySnapshot(source_ids=["misconception:e1"]),
    )

    result = await execute_agent_tool(None, plan, context)

    assert result.tool_name == "visualization"
    assert result.executed is True
    assert result.evidence["visualization_type"]
    assert result.consumed_input["subject"] == "数学"


def test_verification_rejects_untraceable_memory_and_accepts_grounded_evidence():
    memory = AgentMemorySnapshot(source_ids=["mastery:m1"])
    plan = AgentPlan(
        goal="补齐基础",
        steps=["读取记忆", "检索知识卡"],
        tool_name="knowledge_search",
        tool_input={},
        expected_evidence=["knowledge_card_codes"],
        decision_summary="根据薄弱知识点补齐前置知识",
        memory_source_ids=["mastery:m1"],
        confidence=0.8,
    )
    tool_result = SimpleNamespace(
        tool_name="knowledge_search",
        executed=True,
        evidence={"knowledge_card_codes": ["math.eq.1"]},
        error=None,
    )

    verified = verify_decision(plan, tool_result, memory)
    assert verified.status == "verified"
    assert all(check.passed for check in verified.checks)

    plan.memory_source_ids = ["mastery:not-exists"]
    partial = verify_decision(plan, tool_result, memory)
    assert partial.status == "partial"
    assert any(check.name == "memory_grounding" and not check.passed for check in partial.checks)

    plan.memory_source_ids = ["mastery:m1", "mastery:not-exists"]
    mixed = verify_decision(plan, tool_result, memory)
    assert mixed.status == "partial"


def test_tool_evidence_really_drives_student_reply():
    result = SimpleNamespace(
        executed=True,
        tool_name="step_alignment",
        evidence={"alignment_prompt": "停在第1步，只说明这一步使用的题目条件或规则"},
    )
    reply = ground_reply_with_tool("先检查当前这一步。", result)
    assert "只说明这一步使用的题目条件或规则" in reply
    assert "移项" not in reply


@pytest.mark.asyncio
async def test_step_alignment_never_exposes_reference_solution_text():
    plan = AgentPlan(
        goal="对齐步骤",
        steps=["检查当前依据"],
        tool_name="step_alignment",
        expected_evidence=["alignment_prompt"],
        decision_summary="只提示当前依据",
        confidence=0.8,
    )
    context = AgentToolContext(
        subject="数学",
        question_type="方程题",
        question_text="2x=4",
        final_answer="x=2",
        reference_steps=["两边同除以2", "最终答案是x=2"],
        student_message="下一步呢",
        turn_count=2,
    )

    result = await execute_agent_tool(None, plan, context)
    reply = ground_reply_with_tool("先检查当前一步。", result)

    assert "x=2" not in str(result.evidence)
    assert "最终答案" not in reply


@pytest.mark.asyncio
async def test_planner_cannot_reveal_answer_without_explicit_student_intent():
    class UnsafePlanner:
        async def generate_structured(self, prompt, schema, system):
            return AgentPlan(
                goal="直接展示答案",
                steps=["展示答案"],
                tool_name="answer_reveal",
                expected_evidence=["reference_steps"],
                decision_summary="模型想直接给答案",
                confidence=0.99,
            )

    context = AgentToolContext(
        subject="数学",
        question_type="方程题",
        question_text="2x=4",
        final_answer="x=2",
        reference_steps=["两边同除以2"],
        student_message="给我一个提示",
        turn_count=1,
    )
    graph = {"branch": "hint_requested", "tool_name": "step_alignment", "next_goal": "给一个小提示"}

    plan, status = await plan_agent_turn(UnsafePlanner(), graph, context)

    assert status == "fallback"
    assert plan.tool_name == "step_alignment"


@pytest.mark.asyncio
async def test_answer_check_never_sends_arbitrary_student_text_to_sympy(monkeypatch):
    def forbidden(*args):
        raise AssertionError("untrusted text reached SymPy")

    monkeypatch.setattr(agent_runtime, "compare_equivalence", forbidden)
    plan = AgentPlan(
        goal="核对答案",
        steps=["安全核验"],
        tool_name="answer_check",
        expected_evidence=["answer_match"],
        decision_summary="核对结论",
        confidence=0.8,
    )
    context = AgentToolContext(
        subject="数学",
        question_type="计算题",
        question_text="2x=4",
        final_answer="x=2",
        reference_steps=[],
        student_message="__import__('os').system('id')",
        turn_count=1,
    )

    result = await execute_agent_tool(None, plan, context)

    assert result.executed is True
    assert result.evidence["checkable"] is False
    assert result.evidence["verification_method"] == "unverified"
