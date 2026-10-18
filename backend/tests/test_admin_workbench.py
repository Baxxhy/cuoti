from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.admin_workbench import build_agent_trace, sanitize_admin_value


def test_sanitize_admin_value_removes_sensitive_fields_recursively():
    payload = {
        "logical_model": "Qwen",
        "credential": "secret",
        "nested": {"password_hash": "hash", "status": "ok"},
        "items": [{"api_key": "key", "count": 2}],
    }

    assert sanitize_admin_value(payload) == {
        "logical_model": "Qwen",
        "nested": {"status": "ok"},
        "items": [{"count": 2}],
    }


def test_build_agent_trace_exposes_decisions_without_private_reasoning():
    moment = datetime(2026, 8, 25, 9, 30, tzinfo=timezone.utc)
    runs = [
        SimpleNamespace(
            id="run-1",
            created_at=moment,
            agent_name="mindtrace_tutor",
            status="completed",
            result={
                "branch": "guided_question",
                "next_goal": "确认学生理解限制条件",
                "observation": {"memory_count": 2},
                "plan": {"steps": ["读取长期记忆", "执行知识检索"]},
                "verification": {"status": "verified", "evidence_refs": ["mastery:m1"]},
                "chain_of_thought": "private",
            },
        )
    ]
    calls = [
        SimpleNamespace(
            id="call-1",
            created_at=moment,
            agent_run_id="run-1",
            tool_name="knowledge_search",
            input_json={"query": "一元二次方程", "api_key": "secret"},
            output_json={"result_count": 3, "credential": "secret"},
        )
    ]

    trace = build_agent_trace(runs, calls)

    assert trace == [
        {
            "id": "run-1",
            "time": "2026-08-25T09:30:00+00:00",
            "agent": "教学决策智能体",
            "status": "completed",
            "decision": "引导式提问",
            "goal": "确认学生理解限制条件",
            "observation": {"memory_count": 2},
            "plan": {"steps": ["读取长期记忆", "执行知识检索"]},
            "verification": {"status": "verified", "evidence_refs": ["mastery:m1"]},
            "actions": [
                {
                    "id": "call-1",
                    "tool": "知识检索",
                    "input": {"query": "一元二次方程"},
                    "output": {"result_count": 3},
                }
            ],
        }
    ]
    assert "private" not in str(trace)
