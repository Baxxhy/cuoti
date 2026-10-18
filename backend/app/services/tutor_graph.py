from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Literal, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from app.services.pedagogy import pedagogy_for


class TutorGraphState(TypedDict):
    turn_count: int
    student_message: str
    stage: str
    hint_level: int
    repeated_count: int
    reply: str
    branch: str
    strategy: str
    next_goal: str
    tool_name: str
    mastery_proven: bool
    subject: str
    question_type: str
    question_text: str
    final_answer: str
    reference_steps: list[str]


AnyBranch = Literal[
    "completely_unknown",
    "hint_requested",
    "partial_correct",
    "repeated_error",
    "new_error",
    "answer_requested",
    "correct_but_unclear",
    "guided_question",
]


def _update(state: TutorGraphState, **changes: Any) -> None:
    cast(dict[str, Any], state).update(changes)


def evaluate(state: TutorGraphState) -> TutorGraphState:
    message = state["student_message"].strip().lower()
    answer = "".join(state["final_answer"].lower().replace("等于", "=").split())
    compact = "".join(message.replace("等于", "=").split())
    if any(word in message for word in ("直接告诉", "给答案", "答案是什么", "只要答案")):
        state["branch"] = "answer_requested"
    elif any(word in message for word in ("不会", "不知道", "不懂", "没学过")):
        state["branch"] = "completely_unknown"
    elif state["repeated_count"] >= 1:
        state["branch"] = "repeated_error"
    elif any(word in message for word in ("提示", "什么方法", "怎么做", "从哪开始")):
        state["branch"] = "hint_requested"
    elif any(word in message for word in ("新错误", "另外", "单位", "我又觉得")):
        state["branch"] = "new_error"
    elif (
        answer and answer in compact and not any(word in message for word in ("因为", "所以", "根据", "说明"))
    ):
        state["branch"] = "correct_but_unclear"
    elif any(word in message for word in ("但", "然后呢", "下一步", "部分", "我觉得")):
        state["branch"] = "partial_correct"
    else:
        state["branch"] = "guided_question"
    return state


def route(state: TutorGraphState) -> AnyBranch:
    return cast(AnyBranch, state["branch"])


def completely_unknown(state: TutorGraphState) -> TutorGraphState:
    profile = pedagogy_for(state["subject"])
    _update(
        state,
        stage="understanding",
        hint_level=1,
        strategy="prerequisite_example",
        tool_name="knowledge_search",
        next_goal=f"先补上{profile.reasoning_focus}的基础",
        mastery_proven=False,
        reply=f"没关系，我们先把题目拆小。{profile.prerequisite_prompt}你先说出其中一项就可以。",
    )
    return state


def hint_requested(state: TutorGraphState) -> TutorGraphState:
    profile = pedagogy_for(state["subject"])
    message = state["student_message"]
    if "方法" in message:
        reply = f"先不用选完整方法。判断这一步是在用定义、公式还是运算规则，再说出对应的{profile.reasoning_focus}。"
    else:
        reply = f"给你一个小提示：先只找题目中与这一步直接相关的一个条件。它和{profile.reasoning_focus}有什么关系？"
    _update(
        state,
        stage="understanding",
        hint_level=min(3, state["hint_level"] + 1),
        strategy="incremental_hint",
        tool_name="step_alignment",
        next_goal="根据一个小提示继续思考",
        mastery_proven=False,
        reply=reply,
    )
    return state


def partial_correct(state: TutorGraphState) -> TutorGraphState:
    profile = pedagogy_for(state["subject"])
    _update(
        state,
        stage="understanding",
        hint_level=min(3, state["hint_level"] + 1),
        strategy="preserve_correct_part",
        tool_name="step_alignment",
        next_goal="保留正确部分，只修正下一处",
        mastery_proven=False,
        reply=profile.partial_prompt,
    )
    return state


def repeated_error(state: TutorGraphState) -> TutorGraphState:
    profile = pedagogy_for(state["subject"])
    _update(
        state,
        stage="understanding",
        hint_level=min(3, state["hint_level"] + 1),
        strategy="visual_counterexample",
        tool_name="visualization",
        next_goal="换一种表示方法检查原思路",
        mastery_proven=False,
        reply=f"同一个地方又卡住了，我们换一种讲法。{profile.alternate_prompt}",
    )
    return state


def new_error(state: TutorGraphState) -> TutorGraphState:
    _update(
        state,
        stage="understanding",
        hint_level=1,
        strategy="temporary_rediagnosis",
        tool_name="rediagnose",
        next_goal="先处理刚出现的新问题",
        mastery_proven=False,
        reply="这里出现了一个新的偏差。我们先暂停原步骤：请指出这一步用了哪个题目条件、概念或规则，我会据此调整讲解。",
    )
    return state


def answer_requested(state: TutorGraphState) -> TutorGraphState:
    profile = pedagogy_for(state["subject"])
    answer = state["final_answer"] or "请先补充完整题目信息后再核对答案"
    steps = "；".join(state["reference_steps"][:3])
    detail = f"参考过程：{steps}。" if steps else ""
    _update(
        state,
        stage="understanding",
        hint_level=3,
        strategy="answer_with_explanation",
        tool_name="answer_reveal",
        next_goal="解释结论依据以证明真正理解",
        mastery_proven=False,
        reply=f"这道题的参考结论是：{answer}。{detail}看过答案还不等于掌握。{profile.teach_back_prompt}",
    )
    return state


def correct_but_unclear(state: TutorGraphState) -> TutorGraphState:
    profile = pedagogy_for(state["subject"])
    _update(
        state,
        stage="understanding",
        hint_level=1,
        strategy="understanding_check_prompt",
        tool_name="answer_check",
        next_goal="完成明确的理解检查",
        mastery_proven=False,
        reply=f"结论可能是对的，但理由还不够清楚。{profile.teach_back_prompt}",
    )
    return state


def guided_question(state: TutorGraphState) -> TutorGraphState:
    profile = pedagogy_for(state["subject"])
    _update(
        state,
        stage="understanding",
        hint_level=max(1, state["hint_level"]),
        strategy="socratic",
        tool_name="step_alignment",
        next_goal=f"说清{profile.reasoning_focus}中的下一步",
        mastery_proven=False,
        reply=f"先不展开完整答案。{profile.guided_prompt}",
    )
    return state


builder = StateGraph(TutorGraphState)
builder.add_node("evaluate", evaluate)
for name, function in (
    ("completely_unknown", completely_unknown),
    ("hint_requested", hint_requested),
    ("partial_correct", partial_correct),
    ("repeated_error", repeated_error),
    ("new_error", new_error),
    ("answer_requested", answer_requested),
    ("correct_but_unclear", correct_but_unclear),
    ("guided_question", guided_question),
):
    builder.add_node(name, function)
    builder.add_edge(name, END)
builder.add_edge(START, "evaluate")
builder.add_conditional_edges("evaluate", route)
tutor_graph = builder.compile()


def run_tutor_step(
    turn_count: int,
    message: str,
    hint_level: int,
    repeated_count: int = 0,
    context: dict[str, Any] | None = None,
) -> TutorGraphState:
    context = context or {}
    return cast(
        TutorGraphState,
        tutor_graph.invoke(
            {
                "turn_count": turn_count,
                "student_message": message,
                "stage": "understanding",
                "hint_level": hint_level,
                "repeated_count": repeated_count,
                "reply": "",
                "branch": "guided_question",
                "strategy": "socratic",
                "next_goal": "定位下一步",
                "tool_name": "step_alignment",
                "mastery_proven": False,
                "subject": str(context.get("subject", "数学")),
                "question_type": str(context.get("question_type", "综合题")),
                "question_text": str(context.get("question_text", "")),
                "final_answer": str(context.get("final_answer", "")),
                "reference_steps": [str(item) for item in context.get("reference_steps", [])],
            }
        ),
    )


def ensure_fresh_tutor_reply(
    candidate: str,
    draft: str,
    recent_assistant_replies: list[str],
    *,
    subject: str,
    branch: str,
    turn_count: int,
) -> str:
    def normalized(value: str) -> str:
        return "".join(value.lower().split()).replace("，", "").replace("。", "")

    def repeated(value: str) -> bool:
        compact = normalized(value)
        return any(
            SequenceMatcher(None, compact, normalized(previous)).ratio() >= 0.78
            for previous in recent_assistant_replies[-4:]
            if previous.strip()
        )

    if candidate.strip() and not repeated(candidate):
        return candidate.strip()
    if draft.strip() and not repeated(draft):
        return draft.strip()
    profile = pedagogy_for(subject)
    alternatives = {
        "hint_requested": (
            "我们再缩小一步：先圈出这一步直接使用的一个已知条件。",
            "先不要计算，只判断这里应该用定义、公式还是运算规则。",
        ),
        "completely_unknown": (
            f"我们从最小的一步开始：先说出一个已知条件，再判断它和{profile.reasoning_focus}的关系。",
            "暂时不用求答案。先把题目要求你得到的结论说出来。",
        ),
        "guided_question": (
            "换个问法：这一步如果代回原来的条件，结果还成立吗？",
            "先只回答一件事：这一步用了题目中的哪个条件？",
            "把这一步分成两半，先说它的依据，不急着说结论。",
        ),
    }
    choices = alternatives.get(
        branch,
        (
            "我们换一个角度，只检查这一步的依据是否满足题目条件。",
            "先停在当前这一步，说出你最确定的那一部分。",
        ),
    )
    return choices[max(0, turn_count - 1) % len(choices)]
