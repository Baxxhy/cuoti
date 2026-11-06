from grounded_knowledge import build_knowledge_evidence


def card(code, subject="数学", **extra):
    return {"code": code, "name": code, "subject": subject, "content": {"definition": "等式两边同除以非零数，等式仍成立。", "formulas": ["a=b"]}, **extra}


def test_graph_context_has_real_bounded_sources_and_excludes_foreign_or_orphan_cards():
    cards = [card("equation"), card("property", retrieval_role="prerequisite", anchor_code="equation"),
             card("foreign", "英语"), card("orphan", retrieval_role="prerequisite", anchor_code="missing")]
    sources = build_knowledge_evidence(cards, "数学", "初一")
    assert [x["code"] for x in sources] == ["equation", "property"]
    assert sources[1]["anchor_code"] == "equation"
    assert all(len(x["source_hash"]) == 64 for x in sources)
    assert build_knowledge_evidence([], "数学") == []


def test_evidence_hash_changes_with_source_and_grade_boundaries_are_respected():
    c = card("equation")
    first = build_knowledge_evidence([c], "数学")
    c["content"]["definition"] = "等式两边加同一个数，等式仍成立。"
    second = build_knowledge_evidence([c], "数学")
    assert first[0]["source_hash"] != second[0]["source_hash"]
    c["content"]["grade"] = "高一"
    assert build_knowledge_evidence([c], "数学", "初一") == []
    c["content"]["grade"] = "初一"
    assert len(build_knowledge_evidence([c], "数学", "高一")) == 1
    assert len(build_knowledge_evidence([card(str(i)) for i in range(20)], "数学")) == 6


def test_generic_seed_placeholders_are_not_presented_as_teaching_evidence():
    generic = card("placeholder")
    generic["content"] = {"definition": "等式是数学中用于解释和解决问题的核心知识。"}
    assert build_knowledge_evidence([generic], "数学") == []
    generic["content"]["formulas"] = ["a=b => a+c=b+c"]
    evidence = build_knowledge_evidence([generic], "数学")
    assert evidence[0]["definition"] == "" and evidence[0]["formulas"]
