from adaptive_practice import AdaptivePracticeInput, information_gain, select_practice


def question(qid, skill):
    return {"id": qid, "subject": "数学", "knowledge_points": [skill], "options": ["A", "B", "C", "D"]}


def test_prioritizes_unresolved_skill_using_only_confirmed_student_answers():
    candidates = [question("weak", "等式"), question("strong", "分式")]
    observations = [{**question(f"past-{i}", "等式"), "correct": False} for i in range(3)]
    observations += [{**question(f"known-{i}", "分式"), "correct": True} for i in range(8)]
    result = select_practice(AdaptivePracticeInput(candidates=candidates, observations=observations, count=1))
    assert result["question_ids"] == ["weak"]
    assert result["trace"][0]["evidence_count"] == 3
    assert result["calibration"] == "cold_start_defaults"


def test_assisted_and_unconfirmed_observations_do_not_inflate_mastery():
    candidates = [question("a", "等式"), question("b", "分式")]
    baseline = select_practice(AdaptivePracticeInput(candidates=candidates, count=2))
    assisted = [{**question("a", "等式"), "correct": True, "independent": False}]
    pending = [{**question("b", "分式"), "correct": False, "confirmed": False}]
    assert select_practice(AdaptivePracticeInput(candidates=candidates, observations=assisted+pending, count=2)) == baseline


def test_information_gain_and_repeat_avoidance_are_real_selection_signals():
    assert information_gain(0.5, 0.25) > information_gain(0.99, 0.25)
    candidates = [question("a", "等式"), question("b", "等式")]
    result = select_practice(AdaptivePracticeInput(candidates=candidates, observations=[{**candidates[0], "correct": False}], count=2))
    assert result["question_ids"] == ["b", "a"]
    assert len(set(result["question_ids"])) == 2


def test_unannotated_bank_uses_explicit_coarse_basis_without_invented_concepts():
    result = select_practice(AdaptivePracticeInput(candidates=[{"id": "a", "subject": "物理", "question_type": "计算题"}], count=1))
    assert result["trace"][0]["basis"] == "question_type"
    assert result["trace"][0]["evidence_count"] == 0


def test_long_correct_streak_does_not_make_later_errors_impossible():
    candidate = question("new", "等式")
    history = [{**question(f"past-{i}", "等式"), "correct": True} for i in range(399)]
    confident = select_practice(AdaptivePracticeInput(candidates=[candidate], observations=history, count=1))
    history.append({**question("last", "等式"), "correct": False})
    revised = select_practice(AdaptivePracticeInput(candidates=[candidate], observations=history, count=1))
    assert revised["trace"][0]["prior"] < confident["trace"][0]["prior"] < 1
