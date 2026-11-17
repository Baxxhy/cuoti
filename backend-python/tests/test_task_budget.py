import pytest
from cuoti_backend.task_budget import (
    TaskBudget,
    TaskBudgetExceeded,
    at_limit,
    limit_view,
)


def test_budget_never_returns_unlimited_zero_timeout():
    now = [100.0]
    budget = TaskBudget(clock=lambda: now[0])
    assert budget.timeout_seconds(200) == 45
    now[0] += 44.5
    with pytest.raises(TaskBudgetExceeded) as error:
        budget.timeout_seconds(200)
    assert error.value.stage == "remaining_budget"
    now[0] += 0.5
    with pytest.raises(TaskBudgetExceeded):
        budget.check("save")
    assert budget.elapsed_ms() == 45000


def test_task_run_and_round_limits_preserve_stop_view():
    assert not at_limit({"run_count": 71, "checkpoint": {"rounds": 23}})
    assert at_limit({"run_count": 72})
    assert at_limit({"checkpoint": {"rounds": 24}})
    assert limit_view()["input_kind"] == "none"
