"""Source-based checks for bounded standalone polynomial solving.

Reference prose is not a required sequence of student actions. A shorter valid
derivation must not become a sign error merely because its row number differs.
"""

import re
from types import SimpleNamespace

import sympy as sp
from app.services.diagnosis import classify_error
from app.services.math_tools import normalize_expression, parse_math_expression


def equation(value):
    raw = normalize_expression(value).strip(" 。.!！?？")
    if len(raw) > 200 or raw.count("=") != 1:
        raise ValueError("unsupported equation")
    left, right = (parse_math_expression(part) for part in raw.split("="))
    variables = left.free_symbols | right.free_symbols
    if len(variables) != 1:
        raise ValueError("one variable required")
    variable = next(iter(variables))
    polynomial = sp.Poly(left - right, variable)
    if not 1 <= polynomial.degree() <= 4:
        raise ValueError("unsupported degree")
    roots = sp.solveset(sp.Eq(left, right), variable, domain=sp.S.Reals)
    if not isinstance(roots, sp.FiniteSet) or not roots:
        raise ValueError("finite nonempty real roots required")
    assignment = left == variable and not right.free_symbols
    return raw, variable, roots, assignment


def source_equation(text):
    clean, count = re.subn(
        r"^(?:解(?:下列)?(?:一元(?:一次|二次))?方程|求解(?:方程)?|solve(?:\s+the)?(?:\s+equation)?)[：:\s]*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )
    if not count:
        return None
    parts = re.split(r"[，,。；;]", clean.strip("。 "), maxsplit=1)
    if len(parts) == 2 and parts[1].strip("。 ") not in {
        "写出所有实数解",
        "求所有实数解",
    }:
        return None
    try:
        return equation(parts[0])
    except Exception:  # noqa: BLE001 - unsupported symbolic inputs stay unverified
        return None


def answer_roots(text, variable):
    roots = sp.FiniteSet()
    for part in re.split(r"或|\bor\b|[、,，;；]", text, flags=re.IGNORECASE):
        part = normalize_expression(part).strip(" 。")
        if "=" in part:
            _, symbol, values, assignment = equation(part)
            if symbol != variable or not assignment:
                raise ValueError("explicit root assignment required")
        else:
            value = parse_math_expression(part)
            if value.free_symbols or value.is_real is not True:
                raise ValueError("real constant required")
            values = sp.FiniteSet(value)
        roots |= values
    return roots


def polynomial_alignment(text, references, students, student_answer):
    source = source_equation(text)
    if source is None or not students:
        return None
    raw, variable, roots, _ = source
    try:
        parsed = []
        for step in students:
            try:
                parsed.append(equation(step.text))
            except Exception:  # noqa: BLE001 - allow explicit multiple-root answers
                if not re.search(r"或|\bor\b|[、,，;；]", step.text):
                    return None
                values = answer_roots(step.text, variable)
                parsed.append((step.text, variable, values, len(values) == 1))
        if any(row[1] != variable for row in parsed):
            return None
    except Exception:  # noqa: BLE001 - no guess from prose or unsupported formulas
        return None
    reference_equations = []
    for reference in references:
        # Extract only bounded arithmetic spans; no model-generated code is run.
        for span in re.findall(r"[A-Za-z0-9\s.+*/()=^{}$\\-]+", reference.text):
            try:
                value = equation(span)
                if value[1] == variable and value[2] == roots:
                    reference_equations.append((reference, value))
            except Exception:  # noqa: BLE001, S112 - prose is not a missing action
                continue
    try:
        submitted = answer_roots(student_answer or "", variable)
    except Exception:  # noqa: BLE001 - final answer may need model review
        submitted = None
    rows = []
    first_error = None
    for index, (student, value) in enumerate(zip(students, parsed)):
        expression, _, solutions, assignment = value
        complete = solutions == roots
        branch = assignment and solutions.is_subset(roots) is True
        reference, compared = next(
            (
                (step, item[0])
                for step, item in reference_equations
                if item[0].split("=", 1)[0] == expression.split("=", 1)[0]
            ),
            (None, raw),
        )
        relation = (
            "equivalent"
            if complete
            else "branch_solution"
            if branch
            else classify_error(compared, expression)
        )
        if (
            branch
            and index == len(students) - 1
            and submitted is not None
            and submitted.is_subset(roots) is True
            and submitted != roots
        ):
            relation = "condition_omission"
        valid = relation in {"equivalent", "branch_solution"}
        if not valid and first_error is None:
            first_error = index
        rows.append(
            {
                "index": index,
                "reference_step_id": reference.id if reference else None,
                "student_step_id": student.id,
                "reference_text": compared,
                "student_text": student.text,
                "alignment": relation,
                "equivalent": complete,
                "uses_condition": True,
                "math_valid": complete or branch,
                "is_first_error": first_error == index,
                "propagated": first_error is not None
                and index > first_error
                and not valid,
                "verification_scope": "original_equation_real_roots"
                if complete
                else "branch_root"
                if branch
                else "different_roots",
            }
        )
    return rows, first_error is None and submitted == roots


def verify_polynomial_repair(text, references, students, alignment, counter):
    first = next((row for row in alignment if row["is_first_error"]), None)
    if first is None:
        return counter
    index = first["index"]
    repaired = counter.get("repaired_steps", [])
    checked = None
    preserved = len(repaired) == len(students) and all(
        re.sub(r"\s+", "", normalize_expression(repaired[i]))
        == re.sub(r"\s+", "", normalize_expression(students[i].text))
        for i in range(index)
    )
    consistent = preserved and normalize_expression(
        counter.get("corrected_step", "")
    ) == normalize_expression(repaired[index])
    if consistent:
        records = [
            SimpleNamespace(id=step.id, text=value)
            for step, value in zip(students, repaired)
        ]
        checked = polynomial_alignment(text, references, records, repaired[-1])
    confirmed = checked is not None and checked[1]
    affected = sum(not row["equivalent"] for row in alignment[index:])
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
        "validation_scope": "polynomial_real_solution_set_and_preserved_prefix",
        "conclusion": f"保留前面正确的步骤，修正第 {index + 1} 步后，修复路径与原方程的完整实数解一致。"
        if confirmed
        else "当前修复尚未通过原方程完整实数解及原正确步骤的核验，请继续核对。",
    }
