from app.services.academic_text import academic_summary, repair_question_title


def test_summaries_keep_complete_math_and_bounded_plain_prose():
    source = r"计算 $\frac{x^2+1}{2}$ 的值"
    assert academic_summary(source, 8) == source
    assert academic_summary("普通标题", 2) == "普通"


def test_old_truncated_auto_titles_use_original_without_overwriting_custom_names():
    source = r"计算 $\frac{x^2+1}{2}$ 的值"
    assert repair_question_title({"title": source[:12], "question_text": source})["title"] == source
    assert repair_question_title({"title": "$x$ 专题", "question_text": source})["title"] == "$x$ 专题"
