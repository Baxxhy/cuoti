from .math_tools import compare_equivalence, solve_text_equation

REPAIR_EQUATION = "z + 2 = 9"


def assess(answer, expected, equation=""):
    answer = str(answer).strip()
    if "=" in answer:
        left, right = answer.split("=",1)
        # A variable assignment is acceptable for this fixed scalar-answer exercise.
        if len(left.strip()) == 1 and left.strip().isalpha() and left.strip() in equation:
            answer = right.strip()
    equal, checked = compare_equivalence(answer, str(expected))
    return {"status": "verified" if checked and equal else "inconsistent" if checked else "unverified", "correct": bool(checked and equal), "scope": "参考答案的数值或表达式等价性"}


def assess_repair(answer):
    solved, checked = solve_text_equation(REPAIR_EQUATION)
    if not checked: return {"status":"unverified","correct":False,"scope":"补救题求解未确定"}
    return assess(answer, solved.split("=",1)[1], REPAIR_EQUATION)
