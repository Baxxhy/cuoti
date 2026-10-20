from learning_planner import PlanCandidate, PlannerInput, plan_learning


def item(qid, **extra):
    return PlanCandidate(**({"id": qid, "subject": "数学"} | extra))


def test_action_priority_and_failure_recovery():
    assert (
        plan_learning(PlannerInput(prerequisite_missing=True)).action == "prerequisite"
    )
    assert plan_learning(PlannerInput(repeated_error=True)).action == "repair"
    assert plan_learning(PlannerInput(consecutive_failures=2)).action == "hint"
    assert plan_learning(PlannerInput(phase="independent")).action == "retry"
    assert plan_learning(PlannerInput(evidence_sufficient=False)).action == "explain"


def test_due_review_cannot_be_starved_by_new_items():
    result = plan_learning(
        PlannerInput(
            phase="done",
            candidates=[
                item("new", error_relevance=1),
                item("due", due=True, difficulty=1),
            ],
        )
    )
    assert result.action == "review" and result.question_id == "due"
    assert result.alternatives == ["new"]
    assert all(
        0 <= value <= 1
        for row in result.ranking
        for value in row["components"].values()
    )


def test_no_just_mastered_wrong_subject_or_over_budget_recommendations():
    result = plan_learning(
        PlannerInput(
            phase="done",
            current_subject="数学",
            candidates=[
                item("recent", just_mastered=True),
                item("long", estimated_minutes=20),
                item("other", subject="英语"),
            ],
            knowledge_card_ids=["card-1"],
        )
    )
    assert result.question_id is None and result.action == "prerequisite"
    assert result.knowledge_card_ids == ["card-1"]


def test_empty_bank_is_explicit_and_goals_stop_execution():
    result = plan_learning(PlannerInput(phase="done"))
    assert result.action == "stop" and "暂时没有" in result.reason
    for extra in [{"minutes_remaining": 0}, {"goal_remaining": 0}]:
        assert plan_learning(PlannerInput(**extra)).action == "stop"


def test_repetition_penalty_and_difficulty_are_used_in_actual_selection():
    result = plan_learning(
        PlannerInput(
            phase="done",
            candidates=[
                item("a", recent_exposures=3),
                item("b"),
                item("c", difficulty=1),
            ],
        )
    )
    assert result.question_id == "b"
    assert len(set(result.alternatives)) == len(result.alternatives)
