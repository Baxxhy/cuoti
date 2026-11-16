import pytest
from cuoti_backend.tutoring import canonical, policy


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("teach_back_retry", "teach_back"),
        ("near_remediation", "near_transfer"),
        ("transfer_insufficient", "far_transfer"),
        ("finished", "finished"),
        ("other", "understanding"),
    ],
)
def test_canonical_tutoring_stages(raw, expected):
    assert canonical(raw) == expected


def test_teaching_policy_uses_local_evidence():
    assert policy("计算题", False, True, "5")["mode"] == "full"
    assert policy("计算题", False, False, "5")["mode"] == "compressed"
    assert policy("综合题", True, True, "A")["question_type"] == "choice"
    assert policy("单选题", True, True, "")["mode"] == "full"


def test_dialogue_knowledge_grade_filter_and_dependency_dedup(monkeypatch):
    from cuoti_backend import knowledge_mapping

    def card(id, name, grade, aliases=()):
        return {
            "id": id,
            "code": id,
            "name": name,
            "subject": "数学",
            "content": {"grade": grade, "related_knowledge": list(aliases)},
        }

    eq = card("eq", "方程", "初一")
    high = card("high", "方程", "高一")
    alias = card("alias", "等式性质", "初一", ["移项"])
    basic = card("basic", "基础", "初一")

    def select(db, table, sql, params=()):
        return [alias, eq, high] if "LIMIT 200" in sql else [basic]

    monkeypatch.setattr(knowledge_mapping, "select_rows", select)
    result = knowledge_mapping.dialogue_cards(None, "方程移项", "数学", "初一")
    assert [r["code"] for r in result] == ["eq", "alias", "basic"]
    assert result[0]["retrieval_role"] == "anchor"
    assert result[-1]["anchor_code"] == "eq"
