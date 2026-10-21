import pytest

from mastery_tracker import (
    AnswerEvidence,
    KnowledgeState,
    compute_aemt_cognition,
    update_mastery,
)


def event(**extra):
    return AnswerEvidence(
        **(
            {
                "event_id": "request-1",
                "verdict": "confirmed_correct",
                "scope": "original_question",
            }
            | extra
        )
    )


def test_independent_hint_and_revealed_answer_are_distinct():
    prior = KnowledgeState()
    independent = update_mastery(prior, event())
    hint = update_mastery(prior, event(hint_used=True))
    revealed = update_mastery(prior, event(solution_seen=True))
    assert independent.state.mastery > hint.state.mastery > prior.mastery
    assert revealed.state.mastery == prior.mastery
    assert revealed.state.evidence_count == 0 and revealed.state.solution_count == 1
    assert independent.state.independent_correct == 1 and hint.state.hinted_count == 1


def test_failure_is_negative_and_delayed_transfer_stronger():
    prior = KnowledgeState()
    wrong = update_mastery(prior, event(verdict="confirmed_incorrect"))
    delayed = update_mastery(prior, event(delayed_similar=True, days_since_last=3))
    assert wrong.state.mastery < prior.mastery
    assert delayed.state.mastery > update_mastery(prior, event()).state.mastery


@pytest.mark.parametrize(
    "extra",
    [
        {"source_current": False},
        {"student_confirmed": False},
        {"grading_reliable": False},
        {"verdict": "review_required"},
        {"scope": "local_step"},
    ],
)
def test_unreliable_and_local_work_cannot_update_mastery(extra):
    prior = KnowledgeState()
    result = update_mastery(prior, event(**extra))
    assert not result.changed and result.state == prior


def test_resume_is_not_an_observation_and_retry_is_idempotent():
    first = update_mastery(KnowledgeState(), event())
    retry = update_mastery(first.state, event())
    assert not retry.changed and retry.state == first.state


def test_time_changes_priority_without_inventing_new_answers():
    prior = KnowledgeState(mastery=0.8)
    recent = update_mastery(prior, event(verdict="review_required"))
    stale = update_mastery(prior, event(verdict="review_required", days_since_last=90))
    assert recent.state == stale.state == prior
    assert stale.forgetting_risk > recent.forgetting_risk
    retained = update_mastery(prior, event(days_since_last=90, delayed_similar=True))
    assert retained.forgetting_risk < stale.forgetting_risk


def test_long_answer_sequences_remain_finite_and_can_recover():
    state = KnowledgeState()
    for index in range(300):
        state = update_mastery(state, event(event_id=str(index))).state
    assert 0 < state.mastery < 1
    wrong = update_mastery(
        state, event(event_id="wrong", verdict="confirmed_incorrect")
    )
    assert wrong.state.mastery < state.mastery


def test_storage_adapter_does_not_apply_legacy_additive_awards():
    prior = {
        "mastery_score": 0.35,
        "evidence_count": 2,
        "confidence": 0.4,
        "near_transfer_rate": 0.5,
        "far_transfer_rate": 0,
        "forgetting_risk": 0.65,
        "update_reason": "",
    }
    mistake = {
        "probability": 0.5,
        "evidence_count": 2,
        "related_question_count": 1,
        "label": "移项",
        "status": "active",
        "successful_strategy": "",
        "failed_strategy": "",
    }
    independent, _ = compute_aemt_cognition(
        prior, mistake, {"aemt_event": event().model_dump(), "near_transfer": True}
    )
    hinted, _ = compute_aemt_cognition(
        prior,
        mistake,
        {"aemt_event": event(hint_used=True).model_dump(), "near_transfer": True},
    )
    revealed, _ = compute_aemt_cognition(
        prior,
        mistake,
        {"aemt_event": event(solution_seen=True).model_dump(), "near_transfer": True},
    )
    assert (
        independent["mastery_score"] > hinted["mastery_score"] > prior["mastery_score"]
    )
    assert independent["evidence_count"] == 3
    assert (
        revealed["mastery_score"] == prior["mastery_score"]
        and revealed["evidence_count"] == 2
    )
