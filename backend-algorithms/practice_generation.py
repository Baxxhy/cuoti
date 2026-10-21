"""Bounded, source-grounded practice generation; never admit generic study advice."""

import json
import secrets

import sympy as sp
from pydantic import BaseModel, ConfigDict

from learning_core.providers.api_pool import ApiPoolUnavailable
from learning_core.schemas import VariantOutput
from learning_task_compute import linear_source
from variant_compute import generate_variant


class PracticeReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    same_skill: bool
    answer_correct: bool
    self_contained: bool
    grade_appropriate: bool


class UnavailablePracticeProvider:
    async def generate_structured(self, *args, **kwargs):
        raise ApiPoolUnavailable("模型池暂不可用")


def local_practice(subject, text):
    if subject != "数学":
        return None
    source = text.split("\n选项：", 1)[0]
    if linear_source(source) is not None and ("解" in source or "方程" in source):
        a, b, x = (
            secrets.randbelow(8) + 2,
            secrets.randbelow(15) + 1,
            secrets.randbelow(19) - 9,
        )
        c = a * x + b
        while f"解方程：${a}x+{b}={c}$" in text:
            x += 1
            c = a * x + b
        variable = sp.Symbol("x")
        assert sp.solve(a * variable + b - c, variable) == [x]
        return VariantOutput(
            question_text=f"解方程：${a}x+{b}={c}$",
            answer=f"x={x}",
            reference_solution=[
                f"两边同时减去{b}，得{a}x={c - b}",
                f"两边同时除以{a}，得x={x}",
            ],
            explanation=f"先消去常数项，再除以未知数的系数，得到x={x}。",
        )
    return None


async def generate_practice(provider, subject, transfer, text, question_type, points):
    local = local_practice(subject, text)
    if local is not None and transfer == "near":
        return {
            "variant": local.model_dump(mode="json"),
            "verified": True,
            "generation": {"source": "sympy_checked_practice"},
            "logical_model": "Qwen",
        }
    result, verified, meta = await generate_variant(
        provider, subject, transfer, text, question_type, knowledge_points=points
    )
    admitted = False
    if verified and meta.source not in {"knowledge_confirmation_fallback"}:
        # These deterministic fallbacks carry checked answers; other generated
        # items require an independent structured review before they are served.
        if meta.source == "knowledge_linear_equation_fallback":
            admitted = True
        else:
            try:
                review = await provider.generate_structured(
                    "核对以下练习，不要默认生成的答案正确。独立求解后判断：与原题是否考查同一技能，"
                    "答案及所有选项是否正确且无歧义，是否无需缺失图片即可作答，难度是否符合原题年级。"
                    "任何无法确认的字段填false。原题及年级："
                    + text
                    + "\n练习："
                    + json.dumps(result.model_dump(mode="json"), ensure_ascii=False),
                    PracticeReview,
                )
                admitted = all(
                    (
                        review.same_skill,
                        review.answer_correct,
                        review.self_contained,
                        review.grade_appropriate,
                    )
                )
            except (ApiPoolUnavailable, ValueError):
                pass
    return {
        "variant": result.model_dump(mode="json"),
        "verified": admitted,
        "generation": meta.model_dump(),
        "logical_model": "Qwen",
    }
