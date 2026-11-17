"""Execution limits shared by the learning task worker and its public view."""

from time import monotonic


class TaskBudgetExceeded(Exception):
    def __init__(self, stage):
        super().__init__("本次执行已到时限，结果未提交")
        self.stage = stage


class TaskBudget:
    def __init__(self, limit=45, *, clock=monotonic):
        self.clock = clock
        self.started = clock()
        self.limit = limit

    def elapsed_ms(self):
        return int((self.clock() - self.started) * 1000)

    def remaining(self):
        return self.limit - (self.clock() - self.started)

    def check(self, stage):
        if self.remaining() <= 0:
            raise TaskBudgetExceeded(stage)

    def timeout_seconds(self, cap, reserve_seconds=0):
        seconds = int(self.remaining()) - reserve_seconds
        if seconds < 1:
            raise TaskBudgetExceeded("remaining_budget")
        return min(seconds, cap)


def at_limit(task):
    return (
        task.get("run_count", 0) >= 72
        or (task.get("checkpoint") or {}).get("rounds", 0) >= 24
    )


def stopped_view(message):
    return {
        "title": message,
        "prompt_blocks": [],
        "input_kind": "none",
        "primary_action": "",
        "secondary_actions": [],
        "feedback": message,
    }


def limit_view():
    view = stopped_view("已到本次学习上限。结束后可从原题重开，记录会保留。")
    view["title"] = "本次先停在这里"
    return view
