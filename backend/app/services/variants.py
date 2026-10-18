from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from app.providers.api_pool import ApiPoolProvider, ApiPoolUnavailable
from app.schemas import RecognitionOption, VariantOutput
from app.services.math_tools import solve_text_equation, verify_equivalence
from app.services.practice_retrieval import VariantReference, concept_terms


@dataclass(slots=True)
class VariantGenerationMeta:
    source: str
    fallback_reason: str = ""
    retrieval_ids: list[str] | None = None

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _cube_fallback(transfer_type: str) -> VariantOutput:
    if transfer_type == "near":
        return VariantOutput(
            question_text=(
                "一个正方体展开图的六个面按下面的阶梯形排列：\n"
                "[2][3]\n   [x][y]\n      [z][5]\n"
                "折叠后相对面上的两个数之和都是7，求x+y。"
            ),
            answer="7",
            reference_solution=["由展开图可知x与5相对、2与y相对", "x=2，y=5", "x+y=7"],
            explanation="仍然练习正方体展开图中的相对面判断，只改变数字条件。",
        )
    return VariantOutput(
        question_text=(
            "礼品盒的六个面按下面的正方体展开图排列：\n"
            "[语][数]\n   [英][物]\n      [化][生]\n"
            "折叠成礼品盒后，写有“物”的面与哪个面相对？"
        ),
        answer="语",
        reference_solution=["把阶梯形展开图想象折叠", "第一行左端与第二行右端相对", "物的相对面是语"],
        explanation="把数字关系换成礼品盒标签，继续验证正方体相对面的判断。",
    )


def _reference_fallback(reference: VariantReference, topic: str) -> VariantOutput:
    steps = [line.strip() for line in reference.solution.splitlines() if line.strip()][:6]
    option_rows = re.findall(
        r"(?m)(?:^|\n)\s*([A-H])[\.、．]\s*([^\n]+)",
        reference.question_text,
    )
    return VariantOutput(
        question_text=reference.question_text,
        answer=reference.answer,
        reference_solution=steps or [f"根据{topic}提取条件", "完成判断并写出结论"],
        explanation=f"这道真实题继续检查“{topic}”。",
        options=[RecognitionOption(label=label, text=text.strip()) for label, text in option_rows],
    )


def build_knowledge_fallback(
    subject: str,
    transfer_type: str,
    context: str,
    question_type: str,
    knowledge_points: list[Any] | None,
    references: list[VariantReference] | None,
) -> tuple[VariantOutput, str]:
    combined = " ".join([context, *(str(item) for item in (knowledge_points or []))])
    if subject == "数学" and "一元一次方程" in combined:
        if transfer_type == "near":
            stem = "解方程：3x+4=19"
            steps = ["等式两边同时减去4，得3x=15", "等式两边同时除以3，得x=5", "代入原式，3×5+4=19"]
        else:
            stem = "买4本价格相同的练习本和一支5元的笔，共花25元。设每本练习本价格为x元，列出一元一次方程并求每本的价格。"
            steps = ["根据总价列方程4x+5=25", "等式两边同时减去5，得4x=20", "两边同时除以4，得x=5，即每本5元"]
        choice = question_type in {"choice", "multiple_choice", "单选题", "多选题", "选择题"}
        return VariantOutput(
            question_text=stem,
            answer="A" if choice else "x=5",
            reference_solution=steps,
            explanation="用等式两边同时加减同一个数、除以同一个非零数的性质求解，移项时注意符号。",
            options=[
                RecognitionOption(label=label, text=text)
                for label, text in (
                    ("A", "x=5"),
                    ("B", "x=3"),
                    ("C", "x=7"),
                    ("D", "x=8"),
                )
            ]
            if choice
            else [],
        ), "knowledge_linear_equation_fallback"
    if "正方体" in combined and any(item in combined for item in ("展开图", "相对面", "折叠")):
        return _cube_fallback(transfer_type), "knowledge_cube_fallback"
    if "补集" in combined:
        if transfer_type == "near":
            question = "已知全集 $U=\\{1,2,3,4,5,6\\}$，集合 $A=\\{1,3,5\\}$，则 $A$ 在 $U$ 中的补集是（ ）"
            explanation = "先锁定全集，再去掉属于 A 的元素；剩下的元素组成 A 的补集。"
        else:
            question = (
                "某学习小组成员编号的全集为 $U=\\{1,2,3,4,5,6\\}$，已完成作业的成员集合为 "
                "$A=\\{1,3,5\\}$。未完成作业的成员集合，也就是 $A$ 在 $U$ 中的补集是（ ）"
            )
            explanation = "把全体成员看作全集 U，未完成成员就是从 U 中去掉已完成集合 A 后剩下的人。"
        return VariantOutput(
            question_text=question,
            answer="A",
            reference_solution=[
                "全集是 $U=\\{1,2,3,4,5,6\\}$",
                "从 U 中去掉 A 的元素 1、3、5",
                "补集为 $\\{2,4,6\\}$",
            ],
            explanation=explanation,
            options=[
                RecognitionOption(label="A", text="$\\{2,4,6\\}$"),
                RecognitionOption(label="B", text="$\\{1,3,5\\}$"),
                RecognitionOption(label="C", text="$\\{1,2,3\\}$"),
                RecognitionOption(label="D", text="$\\{4,5,6\\}$"),
            ],
        ), "knowledge_complement_fallback"
    topic_terms = concept_terms(knowledge_points, context)
    topic = topic_terms[0] if topic_terms else (str((knowledge_points or [question_type])[0]))
    for reference in references or []:
        if "<ImageHere>" in reference.question_text or not reference.answer:
            continue
        result = _reference_fallback(reference, topic)
        if verify_variant(result, subject) and verify_knowledge_alignment(result, knowledge_points, context):
            return result, "retrieved_question_fallback"
    result = VariantOutput(
        question_text=f"判断并说明理由：解决与“{topic}”有关的问题时，必须先根据题目条件完成对应判断，不能只记最后答案。",
        answer="A"
        if question_type in {"choice", "multiple_choice", "单选题", "多选题", "选择题"}
        else "正确",
        reference_solution=[f"识别当前知识点：{topic}", "检查题目条件", "依据条件完成判断"],
        explanation=f"这是关于“{topic}”的基础确认题，完成后系统会继续安排同知识点练习。",
        options=(
            [
                RecognitionOption(label="A", text=f"先检查与{topic}有关的题目条件"),
                RecognitionOption(label="B", text="跳过条件，直接套用上次答案"),
                RecognitionOption(label="C", text="只看数字大小，不判断题意"),
                RecognitionOption(label="D", text="凭印象选择，不进行验证"),
            ]
            if question_type in {"choice", "multiple_choice", "单选题", "多选题", "选择题"}
            else []
        ),
    )
    return result, "knowledge_confirmation_fallback"


def verify_knowledge_alignment(
    result: VariantOutput,
    knowledge_points: list[Any] | None,
    original_context: str,
) -> bool:
    source = " ".join([original_context, *(str(item) for item in (knowledge_points or []))])
    candidate = " ".join([result.question_text, result.explanation, *result.reference_solution])
    if "一元一次方程" in source:
        # A prefixed explanation such as “继续检查一元一次方程” cannot make
        # an unrelated geometry/function stem a transfer exercise.
        stem = result.question_text
        if any(marker in stem for marker in ("菱形", "抛物线", "反比例", "二次函数", "x^2", "x²", "x^{2}")):
            return False
        solved, ok = solve_text_equation(stem)
        if ok:
            return bool(solved) and "=" in stem and not re.search(r"\^|²|³|\\frac|/\s*[a-z]", stem)
        return "一元一次方程" in stem and bool(re.search(r"\d+", stem)) and "求" in stem
    if "正方体" in source and any(item in source for item in ("展开图", "相对面", "折叠")):
        markers = ("正方体", "展开图", "相对面", "折叠")
        marker_match = sum(marker in candidate for marker in markers) >= 2
        question = result.question_text
        indented_grid = len(re.findall(r"(?m)^\s+\[[^\n]+\]", question)) >= 1 and question.count("[") >= 6
        markdown_grid = question.count("|") >= 8 and question.count("\n") >= 2
        explicit_positions = (
            sum(word in question for word in ("上方", "下方", "左侧", "右侧", "紧邻", "中间一行")) >= 2
        )
        self_contained = "<ImageHere>" not in question and (
            indented_grid or markdown_grid or explicit_positions
        )
        return marker_match and self_contained
    if "补集" in source:
        # “集合”本身过于宽泛。补集练习必须真正涉及补集（或常用补集符号），
        # 不能把任意一道集合计数题当成同知识点迁移题。
        compact_candidate = re.sub(r"\s+", "", candidate)
        return "补集" in candidate or any(
            symbol in compact_candidate for symbol in ("∁", "complement", "C_{\\mathbb", "C_\\mathbb", "C_R")
        )
    terms = [item for item in concept_terms(knowledge_points, original_context) if len(item) >= 3]
    if not terms:
        return True
    return any(term.lower() in result.question_text.lower() for term in terms)


async def generate_variant(
    provider: ApiPoolProvider,
    subject: str,
    transfer_type: str,
    context: str,
    question_type: str = "综合题",
    *,
    knowledge_points: list[Any] | None = None,
    references: list[VariantReference] | None = None,
) -> tuple[VariantOutput, bool, VariantGenerationMeta]:
    references = references or []
    fallback, fallback_source = build_knowledge_fallback(
        subject,
        transfer_type,
        context,
        question_type,
        knowledge_points,
        references,
    )
    reference_text = "\n\n".join(
        f"真实题库参考{index + 1}：\n{item.question_text}\n答案：{item.answer}\n知识点：{'、'.join(str(point) for point in item.knowledge_points)}"
        for index, item in enumerate(references[:3])
    )
    prompt = (
        f"根据原题生成{transfer_type}迁移题。学科：{subject}；题型：{question_type}；"
        f"核心知识点：{'、'.join(str(item) for item in (knowledge_points or []))}；"
        f"原题、知识点与错因：{context}。\n{reference_text}\n"
        "近迁移必须保持核心知识点、题型和难度，只改变数字或表面条件；"
        "远迁移必须保持核心知识点，允许改变材料或应用场景。"
        "禁止生成只属于同一学科但知识点不同的题。若原题是几何、正方体或图形题，禁止改成解方程。"
        "题目必须自包含；不要输出<ImageHere>。需要正方体展开图时，必须用至少三行方框文本表示六个面的真实相对位置，"
        "每行用前导空格保留错位关系；不得只写‘第一行、第二行’而不说明方框对齐位置。"
        "给出标准答案和逐步参考解法。explanation直接面向中学生，不使用产品术语。"
        "如果原题是单选题或多选题，必须返回可点击的options，每项包含label和text，answer只写选项字母；"
        "每个选项文字不超过35个中文字。"
    )
    reason = ""
    try:
        result = await provider.generate_structured(prompt, VariantOutput)
        needs_options = question_type in {"choice", "multiple_choice", "单选题", "多选题", "选择题"}
        format_verified = verify_variant(result, subject) and (not needs_options or bool(result.options))
        aligned = verify_knowledge_alignment(result, knowledge_points, context)
        if format_verified and aligned:
            return (
                result,
                True,
                VariantGenerationMeta(
                    source="qwen_with_retrieval",
                    retrieval_ids=[item.id for item in references],
                ),
            )
        reason = "knowledge_mismatch" if format_verified and not aligned else "format_or_answer_invalid"
    except ApiPoolUnavailable:
        reason = "ai_pool_unavailable"
    except ValueError:
        reason = "structured_output_invalid"
    verified = verify_variant(fallback, subject) and verify_knowledge_alignment(
        fallback, knowledge_points, context
    )
    return (
        fallback,
        verified,
        VariantGenerationMeta(
            source=fallback_source,
            fallback_reason=reason,
            retrieval_ids=[item.id for item in references],
        ),
    )


def verify_variant(result: VariantOutput, subject: str) -> bool:
    if not result.question_text or not result.answer or not result.reference_solution:
        return False
    # VariantOutput has no external diagram field. Do not serve a task that
    # requires an unavailable image; a textual cube net is self-contained.
    if "<ImageHere>" in result.question_text or (
        any(marker in result.question_text for marker in ("如图", "图中", "下图", "图所示"))
        and not (result.question_text.count("[") >= 6 and result.question_text.count("\n") >= 2)
    ):
        return False
    if subject != "数学":
        return True
    solved, ok = solve_text_equation(result.question_text)
    if ok and result.answer.startswith("x="):
        return verify_equivalence(solved.split("=", 1)[1], result.answer.split("=", 1)[1])
    if "=" in result.question_text and "解方程" in result.question_text:
        return False
    return bool(result.answer)
