import pytest
from cuoti_backend.protocol import ApiError
from cuoti_backend.task_planning import validate_recommendation


def test_recommendation_requires_owned_prepared_candidate_scope():
    domain = {
        "practice_candidates": [
            {"id": "one", "source": "notebook"},
            {"id": "two", "source": "dataset"},
        ]
    }
    validate_recommendation(
        {
            "student_view": {
                "recommendation": {
                    "question_id": "one",
                    "question_source": "notebook",
                    "alternatives": ["two"],
                }
            }
        },
        domain,
    )
    for plan in [
        {"question_id": "foreign", "question_source": "notebook"},
        {"question_id": "one", "question_source": "dataset"},
        {"question_id": "one", "question_source": "notebook", "alternatives": ["one"]},
    ]:
        with pytest.raises(ApiError):
            validate_recommendation({"student_view": {"recommendation": plan}}, domain)
    with pytest.raises(ApiError):
        validate_recommendation(
            {
                "student_view": {
                    "recommendation": {
                        "question_id": "one",
                        "question_source": "notebook",
                    }
                }
            },
            {
                "practice_candidates": [
                    {"id": "one", "source": "notebook", "just_mastered": True}
                ]
            },
        )
