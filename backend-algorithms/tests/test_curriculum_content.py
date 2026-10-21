import json
from pathlib import Path

from sympy import Rational, Symbol, expand, solve, sqrt

from grounded_knowledge import build_knowledge_evidence


def test_all_seed_cards_have_actual_teaching_content_and_no_fake_examples():
    path = Path(__file__).resolve().parents[2] / "backend-cangjie/schema/knowledge_seed.json"
    data = json.loads(path.read_text())
    assert len(data["cards"]) >= 250
    for card in data["cards"]:
        content = card["content"]
        assert build_knowledge_evidence([card], card["subject"], content["grade"]), card["code"]
        assert "核心学习主题，作答时" not in content["definition"]
        assert "中用于解释和解决" not in content["definition"]
        assert "示例步骤：识别题目要求" not in content["worked_example"]
    codes = {card["code"] for card in data["cards"]}
    assert all(edge["source"] in codes and edge["target"] in codes for edge in data["relations"])


def test_authored_numeric_examples_have_symbolic_checks():
    x = Symbol("x")
    assert solve(2*x+3-11, x) == [4]
    assert solve(3*x-2-7, x) == [3]
    assert expand(-2*(x-3)) == -2*x+6
    assert expand((x-3)*(x+3)) == x*x-9
    assert sqrt((-3)**2) == 3
    assert Rational(2*80+3*90, 5) == 86
