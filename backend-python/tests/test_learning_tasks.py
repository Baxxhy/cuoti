import pytest
from cuoti_backend.learning_tasks import validate_visual, visual_values
from cuoti_backend.protocol import ApiError


def test_visual_action_checks_domain_and_step():
    task = {
        "checkpoint": {
            "phase": "repair",
            "visual_open": True,
            "visualization": {
                "source_phase": "repair",
                "spec": {
                    "interactive_variables": [
                        {"name": "delta", "min": -1, "max": 1, "step": 0.5}
                    ]
                },
            },
        }
    }
    validate_visual(task, {}, "observe_visualization", {"delta": 0.5})
    for values in [{}, {"delta": 0.2}, {"delta": 2}]:
        with pytest.raises(ApiError):
            validate_visual(task, {}, "observe_visualization", values)
    for value in [{"delta": True}, {"delta": float("nan")}, {"evil": 1}]:
        with pytest.raises(ApiError):
            visual_values({"visual_values": value})
    with pytest.raises(ApiError):
        validate_visual(task, {"visual_values": {}}, "hint", {})
    task["checkpoint"]["phase"] = "contrast"
    with pytest.raises(ApiError):
        validate_visual(task, {}, "close_visualization", {})
