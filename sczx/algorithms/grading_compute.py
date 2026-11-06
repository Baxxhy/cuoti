"""Grade supplied answers without loading any business database or state."""

import asyncio
import re

from inequality_compute import grade_inequality
from learning_core.providers.api_pool import ApiPoolUnavailable
from learning_core.services.grading import grade_answer as original_grade_answer


def angular_answer(value):
    if not isinstance(value, str) or "\n" in value or len(value) > 120:
        return None
    raw = (
        re.sub(r"\s+", "", value)
        .replace(r"\angle", "∠")
        .replace(r"^{\circ}", "°")
        .replace(r"^\circ", "°")
        .replace(r"\circ", "°")
    )
    if raw.startswith("$") and raw.endswith("$"):
        raw = raw[1:-1]
    match = re.fullmatch(
        r"(?:∠([A-Z]{1,3})[=＝])?([+-]?\d{1,3}(?:\.\d{1,3})?)(?:°|度)[。.]?", raw
    )
    return (match.group(1) or "", match.group(2) + "°") if match else None


async def grade_answer(provider, *, question, answer, expected, subject, **kwargs):
    if subject == "数学" and not kwargs.get("options"):
        checked = await asyncio.to_thread(grade_inequality, question, answer, expected)
        if checked is not None:
            return checked
    left, right = angular_answer(answer), angular_answer(expected)
    if subject == "数学" and left and right:
        target = right[0]
        if not target:
            requested = re.search(
                r"(?:求|计算)\s*∠([A-Z]{1,3})", question.replace(r"\angle", "∠")
            )
            target = requested.group(1) if requested else ""

        def key(label):
            triangles = re.findall(r"(?:三角形|△)\s*([A-Z]{3})", question)
            if len(set(triangles)) == 1 and (
                len(label) == 1
                and label in triangles[0]
                or len(label) == 3
                and len(set(label)) == 3
                and set(label) == set(triangles[0])
            ):
                return label if len(label) == 1 else label[1]
            return label

        if not left[0] or (target and key(left[0]) == key(target)):
            result = await original_grade_answer(
                provider,
                question=question,
                answer=left[1][:-1],
                expected=right[1][:-1],
                subject=subject,
                **kwargs,
            )
            result["expected_answer"] = expected
            result["recognized_answer"] = answer
            result["evidence"] = [
                *result.get("evidence", []),
                "单个角度数值及标准度数单位规范化；保留角标和原始作答",
            ]
            return result
    return await original_grade_answer(
        provider,
        question=question,
        answer=answer,
        expected=expected,
        subject=subject,
        **kwargs,
    )


class UnavailableGradingProvider:
    async def generate_structured(self, *args, **kwargs):
        raise ApiPoolUnavailable("模型池尚未就绪")

    async def generate_multimodal(self, *args, **kwargs):
        raise ApiPoolUnavailable("模型池尚未就绪")
