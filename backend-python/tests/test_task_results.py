import pytest
from cuoti_backend.protocol import ApiError
from cuoti_backend.task_results import validate_result


@pytest.mark.parametrize(
    "trace",
    [
        {"tool_name": "unknown", "validation": "verified"},
        {"tool_name": "check_step", "validation": "invented"},
        {
            "tool_name": "check_step",
            "validation": "verified",
            "memory_refs": ["foreign"],
        },
    ],
)
def test_task_result_rejects_unverified_tools_and_memory(trace):
    with pytest.raises(ApiError):
        validate_result(
            {"status": "waiting_student", "traces": [trace]}, {}, {"entries": []}
        )


def test_task_result_bounds_and_known_trace():
    trace = {"tool_name": "check_step", "validation": "needs_review", "memory_refs": []}
    validate_result({"status": "needs_review", "traces": [trace]}, {}, {"entries": []})
    with pytest.raises(ApiError):
        validate_result({"status": "running", "traces": []}, {}, {"entries": []})
    with pytest.raises(ApiError):
        validate_result(
            {"status": "completed", "traces": [trace] * 4}, {}, {"entries": []}
        )
