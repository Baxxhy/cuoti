from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.providers.api_pool import ApiPoolProvider, ApiPoolUnavailable
from app.schemas import AnswerGradeOutput
from app.services.math_tools import compare_equivalence, normalize_expression, parse_math_expression

CONFIRMED_CORRECT = "confirmed_correct"
CONFIRMED_INCORRECT = "confirmed_incorrect"
PROBABLY_CORRECT = "probably_correct"
REVIEW_REQUIRED = "review_required"


def _safe_result(
    result: dict[str, Any],
    verdict: str,
    *,
    confidence: float,
    evidence: list[str],
    conflict: bool = False,
) -> dict[str, Any]:
    decisive = verdict in {CONFIRMED_CORRECT, CONFIRMED_INCORRECT}
    return {
        **result,
        "verdict": verdict,
        "decisive": decisive,
        "can_update_learning": decisive,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "evidence": evidence,
        "conflict": conflict,
    }


def _rule_is_conclusive(result: dict[str, Any]) -> bool:
    return result.get("method") in {
        "option_exact",
        "normalized_exact",
        "sympy_equivalent",
        "sympy_mismatch",
        "final_conclusion",
        "numeric_unit",
    }


def _normalize(value: str) -> str:
    return re.sub(r"[\s，。；、,!！？:：'\"（）()]", "", value).lower()


def _numeric_unit(value: str) -> tuple[str, str]:
    compact = re.sub(r"\s+", "", value).strip("。；;")
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Z²³/·%℃°]+)?", compact)
    return (match.group(1), match.group(2) or "") if match else ("", "")


def _choice_values(value: Any) -> set[str]:
    if isinstance(value, list):
        return {_normalize(str(item)).upper() for item in value if _normalize(str(item))}
    compact = _normalize(str(value)).upper()
    if re.fullmatch(r"[A-H]+", compact):
        return set(compact)
    labelled = re.findall(r"(?:答案|选项|选择)([A-H]+)", compact)
    return set(labelled[-1]) if labelled else ({compact} if compact else set())


def _final_answer_candidate(answer: str, expected: str) -> str:
    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    if not lines:
        return ""
    conclusion = re.fullmatch(
        r"(?:综上[，,、\s]*)?(?:集合对的)?(?:个数|数量|答案|结果)(?:为|是|等于|[:：])\s*(.+?)\s*(?:个)?[。；; ]*",
        lines[-1],
    )
    if conclusion:
        return conclusion.group(1).strip()
    number_with_unit = re.fullmatch(r"([-+]?\d+(?:\.\d+)?)\s*个[。；; ]*", lines[-1])
    if number_with_unit:
        return number_with_unit.group(1)
    if len(lines[-1]) <= 80:
        return re.sub(r"^(?:(?:答案|结果|所以|则|为|即|是|答)[：:\s]*)+", "", lines[-1]).strip("。；; ")
    return ""


def _compare_math_answers(answer: str, expected: str) -> tuple[bool, bool]:
    """Keep assignment names and every component of a multi-value answer."""

    def assignments(value: str) -> dict[str, str] | None:
        parts = re.split(r"[,，;；]", value)
        result: dict[str, str] = {}
        for part in parts:
            match = re.fullmatch(r"\s*([A-Za-z])\s*=\s*([^=]+)\s*", part)
            if match is None or match.group(1) in result:
                return None
            result[match.group(1)] = match.group(2)
        return result

    if "=" not in expected and "=" not in answer:
        return compare_equivalence(answer, expected)
    expected_assignments, answer_assignments = assignments(expected), assignments(answer)
    if expected_assignments is None:
        if "=" not in expected and answer_assignments is not None and len(answer_assignments) == 1:
            return compare_equivalence(next(iter(answer_assignments.values())), expected)
        return False, False
    if answer_assignments is None:
        if "=" not in answer and len(expected_assignments) == 1:
            return compare_equivalence(answer, next(iter(expected_assignments.values())))
        return False, False
    if expected_assignments.keys() != answer_assignments.keys():
        return False, True
    comparisons = [
        compare_equivalence(answer_assignments[key], value) for key, value in expected_assignments.items()
    ]
    return all(equal for equal, _ in comparisons), all(parsed for _, parsed in comparisons)


def _math_expected_candidate(expected: str) -> str:
    """Read a single explicit answer or an entirely verified simplification chain.

    Some imported answers contain an answer section followed by prose analysis.
    Do not guess the last formula in general prose or discard multipart answers.
    """
    candidate = expected.strip()
    if len(candidate) > 4000:
        return expected
    if candidate.startswith("【答案】"):
        candidate = re.split(r"【(?:解析|分析)】", candidate[len("【答案】") :], maxsplit=1)[0].strip()
    candidate = re.sub(r"(?<![.])[。.]\s*$", "", candidate).strip()
    chain = re.fullmatch(r"(?:解\s*[:：]\s*)?原式\s*(.+)", candidate, flags=re.S)
    if chain is None:
        try:
            parse_math_expression(candidate)
            return candidate
        except Exception:
            return expected
    expression = re.sub(r"\$([^$\n]+)\$", r"\1", chain.group(1)).strip()
    if not expression.startswith("="):
        return expected
    parts = [part.strip() for part in expression[1:].split("=")]
    if len(parts) > 30:
        return expected
    try:
        for part in parts:
            parse_math_expression(part)
        if all(compare_equivalence(parts[0], part) == (True, True) for part in parts[1:]):
            return parts[-1]
    except Exception:
        pass
    return expected


def _grade_by_rule(answer: str, expected: str, subject: str, question_type: str) -> dict[str, Any]:
    answer, expected = answer.strip(), expected.strip()
    if not answer:
        return {
            "correct": False,
            "score": 0,
            "recognized_answer": "",
            "expected_answer": expected,
            "method": "empty",
            "feedback": "请先写下答案或关键步骤。",
            "matched_points": [],
            "grader": "rule",
        }
    recognized = answer
    normalized, target = _normalize(answer), _normalize(expected)
    correct = normalized == target
    matched: list[str] = []
    method = "normalized_exact" if correct else "normalized_mismatch"
    if subject == "数学":
        math_expected = _math_expected_candidate(expected)
        candidate = _final_answer_candidate(answer, expected)
        if candidate:
            recognized = candidate
        math_exact = re.sub(r"\s+", "", normalize_expression(recognized)) == re.sub(
            r"\s+",
            "",
            normalize_expression(math_expected),
        )
        try:
            correct, parsed = _compare_math_answers(recognized, math_expected)
            if parsed:
                method = "sympy_equivalent" if correct else "sympy_mismatch"
            elif math_exact:
                correct = True
                method = "normalized_exact"
            else:
                correct = False
                method = "math_unverified"
        except (ValueError, TypeError):
            method = "math_unverified"
    elif subject in {"物理", "化学"}:
        number, unit = _numeric_unit(answer)
        target_number, target_unit = _numeric_unit(expected)
        if number and target_number:
            correct = Decimal(number) == Decimal(target_number) and (not target_unit or unit == target_unit)
            method = "numeric_unit"
    elif not any(token in question_type for token in ("选择", "判断", "填空")) and target:
        chunks = [item for item in re.split(r"[，。；、,;\s]+", expected) if len(item) >= 2]
        matched = [item for item in chunks if _normalize(item) in normalized]
        correct = len(matched) / max(1, len(chunks)) >= 0.6 or (len(target) >= 4 and target in normalized)
        method = "key_point_coverage"
    score = 100 if correct else 0
    concise = recognized if len(recognized) <= 40 else "未识别到明确的最终结论"
    feedback = (
        f"系统识别到最终答案为“{concise}”，与标准答案一致。"
        if correct
        else f"系统识别到的最终答案是“{concise}”，标准答案是“{expected}”。请检查最后一行结论。"
    )
    return {
        "correct": correct,
        "score": score,
        "recognized_answer": recognized,
        "expected_answer": expected,
        "method": method,
        "feedback": feedback,
        "matched_points": matched,
        "grader": "rule",
    }


def _needs_process_review(answer: str, question_type: str) -> bool:
    markers = ("综合", "解答", "证明", "计算", "主观", "材料", "proof", "subjective", "calculation")
    normalized_type = question_type.casefold()
    return (
        len(answer.strip()) > 80 or "\n" in answer.strip() or any(item in normalized_type for item in markers)
    )


async def grade_answer(
    provider: ApiPoolProvider,
    *,
    question: str,
    answer: Any,
    expected: Any,
    reference_solution: list[Any] | None,
    subject: str,
    question_type: str,
    options: list[Any] | None = None,
) -> dict[str, Any]:
    """The single grading entry point for every student-answer workflow."""
    expected_text = str(expected)
    answer_text = str(answer)
    if options:
        student_values, expected_values = _choice_values(answer), _choice_values(expected)
        correct = bool(expected_values) and student_values == expected_values
        return _safe_result(
            {
                "correct": correct,
                "score": 100 if correct else 0,
                "recognized_answer": "、".join(sorted(student_values)),
                "expected_answer": "、".join(sorted(expected_values)),
                "method": "option_exact",
                "feedback": (
                    "选项与标准答案一致。"
                    if correct
                    else f"系统识别到你的选择为“{'、'.join(sorted(student_values)) or '空'}”，标准答案为“{'、'.join(sorted(expected_values))}”。"
                ),
                "matched_points": [],
                "grader": "rule",
            },
            CONFIRMED_CORRECT if correct else CONFIRMED_INCORRECT,
            confidence=0.99,
            evidence=["选项集合与标准答案进行精确比较"],
        )
    rule_result = _grade_by_rule(answer_text, expected_text, subject, question_type)
    if not _needs_process_review(answer_text, question_type):
        conclusive = _rule_is_conclusive(rule_result)
        verdict = (
            CONFIRMED_CORRECT
            if rule_result["correct"] and conclusive
            else CONFIRMED_INCORRECT
            if conclusive
            else REVIEW_REQUIRED
        )
        if verdict == REVIEW_REQUIRED:
            rule_result["feedback"] = "当前答案无法通过规则可靠验证，需要再核对后才能更新学习记录。"
        return _safe_result(
            rule_result,
            verdict,
            confidence=0.98 if conclusive else 0.45,
            evidence=[f"规则校验：{rule_result['method']}"],
        )
    prompt = (
        f"学科：{subject}\n题型：{question_type}\n题目：{question}\n"
        f"标准答案：{expected_text}\n参考步骤：{reference_solution or []}\n学生作答：{answer_text}\n"
        "请判断学生作答是否正确。允许与参考步骤不同但数学上等价的正确方法；"
        "不要因为表述、排版、OCR空格或乘号写法不同而扣分。"
        "同时检查过程是否存在会影响结论的矛盾或计算错误。"
        "reason只写一到两句、直接面向学生；若判错，必须明确指出第一个关键错误或答案差异。"
    )
    try:
        result = await provider.generate_structured(
            prompt,
            AnswerGradeOutput,
            system="你是严谨的中学作业判题老师。只依据题目、标准答案和学生作答判断，并返回合法JSON。",
        )
    except (ApiPoolUnavailable, ValueError):
        fallback = {**rule_result, "grader": "rule_fallback"}
        has_working = "\n" in answer_text.strip() or len(answer_text.strip()) > 80
        if _rule_is_conclusive(rule_result) and not has_working:
            return _safe_result(
                fallback,
                CONFIRMED_CORRECT if rule_result["correct"] else CONFIRMED_INCORRECT,
                confidence=0.9,
                evidence=[f"模型不可用；规则校验：{rule_result['method']}"],
            )
        fallback["feedback"] = (
            str(rule_result["feedback"]) + " 过程复核暂时不可用，这次不更新掌握度，请稍后重试。"
            if _rule_is_conclusive(rule_result)
            else "判题模型暂时不可用，规则也无法确认这份过程，请稍后重试或人工核对。"
        )
        return _safe_result(
            fallback,
            REVIEW_REQUIRED,
            confidence=0.2,
            evidence=["模型不可用", f"规则校验不充分：{rule_result['method']}"],
        )
    llm_result = {
        "correct": result.correct,
        "score": result.score,
        "recognized_answer": result.recognized_final_answer,
        "expected_answer": expected_text,
        "method": "llm_process_review",
        "matched_points": result.matched_key_steps,
        "error_points": result.error_points,
        "confidence": result.confidence,
        "feedback": result.reason,
        "grader": "llm",
    }
    rule_conclusive = _rule_is_conclusive(rule_result)
    conflict = rule_conclusive and bool(rule_result["correct"]) != bool(result.correct)
    evidence = [
        f"规则校验：{rule_result['method']}（{'通过' if rule_result['correct'] else '未通过'}）",
        f"模型过程复核：{'正确' if result.correct else '有误'}，置信度 {result.confidence:.2f}",
    ]
    if conflict:
        llm_result["feedback"] = (
            "规则校验和过程判定出现冲突，这次不记录为答对或答错，请核对识别文字和解题过程。"
        )
        return _safe_result(
            llm_result,
            REVIEW_REQUIRED,
            confidence=min(result.confidence, 0.5),
            evidence=evidence,
            conflict=True,
        )
    if rule_conclusive and result.confidence >= 0.75:
        return _safe_result(
            llm_result,
            CONFIRMED_CORRECT if result.correct else CONFIRMED_INCORRECT,
            confidence=min(0.99, (result.confidence + 0.95) / 2),
            evidence=evidence,
        )
    if result.correct and result.confidence >= 0.8:
        llm_result["feedback"] = result.reason + " 当前只能判为可能正确，确认前不会更新掌握度。"
        return _safe_result(
            llm_result,
            PROBABLY_CORRECT,
            confidence=result.confidence,
            evidence=evidence,
        )
    llm_result["feedback"] = result.reason + " 当前证据不足，确认前不会更新掌握度或错因。"
    return _safe_result(
        llm_result,
        REVIEW_REQUIRED,
        confidence=result.confidence,
        evidence=evidence,
    )
