from .math_tools import compare_equivalence, solve_text_equation

def assess(answer, expected, equation=""):
    answer = str(answer).strip()
    if "=" in answer:
        left, right = answer.split("=",1)
        # A variable assignment is acceptable for this fixed scalar-answer exercise.
        if len(left.strip()) == 1 and left.strip().isalpha() and left.strip() in equation:
            answer = right.strip()
    equal, checked = compare_equivalence(answer, str(expected))
    return {"status": "verified" if checked and equal else "inconsistent" if checked else "unverified", "correct": bool(checked and equal), "scope": "参考答案的数值或表达式等价性"}


def assess_repair(answer, equation="", expected=None):
    """Score only the immutable actual variant; no global fallback exercise."""
    solved, checked = solve_text_equation(equation)
    if not checked or ", " in solved:
        return {"status":"unverified","correct":False,"scope":"当前练习不在单解方程核验范围，需要人工核对"}
    trusted = solved.split("=",1)[1]
    if expected is not None:
        equal, valid = compare_equivalence(str(expected), trusted)
        if not valid or not equal:
            return {"status":"unverified","correct":False,"scope":"变式参考答案未通过程序核验"}
    result = assess(answer, trusted, equation)
    result["status"] = {"verified":"verified_correct","inconsistent":"verified_incorrect"}.get(result["status"],"unverified")
    result["scope"] = "实际变式题的单变量单解实数方程与答案等价性"
    return result
