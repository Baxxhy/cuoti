from __future__ import annotations

import re
from typing import Any

import sympy as sp

from app.services.math_tools import (
    compare_equivalence,
    normalize_expression,
    parse_math_expression,
    verify_equivalence,
)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", normalize_expression(value)).lower()


def equation_equivalent(left: str, right: str, *, require_symbolic: bool = False) -> bool:
    if not require_symbolic and re.sub(r"\s+", "", normalize_expression(left)) == re.sub(
        r"\s+", "", normalize_expression(right)
    ):
        return True
    if "=" not in left or "=" not in right:
        equivalent, parsed = compare_equivalence(left, right)
        return equivalent and (parsed or not require_symbolic)
    try:

        def roots(value: str) -> tuple[sp.Symbol, sp.FiniteSet]:
            lhs_text, rhs_text = normalize_expression(value).split("=", 1)
            lhs, rhs = parse_math_expression(lhs_text), parse_math_expression(rhs_text)
            symbols = lhs.free_symbols | rhs.free_symbols
            if len(symbols) != 1:
                raise ValueError("不支持的方程")
            symbol = next(iter(symbols))
            polynomial = sp.Poly(sp.together(lhs - rhs).as_numer_denom()[0], symbol)
            if polynomial.degree() > 4:
                raise ValueError("不支持的方程")
            solutions = sp.solveset(sp.Eq(lhs, rhs), symbol, domain=sp.S.Reals)
            if not isinstance(solutions, sp.FiniteSet) or not solutions:
                raise ValueError("无法确认有限实数解")
            return symbol, solutions

        return roots(left) == roots(right)
    except Exception:
        return False


def classify_error(reference: str, student: str, subject: str = "数学") -> str:
    ref, stu = _compact(reference), _compact(student)
    if not student:
        return "missing_step"
    if subject == "历史":
        if any(x in ref for x in ("直接原因", "根本原因", "影响", "导致")):
            return "causality_confusion"
        return "fact_error" if any(char.isdigit() for char in ref + stu) else "evidence_missing"
    if subject == "物理":
        ref_units = set(re.findall(r"(?:m/s²|m/s|kg|n|pa|j|w|v|a|ω|hz)", ref, re.I))
        stu_units = set(re.findall(r"(?:m/s²|m/s|kg|n|pa|j|w|v|a|ω|hz)", stu, re.I))
        if ref_units != stu_units:
            return "unit_error"
        return "formula_error" if "=" in ref else "model_error"
    if subject == "化学":
        if any(token in reference for token in ("→", "=", "生成")):
            return "equation_error"
        return (
            "condition_error"
            if any(token in reference for token in ("加热", "点燃", "催化"))
            else "concept_error"
        )
    if subject == "语文":
        return "evidence_missing" if len(stu) < max(4, len(ref) // 2) else "context_error"
    if subject == "英语":
        return (
            "grammar_error"
            if any(token in reference.lower() for token in ("ed", "ing", "have", "has", "was", "were"))
            else "context_error"
        )
    if subject == "生物":
        return (
            "variable_error" if any(token in ref for token in ("变量", "对照", "条件")) else "process_error"
        )
    if subject == "地理":
        return (
            "map_reading_error"
            if any(token in ref for token in ("图", "方向", "位置", "等高线"))
            else "factor_error"
        )
    if subject in {"道德与法治", "思想政治"}:
        return (
            "material_mismatch"
            if any(token in ref for token in ("材料", "体现", "说明"))
            else "concept_confusion"
        )
    if ("+" in stu and "-" in ref) or ("-" in stu and "+" in ref):
        return "sign_error"
    if "(" in ref and "(" not in stu:
        return "formula_error"
    if "=" in reference and "=" in student:
        ref_rhs, stu_rhs = reference.rsplit("=", 1)[-1], student.rsplit("=", 1)[-1]
        if not verify_equivalence(ref_rhs, stu_rhs):
            return "calculation_error"
        return "invalid_transformation"
    if len(stu) < max(2, len(ref) // 2):
        return "condition_omission"
    return "concept_error"


def align_steps(
    reference_steps: list[Any], student_steps: list[Any], subject: str = "数学", question_text: str = ""
) -> list[dict[str, Any]]:
    if reference_steps and question_text and _compact(reference_steps[0].text) in _compact(question_text):
        reference_steps = reference_steps[1:]
    alignments: list[dict[str, Any]] = []
    first_error: int | None = None
    total = max(len(reference_steps), len(student_steps))
    for index in range(total):
        reference = reference_steps[index] if index < len(reference_steps) else None
        student = student_steps[index] if index < len(student_steps) else None
        ref_text = reference.text if reference else ""
        stu_text = student.text if student else ""
        exact = bool(reference and student and _compact(ref_text) == _compact(stu_text))
        equivalent = bool(reference and student and equation_equivalent(ref_text, stu_text))
        if reference is None:
            relation = "extra_step"
        elif student is None:
            relation = "missing_step"
        elif exact:
            relation = "exact"
        elif equivalent:
            relation = "equivalent"
        else:
            relation = classify_error(ref_text, stu_text, subject)
        correct = relation in {"exact", "equivalent"}
        if not correct and first_error is None:
            first_error = index
        alignments.append(
            {
                "index": index,
                "reference_step_id": reference.id if reference else None,
                "student_step_id": student.id if student else None,
                "reference_text": ref_text,
                "student_text": stu_text,
                "alignment": relation,
                "equivalent": equivalent,
                "uses_condition": bool(reference),
                "math_valid": bool(
                    subject == "数学"
                    and reference
                    and student
                    and equation_equivalent(
                        ref_text,
                        stu_text,
                        require_symbolic=True,
                    )
                ),
                "is_first_error": first_error == index,
                "propagated": first_error is not None and index > first_error and not correct,
            }
        )
    return alignments
