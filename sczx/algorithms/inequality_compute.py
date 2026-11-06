"""Bounded, source-based real solution sets for standalone polynomial inequalities."""

import re
from dataclasses import dataclass
from types import SimpleNamespace

import sympy as sp

from learning_core.services.math_tools import normalize_expression, parse_math_expression


def clean(value):
    if not isinstance(value, str) or len(value) > 300 or "\n" in value or "\r" in value:
        raise ValueError("one bounded mathematical statement required")
    value = normalize_expression(value).strip(" 。")
    commands = {
        "leq": "<=",
        "geq": ">=",
        "le": "<=",
        "ge": ">=",
        "lt": "<",
        "gt": ">",
        "cup": "∪",
        "cap": "∩",
        "infty": "∞",
        "in": "∈",
        "varnothing": "∅",
        "emptyset": "∅",
        "left": "",
        "right": "",
        "mid": "|",
        "vert": "|",
    }
    value = value.replace(r"\mathbb{R}", "ℝ").replace("≤", "<=").replace("≥", ">=")
    value = re.sub(
        r"\\([A-Za-z]+)", lambda match: commands.get(match[1], match[0]), value
    )
    value = value.replace(r"\{", "{").replace(r"\}", "}")
    if "\\" in value:
        raise ValueError("unsupported mathematical command")
    value = re.sub(r"\bor\b", "∪", value, flags=re.IGNORECASE)
    value = re.sub(r"\band\b", "∩", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", "", value)


def polynomial(value, variable):
    def degree(node):
        if node == variable:
            return 1
        if node.is_Rational:
            return 0
        if node.is_Add:
            size = max(degree(item) for item in node.args)
        elif node.is_Mul:
            size = sum(degree(item) for item in node.args)
        elif node.is_Pow and node.exp.is_Integer and 0 <= node.exp <= 20:
            size = degree(node.base) * int(node.exp)
        else:
            raise ValueError("rational polynomial required")
        if size > 4:
            raise ValueError("unsupported degree")
        return size

    # Reject high-degree products before Poly can expand externally supplied expressions.
    degree(value)
    result = sp.Poly(value, variable, domain=sp.QQ)
    if result.degree() > 4:
        raise ValueError("unsupported degree")
    if any(
        max(abs(c.p).bit_length(), c.q.bit_length()) > 64 for c in result.all_coeffs()
    ):
        raise ValueError("coefficient budget exceeded")
    return result


class SolvedFormRequired(ValueError):
    """An equivalent constraint is intermediate work, not an isolated solution range."""


def relation_set(value, variable, *, solved=False):
    parts = re.split(r"(<=|>=|<|>)", value)
    if len(parts) not in (3, 5):
        raise ValueError("one or two comparisons required")
    operands = [parse_math_expression(part) for part in parts[::2]]
    if any(item.free_symbols - {variable} for item in operands):
        raise ValueError("different variable")
    result = sp.S.Reals
    relations = {"<": sp.Lt, "<=": sp.Le, ">": sp.Gt, ">=": sp.Ge}
    for index, op in enumerate(parts[1::2]):
        left, right = operands[index : index + 2]
        isolated = (left == variable and not right.free_symbols) or (
            right == variable and not left.free_symbols
        )
        if solved and not isolated:
            raise SolvedFormRequired("isolate the variable in the final answer")
        if isolated:
            bound = right if left == variable else left
            if bound.is_real is not True or bound.is_algebraic is not True:
                raise ValueError("real algebraic bound required")
            operator = (
                op
                if left == variable
                else {"<": ">", "<=": ">=", ">": "<", ">=": "<="}[op]
            )
            current = (
                sp.Interval(-sp.oo, bound, left_open=True, right_open=operator == "<")
                if operator in ("<", "<=")
                else sp.Interval(
                    bound, sp.oo, left_open=operator == ">", right_open=True
                )
            )
            result &= current
            continue
        expression = operands[index] - operands[index + 1]
        polynomial(expression, variable)
        relation = relations[op](expression, 0)
        current = (
            sp.S.Reals
            if relation is sp.S.true
            else sp.S.EmptySet
            if relation is sp.S.false
            else sp.solve_univariate_inequality(relation, variable, relational=False)
        )
        result &= current
    if result.has(sp.ConditionSet):
        raise ValueError("unresolved set")
    return result


def endpoint(value):
    if value in ("∞", "+∞", "oo", "+oo"):
        return sp.oo
    if value in ("-∞", "-oo"):
        return -sp.oo
    result = parse_math_expression(value)
    if (
        result.free_symbols
        or result.is_real is not True
        or result.is_algebraic is not True
    ):
        raise ValueError("real algebraic endpoint required")
    return result


def solution_set(value, variable, *, solved=False):
    raw = clean(value)
    raw = re.sub(r"^(?:解集(?:为|是|[:：])|答案(?:为|是|[:：]))", "", raw)
    builder = re.fullmatch(r"\{([^\W\d_])[|｜:：](.+)\}", raw)
    if builder:
        if builder[1] != str(variable):
            raise ValueError("different set variable")
        raw = builder[2]
    member = re.fullmatch(r"([^\W\d_])∈(.+)", raw)
    if member:
        if member[1] != str(variable):
            raise ValueError("different member variable")
        raw = member[2]
    if raw in ("ℝ", "R", "实数集"):
        return sp.S.Reals
    if raw in ("∅", "空集", "无解", "{}"):
        return sp.S.EmptySet
    unions = re.split(r"或|∪|\bor\b", raw, flags=re.IGNORECASE)
    if len(unions) > 4:
        raise ValueError("too many branches")
    result = sp.S.EmptySet
    for union in unions:
        intersections = re.split(r"且|∩|\band\b", union, flags=re.IGNORECASE)
        if len(intersections) > 3:
            raise ValueError("too many conditions")
        branch = sp.S.Reals
        for part in intersections:
            interval = re.fullmatch(r"([\[(])([^,，]+)[,，]([^,，]+)([\])])", part)
            finite = re.fullmatch(r"\{([^{}]+)\}", part)
            assignment = re.fullmatch(r"([^\W\d_])=([^=<>]+)", part)
            if interval:
                lo, hi = endpoint(interval[2]), endpoint(interval[3])
                if lo is sp.oo or hi is -sp.oo or lo > hi:
                    raise ValueError("reversed interval")
                if (lo is -sp.oo and interval[1] != "(") or (
                    hi is sp.oo and interval[4] != ")"
                ):
                    raise ValueError("infinity is not a closed endpoint")
                current = sp.Interval(
                    lo, hi, left_open=interval[1] == "(", right_open=interval[4] == ")"
                )
            elif finite:
                values = re.split(r"[,，、]", finite[1])
                if len(values) > 4:
                    raise ValueError("too many points")
                current = sp.FiniteSet(*(endpoint(item) for item in values))
                if current.has(sp.oo, -sp.oo):
                    raise ValueError("infinity is not a point")
            elif assignment:
                if assignment[1] != str(variable):
                    raise ValueError("different assignment variable")
                point = endpoint(assignment[2])
                if point in (sp.oo, -sp.oo):
                    raise ValueError("finite assignment required")
                current = sp.FiniteSet(point)
            else:
                current = relation_set(part, variable, solved=solved)
            branch &= current
        result |= branch
    return result


@dataclass(frozen=True)
class InequalitySource:
    text: str
    variable: sp.Symbol
    solutions: sp.Set
    boundary: sp.Set


def source_inequality(text):
    try:
        candidate, count = re.subn(
            r"^(?:解(?:下列)?(?:一元(?:一次|二次))?不等式|求解不等式)[：:\s]*",
            "",
            text.strip(),
        )
        if not count:
            return None
        parts = re.split(r"[，,。；;]", candidate.strip("。 "), maxsplit=1)
        if len(parts) == 2 and parts[1].strip("。 ") not in {
            "写出解集",
            "求解集",
            "写出实数解集",
        }:
            return None
        raw = clean(parts[0])
        operands = re.split(r"<=|>=|<|>", raw)
        if len(operands) != 2:
            return None
        left, right = (parse_math_expression(part) for part in operands)
        variables = left.free_symbols | right.free_symbols
        if len(variables) != 1:
            return None
        variable = next(iter(variables))
        expression = left - right
        polynomial(expression, variable)
        roots = sp.solveset(expression, variable, domain=sp.S.Reals)
        if not isinstance(roots, sp.FiniteSet) and roots is not sp.S.EmptySet:
            return None
        source = InequalitySource(
            parts[0], variable, relation_set(raw, variable), roots
        )
        if (
            solution_set(format_solution(source), variable, solved=True)
            != source.solutions
        ):
            return None
        return source
    except Exception:  # noqa: BLE001 - unsupported mathematics remains unverified
        return None


def format_solution(source):
    def show(value):
        if isinstance(value, sp.Interval):
            a = "-∞" if value.start is -sp.oo else str(value.start)
            b = "∞" if value.end is sp.oo else str(value.end)
            return (
                ("(" if value.left_open else "[")
                + a
                + ", "
                + b
                + (")" if value.right_open else "]")
            )
        if value is sp.S.Reals:
            return "ℝ"
        if value is sp.S.EmptySet:
            return "∅"
        if isinstance(value, sp.FiniteSet):
            return (
                "{"
                + ", ".join(
                    str(item) for item in sorted(value, key=sp.default_sort_key)
                )
                + "}"
            )
        if isinstance(value, sp.Union):
            return " ∪ ".join(show(item) for item in value.args)
        raise ValueError("unsupported set display")

    return f"{source.variable} ∈ {show(source.solutions)}"


def inequality_alignment(text, references, students, student_answer):
    source = source_inequality(text)
    if source is None or not students:
        return None
    try:
        submitted = solution_set(student_answer, source.variable, solved=True)
    except Exception:  # noqa: BLE001
        submitted = None
    rows, first_error, known_prefix = [], None, True
    for index, student in enumerate(students):
        equivalent, valid, relation, scope = (
            False,
            False,
            "unknown",
            "unverified_intermediate",
        )
        try:
            candidate = solution_set(student.text, source.variable)
            equivalent = candidate == source.solutions
            necessary = source.solutions.is_subset(candidate) is True
            final = index == len(students) - 1 and submitted == candidate
            valid = equivalent or (necessary and not final)
            relation = (
                "equivalent"
                if equivalent
                else "necessary_condition"
                if valid
                else "condition_omission"
                if necessary
                else "invalid_transformation"
            )
            scope = (
                "original_inequality_real_solution_set"
                if equivalent
                else "necessary_condition"
                if valid
                else "different_solution_set"
            )
            if (
                not equivalent
                and not final
                and isinstance(candidate, sp.FiniteSet)
                and candidate
                and candidate.is_subset(source.boundary) is True
            ):
                valid, relation, scope = True, "branch_solution", "boundary_zeros"
        except Exception:  # noqa: BLE001 - prose is not a required reference action
            # Finding the boundary zeros is legitimate intermediate work, not a solution set.
            try:
                raw = clean(student.text)
                if raw.count("=") != 1 or re.search(r"[<>]", raw):
                    raise ValueError("not a boundary equation")
                a, b = (parse_math_expression(part) for part in raw.split("="))
                polynomial(a - b, source.variable)
                zeros = sp.solveset(a - b, source.variable, domain=sp.S.Reals)
                valid = bool(zeros) and zeros.is_subset(source.boundary) is True
                relation, scope = (
                    ("branch_solution", "boundary_zeros")
                    if valid
                    else ("unknown", "unverified_intermediate")
                )
            except Exception:  # noqa: BLE001
                relation, scope = "unknown", "unverified_intermediate"
        if relation == "unknown":
            known_prefix = False
        elif not valid and first_error is None and known_prefix:
            first_error = index
        rows.append(
            {
                "index": index,
                "reference_step_id": None,
                "student_step_id": student.id,
                "reference_text": source.text,
                "student_text": student.text,
                "alignment": relation,
                "equivalent": equivalent,
                "uses_condition": True,
                "math_valid": valid,
                "is_first_error": first_error == index,
                "propagated": first_error is not None
                and index > first_error
                and not valid,
                "verification_scope": scope,
            }
        )
    return rows, all(
        row["math_valid"] for row in rows
    ) and submitted == source.solutions


def verify_inequality_repair(text, references, students, alignment, counter):
    first = next((row for row in alignment if row["is_first_error"]), None)
    if first is None:
        return counter
    index, repaired = first["index"], counter.get("repaired_steps", [])
    preserved = False
    try:
        preserved = len(repaired) == len(students) and all(
            clean(repaired[i]) == clean(students[i].text) for i in range(index)
        )
        consistent = preserved and clean(counter.get("corrected_step", "")) == clean(
            repaired[index]
        )
    except (ValueError, TypeError):
        consistent = False
    checked = (
        inequality_alignment(
            text,
            references,
            [
                SimpleNamespace(id=step.id, text=value)
                for step, value in zip(students, repaired)
            ],
            repaired[-1],
        )
        if consistent
        else None
    )
    confirmed = checked is not None and checked[1]
    affected = sum(not row["math_valid"] for row in alignment[index:])
    return {
        **counter,
        "root_cause_confirmed": confirmed,
        "preserved_prefix": preserved,
        "verification_method": (
            "qwen_proposal_sympy_check"
            if counter.get("verification_method", "").startswith("qwen")
            else "reference_repair_sympy_check"
        ),
        "status": "confirmed" if confirmed else "inconclusive",
        "recovered_steps": affected if confirmed else 0,
        "affected_steps": affected,
        "independent_errors": []
        if confirmed
        else counter.get("independent_errors", []),
        "validation_scope": "polynomial_inequality_solution_set_and_preserved_prefix",
        "conclusion": f"保留前面正确的步骤，修正第 {index + 1} 步后，修复路径与原不等式的实数解集一致。"
        if confirmed
        else "当前修复尚未通过原不等式解集和原正确步骤的核验，请继续核对。",
    }


def grade_inequality(question, answer, expected):
    source = source_inequality(question)
    if source is None:
        return None
    try:
        expected_matches = (
            solution_set(expected, source.variable, solved=True) == source.solutions
        )
    except Exception:  # noqa: BLE001
        expected_matches = False
    base = {
        "recognized_answer": answer,
        "expected_answer": expected,
        "method": "sympy_inequality_source_set",
        "matched_points": [],
        "grader": "rule",
        "confidence": 0.99,
    }
    if not expected_matches:
        return {
            **base,
            "correct": False,
            "score": 0,
            "verdict": "review_required",
            "decisive": False,
            "can_update_learning": False,
            "conflict": True,
            "evidence": ["参考答案未通过原题实数解集核验"],
            "feedback": "参考答案与原题解集核验不一致，请重新分析后再提交。",
        }
    try:
        correct = solution_set(answer, source.variable, solved=True) == source.solutions
    except SolvedFormRequired:
        return {
            **base,
            "correct": False,
            "score": 0,
            "verdict": "review_required",
            "decisive": False,
            "can_update_learning": False,
            "conflict": False,
            "evidence": ["当前是原不等式或中间变形，尚未写出最终取值范围"],
            "feedback": "这一步变形已保留，请继续写出未知数的取值范围或区间。",
        }
    except Exception:  # noqa: BLE001 - multi-step prose still needs the existing process review
        return None
    return {
        **base,
        "correct": correct,
        "score": 100 if correct else 0,
        "verdict": "confirmed_correct" if correct else "confirmed_incorrect",
        "decisive": True,
        "can_update_learning": True,
        "conflict": False,
        "evidence": [
            "独立核对原题一元多项式的实数解集及端点开闭，不以模型参考步骤的行号判题"
        ],
        "feedback": "解集与原不等式一致，端点也已核对。"
        if correct
        else "解集与原不等式不一致，请检查取值范围和端点是否包含。",
    }
