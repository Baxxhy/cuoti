"""Two-phase tutoring computation. Cangjie owns database reads, tools and persistence."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Annotated

from pydantic import BaseModel, Field, JsonValue

from agent_compute import (
    AgentMemorySnapshot,
    AgentPlan,
    AgentToolContext,
    AgentTurnResult,
    ValidatedAgentMemorySnapshot,
    build_memory_snapshot,
    execute_agent_tool,
    ground_reply_with_tool,
    plan_agent_turn,
    verify_decision,
)
from grounded_knowledge import build_knowledge_evidence
from learning_core.services.ai_pipeline import generate_tutor_guidance
from learning_core.services.tutor_graph import ensure_fresh_tutor_reply, run_tutor_step
from learning_memory_compute import LearningMemorySnapshot

Text = Annotated[str, Field(max_length=12000)]


class DialogueContext(BaseModel):
    memory_snapshot: LearningMemorySnapshot | None = None
    subject: str = Field(default="数学", max_length=30)
    question_type: str = Field(default="综合题", max_length=50)
    grade: str = Field(default="", max_length=30)
    question_text: Text = ""
    final_answer: Text = ""
    reference_steps: list[Text] = Field(default_factory=list, max_length=100)
    student_message: Text
    turn_count: int = Field(ge=1, le=2147483647)
    hint_level: int = Field(default=0, ge=0, le=2147483647)
    repeated_count: int = Field(default=0, ge=0, le=2147483647)
    knowledge_points: list[JsonValue] = Field(default_factory=list, max_length=100)
    student_answer: str | None = Field(default=None, max_length=12000)
    student_steps: list[Text] = Field(default_factory=list, max_length=100)
    recent_turns: list[dict[str, str]] = Field(default_factory=list, max_length=8)


def context_value(data: DialogueContext, memory: AgentMemorySnapshot):
    return AgentToolContext(
        subject=data.subject,
        question_type=data.question_type,
        question_text=data.question_text,
        final_answer=data.final_answer,
        reference_steps=data.reference_steps,
        student_message=data.student_message,
        turn_count=data.turn_count,
        knowledge_points=data.knowledge_points,
        memory=memory,
    )


async def prepare_dialogue(
    provider, data: DialogueContext, rows: dict[str, list[dict[str, JsonValue]]]
):
    memory = build_memory_snapshot(
        *[
            [SimpleNamespace(**item) for item in rows.get(key, [])]
            for key in ["mastery", "misconceptions", "updates", "reviews"]
        ]
    )
    if data.memory_snapshot is not None:
        memory = ValidatedAgentMemorySnapshot.model_validate(
            {
                **memory.model_dump(),
                "summary": data.memory_snapshot.summary,
                "source_ids": data.memory_snapshot.refs,
                "source_versions": data.memory_snapshot.versions,
                "evidence": [
                    entry.model_dump(mode="json")
                    for entry in data.memory_snapshot.entries
                ],
            }
        )
    graph = run_tutor_step(
        data.turn_count,
        data.student_message,
        data.hint_level,
        data.repeated_count,
        data.model_dump(),
    )
    context = context_value(data, memory)
    plan, status = await plan_agent_turn(provider, dict(graph), context)
    query = " ".join(
        [
            *(str(item) for item in context.knowledge_points[:3]),
            *(str(item.get("label", "")) for item in memory.misconceptions[:2]),
            data.question_type,
            data.student_message,
            data.question_text,
        ]
    ).strip()
    return {
        "graph": dict(graph),
        "memory": memory.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "planner_status": status,
        "knowledge_query": query,
    }


async def finish_dialogue(
    provider,
    data: DialogueContext,
    preparation: dict[str, JsonValue],
    cards: list[dict[str, JsonValue]],
    image_bytes: list[bytes],
):
    memory = (
        ValidatedAgentMemorySnapshot
        if data.memory_snapshot is not None
        else AgentMemorySnapshot
    ).model_validate(preparation["memory"])
    plan = AgentPlan.model_validate(preparation["plan"])
    graph = preparation["graph"]
    context = context_value(data, memory)
    tool = await execute_agent_tool(
        [SimpleNamespace(**item) for item in cards], plan, context
    )
    verification = verify_decision(plan, tool, memory)
    result = AgentTurnResult(
        observation={
            "subject": data.subject,
            "question_type": data.question_type,
            "turn_count": data.turn_count,
            "memory_count": len(memory.source_ids),
            "memory_summary": memory.summary,
        },
        plan=plan,
        tool=tool,
        verification=verification,
        planner_status=preparation["planner_status"],
    )
    draft = ground_reply_with_tool(graph["reply"], tool)
    sources = build_knowledge_evidence(cards, data.subject, data.grade)
    graph_rag = tool.tool_name == "knowledge_search" and any("retrieval_role" in card for card in cards)
    if graph_rag:
        draft = graph["reply"]

    with TemporaryDirectory(prefix="zhiwei-tutor-guidance-") as directory:
        paths = []
        for index, raw in enumerate(image_bytes):
            path = Path(directory) / f"figure-{index}.jpg"
            path.write_bytes(raw)
            paths.append(path)
        reply = await generate_tutor_guidance(
            provider,
            visual_paths=paths,
            question_text=data.question_text,
            student_answer=data.student_answer,
            student_steps=data.student_steps,
            subject=data.subject,
            question_type=data.question_type,
            draft_reply=draft,
            student_message=data.student_message,
            recent_turns=data.recent_turns,
            reveal_answer=graph["tool_name"] == "answer_reveal",
            retrieved_knowledge=sources,
        )
    reply = ensure_fresh_tutor_reply(
        reply,
        draft,
        [row["content"] for row in data.recent_turns if row.get("role") == "assistant"],
        subject=data.subject,
        branch=graph["branch"],
        turn_count=data.turn_count,
    )
    if not graph_rag:
        reply = ground_reply_with_tool(reply, tool)
    # Preserve complete conditions and math. Presentation may disclose long guidance
    # progressively, but a character budget must never alter teaching content.
    return {"reply": reply, "graph": graph, "agent": result.model_dump(mode="json"), "knowledge_sources": sources}
