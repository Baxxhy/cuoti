import asyncio

import pytest
from grading_compute import UnavailableGradingProvider
from learning_memory_compute import LearningMemoryEntry, LearningMemorySnapshot
from learning_task_compute import Checkpoint, TaskAction, TaskContext, execute_task
from pydantic import ValidationError


def entry(**change):
    return {
        "ref": "review_record:r1",
        "kind": "review_record",
        "classification": "verified_event",
        "question_id": "q1",
        "source_refs": ["review_record:r1", "review:p1"],
        "version": "a" * 64,
        "observed_at": 100,
        "expires_at": 100 + 90 * 86400,
        "summary": "这次复习作答有误",
        "independence": "unknown",
        "outcome": "incorrect",
        **change,
    }


def test_memory_types_cannot_promote_self_report_or_estimate_to_fact():
    for bad in [
        entry(kind="self_check", ref="self_check:s1", source_refs=["self_check:s1"]),
        entry(
            outcome="incorrect",
            kind="mastery",
            classification="estimate",
            ref="mastery:m1",
            source_refs=["mastery:m1"],
        ),
        entry(expires_at=100 + 91 * 86400),
        entry(expires_at=99),
        entry(observed_at=True),
        entry(source_refs=["someone_else"]),
        entry(version="unknown"),
        entry(code="execute()"),
    ]:
        with pytest.raises(ValidationError):
            LearningMemoryEntry.model_validate(bad)
    valid = LearningMemoryEntry.model_validate(
        entry(
            kind="self_check",
            ref="self_check:s1",
            classification="student_self_report",
            source_refs=["self_check:s1"],
            independence="not_applicable",
            outcome="unknown",
        )
    )
    assert valid.classification == "student_self_report"
    with pytest.raises(ValidationError):
        LearningMemorySnapshot(entries=[valid, valid])


def context(snapshot):
    return TaskContext(
        question_id="q1",
        subject="数学",
        question_text="解方程：2x+3=11",
        expected="x=4",
        student_steps=["2x=14"],
        memory_snapshot=snapshot,
        memory_refs=snapshot.refs,
        memory_versions=snapshot.versions,
    )


def test_validated_history_changes_real_rule_tool_path_and_only_uses_real_ref():
    snapshot = LearningMemorySnapshot(entries=[entry()])
    result = asyncio.run(
        execute_task(
            UnavailableGradingProvider(),
            context(snapshot),
            Checkpoint(),
            TaskAction(kind="hint"),
        )
    )
    assert [trace.tool_name for trace in result.traces] == ["step_alignment"]
    assert result.traces[0].memory_refs == ["review_record:r1"]
    assert result.traces[0].planner_source == "rule" and not result.learning_eligible
    neutral = snapshot.model_copy(
        update={
            "entries": [LearningMemoryEntry.model_validate(entry(outcome="correct"))]
        }
    )
    result = asyncio.run(
        execute_task(
            UnavailableGradingProvider(),
            context(neutral),
            Checkpoint(),
            TaskAction(kind="hint"),
        )
    )
    assert result.traces[0].tool_name == "knowledge_search"


def test_manifest_mismatch_is_rejected_before_planner_execution():
    snapshot = LearningMemorySnapshot(entries=[entry()])
    values = context(snapshot).model_dump()
    values["memory_refs"] = ["review_record:foreign"]
    with pytest.raises(ValidationError, match="manifest"):
        TaskContext.model_validate(values)


def test_memory_synopsis_keeps_whole_bounded_entries():
    entries = []
    for i in range(4):
        entries.append(
            entry(
                ref=f"cognitive:{i}",
                kind="cognitive",
                source_refs=[f"cognitive:{i}"],
                summary="已核对的记录" * 40 + "，不能据此断言掌握",
            )
        )
    for i in range(3):
        entries.append(
            entry(
                ref=f"self_check:{i}",
                kind="self_check",
                classification="student_self_report",
                source_refs=[f"self_check:{i}"],
                independence="not_applicable",
                outcome="unknown",
                summary="学生自己的话" * 40 + "，还没有独立验证",
            )
        )
    snapshot = LearningMemorySnapshot(entries=entries)
    assert len(snapshot.summary) <= 1800
    assert all(
        part in {e.summary for e in snapshot.entries}
        for part in snapshot.summary.split("；")
    )
    assert len(snapshot.entries) == 7
