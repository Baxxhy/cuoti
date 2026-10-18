import pytest
from fastapi import HTTPException

from app.learning_api import ManualQuestion
from app.request_validation import (
    LoginRequest,
    PaperCreateRequest,
    PaperUpdateRequest,
    RegisterRequest,
    validated_payload,
)


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (RegisterRequest, {"email": "invalid", "password": "secret"}),
        (RegisterRequest, {"email": "student@example.test", "password": {"key": "sensitive-value"}}),
        (LoginRequest, {"email": "student@example.test", "password": "x" * 257}),
        (PaperCreateRequest, {"title": " "}),
        (PaperUpdateRequest, {"items": [{"question_id": "q", "score": -1}]}),
        (PaperCreateRequest, {"filters": {"mastery_min": 0.8, "mastery_max": 0.2}}),
        (PaperCreateRequest, {"filters": {"mastery_min": "bad"}}),
    ],
)
def test_invalid_request_has_readable_422_without_echoing_input(schema, payload):
    with pytest.raises(HTTPException) as error:
        validated_payload(schema, payload)
    assert error.value.status_code == 422
    assert "sensitive-value" not in str(error.value.detail)
    assert all("input" not in item for item in error.value.detail)


def test_paper_update_does_not_clear_omitted_items():
    assert validated_payload(PaperUpdateRequest, {"title": "  新名称  "}) == {"title": "新名称"}


def test_manual_multiple_choice_requires_unique_options_and_preserves_type():
    item = ManualQuestion.model_validate(
        {
            "question_text": "选出正数",
            "question_type": "多选题",
            "options": [{"label": "A", "text": "1"}, {"label": "B", "text": "2"}],
        }
    )
    assert item.question_type == "多选题"
    with pytest.raises(ValueError):
        ManualQuestion.model_validate(
            {
                "question_text": "选出正数",
                "question_type": "多选题",
                "options": [{"label": "A", "text": "1"}, {"label": "A", "text": "2"}],
            }
        )
    with pytest.raises(ValueError):
        ManualQuestion.model_validate({"question_text": "选出正数", "question_type": "单选题"})
