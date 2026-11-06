from __future__ import annotations

import json
import re
from typing import Any

from learning_core.providers.api_pool import ApiPoolProvider, ApiPoolUnavailable
from learning_core.schemas import (
    AdaptiveTeachingBrief,
    TutorActivityDefinition,
    TutorActivityOption,
    TutorActivityPlan,
    TutorOptionExplanation,
)
from learning_core.services.academic_text import academic_summary
from learning_core.services.pedagogy import pedagogy_for
from learning_core.services.question_mapping import student_facing_topic

SHORT_QUESTION_TYPES = {
    "choice",
    "multiple_choice",
    "fill_blank",
    "单选题",
    "多选题",
    "选择题",
    "填空题",
}






def _option_payload(options: list[Any] | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, raw in enumerate(options or []):
        item = raw if isinstance(raw, dict) else {"text": str(raw)}
        label = str(item.get("label") or item.get("key") or chr(65 + index)).strip().upper()
        text = str(item.get("text") or item.get("value") or "").strip()
        if text:
            rows.append({"label": label[:8], "text": text})
    return rows


def choice_answer_label(answer: str | None, options: list[Any] | None) -> str:
    text = str(answer or "").strip()
    labels = [item["label"] for item in _option_payload(options)]
    matched = re.findall(r"(?<![A-Za-z])[A-H](?![A-Za-z])", text.upper())
    if matched:
        selected = [label for label in matched if label in labels]
        if selected:
            return "".join(selected)
    compact = re.sub(r"\s+", "", text)
    for item in _option_payload(options):
        if compact and compact == re.sub(r"\s+", "", item["text"]):
            return item["label"]
    return text


def _bounded(value: str, limit: int) -> str:
    compact = " ".join(str(value or "").split())
    return compact if len(compact) <= limit else compact[: max(1, limit - 1)].rstrip("，。；：") + "。"


def _fallback_brief(
    *,
    question_text: str,
    options: list[Any] | None,
    correct_answer: str,
    student_answer: str,
    diagnosis: dict[str, Any],
    knowledge_points: list[Any] | None,
    question_type: str,
) -> AdaptiveTeachingBrief:
    rows = _option_payload(options)
    correct_label = choice_answer_label(correct_answer, rows)
    selected_label = choice_answer_label(student_answer, rows)
    topic = student_facing_topic(knowledge_points, "choice")
    reciprocal = "倒数" in " ".join([question_text, *[item["text"] for item in rows]])
    explanations: list[TutorOptionExplanation] = []
    for item in rows:
        label = item["label"]
        if reciprocal and "0" in item["text"]:
            explanation = "0没有倒数。"
        elif label == correct_label:
            explanation = "符合倒数定义和题目条件。" if reciprocal else "符合题目条件。"
        elif label == selected_label and diagnosis.get("root_misconception"):
            explanation = str(diagnosis["root_misconception"])
        else:
            explanation = "不符合题目中的关键条件。"
        explanations.append(
            TutorOptionExplanation(
                label=label, text=_bounded(explanation, 35), correct=label == correct_label
            )
        )
    if reciprocal:
        check = TutorActivityDefinition(
            id="targeted-check",
            type="single_choice",
            title="只确认这个易错点",
            question="下面哪个数没有倒数？",
            options=[
                TutorActivityOption(value="A", label="A  -1"),
                TutorActivityOption(value="B", label="B  0"),
                TutorActivityOption(value="C", label="C  1/2"),
                TutorActivityOption(value="D", label="D  2"),
            ],
            correct_answers=["B"],
            hint="倒数要求两个数的乘积等于1。",
            teaching="0乘任何数都不等于1，所以0没有倒数。",
        )
    elif rows:
        focus = str(diagnosis.get("first_error_text") or diagnosis.get("root_misconception") or topic)
        check = TutorActivityDefinition(
            id="targeted-check",
            type="single_choice",
            title="确认刚才的关键点",
            question=_bounded(f"遇到同类题，哪项最需要检查：{focus}？", 45),
            options=[
                TutorActivityOption(value="key", label=_bounded(focus, 35)),
                TutorActivityOption(value="guess", label="跳过条件，直接猜答案"),
            ],
            correct_answers=["key"],
            hint=_bounded(str(diagnosis.get("recommended_strategy") or "回到题目条件检查。"), 70),
            teaching=_bounded(focus, 120),
        )
    else:
        focus = str(diagnosis.get("first_error_text") or diagnosis.get("root_misconception") or topic)
        check = TutorActivityDefinition(
            id="targeted-check",
            type="short_answer",
            title="换个数再确认一次",
            question=_bounded(f"用刚才的方法再判断一次：{focus}", 45),
            correct_answers=[correct_answer],
            hint="只写最后结果即可。",
            teaching=_bounded(focus, 120),
        )
    key = str(
        diagnosis.get("first_error_text") or diagnosis.get("root_misconception") or "关键条件没有判断完整"
    )
    return AdaptiveTeachingBrief(
        topic=_bounded(topic, 24),
        correct_answer=correct_label or correct_answer,
        key_explanation=_bounded(key, 120),
        option_explanations=explanations,
        check=check,
    )


async def build_adaptive_teaching_brief(
    provider: ApiPoolProvider,
    *,
    question_text: str,
    options: list[Any] | None,
    correct_answer: str,
    student_answer: str,
    diagnosis: dict[str, Any],
    student_steps: list[str] | None,
    knowledge_points: list[Any] | None,
    question_type: str,
) -> AdaptiveTeachingBrief:
    fallback = _fallback_brief(
        question_text=question_text,
        options=options,
        correct_answer=correct_answer,
        student_answer=student_answer,
        diagnosis=diagnosis,
        knowledge_points=knowledge_points,
        question_type=question_type,
    )
    context = json.dumps(
        {
            "question_text": question_text,
            "options": _option_payload(options),
            "correct_answer": correct_answer,
            "student_answer": student_answer,
            "diagnosis": diagnosis,
            "student_steps": student_steps or [],
            "knowledge_points": knowledge_points or [],
            "question_type": question_type,
        },
        ensure_ascii=False,
    )
    prompt = (
        "为这道已经答错的中学题生成极短的针对性教学。必须先承认并使用给定正确答案，"
        "围绕学生实际选错的干扰项解释，不从整个章节重新讲。选择题每个选项最多一句。"
        "只生成1个能区分是否修复原错误的新例子检查题，不能复述定义，不能问‘第一步做什么’、"
        "‘你知道了吗’或把答案直接写进问题。教师讲解不超过120个中文字，问题不超过45字，"
        "反馈提示不超过70字，选项不超过35字。check.id固定为targeted-check；"
        "check.type只能按题型使用single_choice、multiple_choice或short_answer。上下文：" + context
    )
    try:
        brief = await provider.generate_structured(
            prompt,
            AdaptiveTeachingBrief,
            system="你是中学错题短教学设计器。只返回合法JSON，不重复、不绕弯、不隐藏可靠答案。/no_think",
        )
    except (ApiPoolUnavailable, ValueError):
        return fallback
    forbidden = ("第一步应该", "应该关注什么", "你知道了吗", "是否理解", "凭感觉")
    if any(text in brief.check.question for text in forbidden):
        brief.check = fallback.check
    brief.topic = _bounded(brief.topic, 24)
    brief.key_explanation = _bounded(brief.key_explanation, 120)
    brief.correct_answer = choice_answer_label(correct_answer, options) or _bounded(correct_answer, 80)
    brief.option_explanations = [
        item.model_copy(update={"text": _bounded(item.text, 35)}) for item in brief.option_explanations
    ]
    brief.check.question = _bounded(brief.check.question, 45)
    brief.check.hint = _bounded(brief.check.hint, 70)
    brief.check.teaching = _bounded(brief.check.teaching, 120)
    normalized_options = []
    answer_map: dict[str, str] = {}
    for item in brief.check.options:
        label, value = str(item.label).strip(), str(item.value).strip()
        if re.fullmatch(r"[A-H]", label.upper()) and not re.fullmatch(r"[A-H]", value.upper()):
            answer_map[value] = label.upper()
            normalized_options.append(
                item.model_copy(
                    update={
                        "value": label.upper(),
                        "label": _bounded(f"{label.upper()}  {value}", 35),
                    }
                )
            )
        else:
            normalized_options.append(item.model_copy(update={"label": _bounded(label, 35)}))
    brief.check.options = normalized_options
    brief.check.correct_answers = [
        answer_map.get(str(value), str(value)) for value in brief.check.correct_answers
    ]
    return brief




def build_understanding_plan(
    *,
    question_text: str,
    subject: str,
    question_type: str,
    knowledge_points: list[Any] | None,
    reference_steps: list[str] | None,
) -> list[dict[str, Any]]:
    points = [str(item) for item in (knowledge_points or []) if str(item).strip()]
    references = [str(item) for item in (reference_steps or []) if str(item).strip()]
    context = " ".join([question_text, *points, *references])
    if "正方体" in context and ("展开图" in context or "相对面" in context):
        cube_net = {
            "type": "cube_net",
            "cells": [
                {"x": 0, "y": 0, "label": "1"},
                {"x": 1, "y": 0, "label": "3"},
                {"x": 1, "y": 1, "label": "x"},
                {"x": 2, "y": 1, "label": "y"},
                {"x": 2, "y": 2, "label": "z"},
                {"x": 3, "y": 2, "label": "4"},
            ],
        }
        plan = TutorActivityPlan(
            activities=[
                TutorActivityDefinition(
                    id="understanding-1",
                    type="single_choice",
                    title="先找出一组相对面",
                    question="图中 x 所在面与哪个数字面相对？",
                    options=[
                        TutorActivityOption(value="1", label="1"),
                        TutorActivityOption(value="3", label="3"),
                        TutorActivityOption(value="4", label="4"),
                    ],
                    correct_answers=["4"],
                    hint="沿着展开图想象折叠，x 与 4 会落在正方体两侧。",
                    teaching="判断相对面时，可以看“相间”关系，也可以沿 Z 字两端想象折叠。",
                    visual=cube_net,
                ),
                TutorActivityDefinition(
                    id="understanding-2",
                    type="single_choice",
                    title="再确认另一组相对面",
                    question="图中数字 1 所在面与哪个字母面相对？",
                    options=[
                        TutorActivityOption(value="x", label="x"),
                        TutorActivityOption(value="y", label="y"),
                        TutorActivityOption(value="z", label="z"),
                    ],
                    correct_answers=["y"],
                    hint="从数字 1 沿展开图折起，和它正对的是 y。",
                    teaching="相对面折叠后不会共用一条棱，而是分别位于正方体两侧。",
                    visual=cube_net,
                ),
                TutorActivityDefinition(
                    id="understanding-3",
                    type="single_choice",
                    title="把相对关系用到计算中",
                    question="相对面上的两个数之和为 5，求得 x=1、y=4，那么 x+y 等于多少？",
                    options=[
                        TutorActivityOption(value="3", label="3"),
                        TutorActivityOption(value="5", label="5"),
                        TutorActivityOption(value="7", label="7"),
                    ],
                    correct_answers=["5"],
                    hint="把 x=1 和 y=4 直接相加。",
                    teaching="先判断相对面，再分别列出和为 5 的关系，最后计算 x+y。",
                    visual=cube_net,
                ),
            ]
        )
        return [item.model_dump(mode="json") for item in plan.activities]

    profile = pedagogy_for(subject)
    topic = points[0] if points else student_facing_topic([], question_type)
    first_reference = references[0] if references else profile.guided_prompt
    plan = TutorActivityPlan(
        activities=[
            TutorActivityDefinition(
                id="understanding-1",
                type="single_choice",
                title=f"先抓住{topic}",
                question="完成这道题时，第一步最应该关注什么？",
                options=[
                    TutorActivityOption(value="key", label=topic),
                    TutorActivityOption(value="answer", label="只记住最后答案"),
                    TutorActivityOption(value="skip", label="跳过题目条件直接计算"),
                ],
                correct_answers=["key"],
                hint=f"先回到题目条件，找到与{topic}直接相关的信息。",
                teaching=f"这道题先围绕“{topic}”判断，再继续后面的步骤。",
            ),
            TutorActivityDefinition(
                id="understanding-2",
                type="single_choice",
                title="确认下一步做法",
                question="下面哪种做法更合适？",
                options=[
                    TutorActivityOption(value="reference", label=academic_summary(first_reference, 42)),
                    TutorActivityOption(value="guess", label="不看条件，凭印象猜一个答案"),
                ],
                correct_answers=["reference"],
                hint=profile.guided_prompt,
                teaching=f"关键做法是：{first_reference}",
            ),
        ]
    )
    return [item.model_dump(mode="json") for item in plan.activities]


def activity_public(
    activity: dict[str, Any], *, attempt: int, feedback: str = "", teaching: str = ""
) -> dict[str, Any]:
    result = {
        "id": activity["id"],
        "type": activity["type"],
        "title": activity["title"],
        "question": activity["question"],
        "options": activity.get("options", []),
        "attempt": attempt,
        "max_attempts": 2,
        "feedback": feedback,
        "teaching": teaching or activity.get("teaching", ""),
        "teaching_title": activity.get("teaching_title", ""),
        "sentence_starter": activity.get("sentence_starter", ""),
        "keywords": activity.get("keywords", []),
        "variant_id": activity.get("variant_id"),
        "visual": activity.get("visual", {}),
        "input_mode": activity.get("input_mode", ""),
    }
    return {
        key: value
        for key, value in result.items()
        if key in {"options", "keywords", "visual"} or value not in (None, "")
    }
