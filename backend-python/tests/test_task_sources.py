import pytest
from cuoti_backend import task_sources


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (1, 1.0, True),
        (True, 1, False),
        ("1", 1, False),
        ([1, 2], [2, 1], False),
        ({"x": 1}, {"x": 1.0}, True),
        (None, None, True),
    ],
)
def test_source_transport_equality(left, right, expected):
    assert task_sources.source_equal(left, right) is expected


def test_existing_source_never_silently_replaced(monkeypatch):
    q = dict.fromkeys(
        [
            "question_text",
            "subject",
            "grade",
            "question_type",
            "student_answer",
            "options",
            "knowledge_points",
            "confirmed",
            "status",
        ],
        "original",
    )
    source = {
        "question": q,
        **dict.fromkeys(
            ["work", "steps", "assets", "analysis", "references", "diagnosis"], None
        ),
    }
    monkeypatch.setattr(
        task_sources,
        "rows",
        lambda *a: [{"source": source, "input_fingerprint": "old"}],
    )
    monkeypatch.setattr(
        task_sources, "execute", lambda *a: pytest.fail("must not overwrite source")
    )
    with pytest.raises(task_sources.TaskSourceError) as error:
        task_sources.capture_source(
            None, {"id": "task", "input_fingerprint": "new"}, source
        )
    assert error.value.reason == "source_fingerprint"


def test_version_invalidation_preserves_cancelled_and_does_not_repeat(monkeypatch):
    calls = []
    monkeypatch.setattr(task_sources, "execute", lambda *args: calls.append(args))
    q = dict.fromkeys(
        [
            "question_text",
            "subject",
            "grade",
            "question_type",
            "student_answer",
            "options",
            "knowledge_points",
            "confirmed",
            "status",
        ],
        "changed",
    )
    source = {
        "question": q,
        **dict.fromkeys(
            ["work", "steps", "assets", "analysis", "references", "diagnosis"], None
        ),
    }
    task = {"id": "task", "input_fingerprint": "old", "status": "running", "version": 7}
    assert not task_sources.validate_version(None, task, source)
    assert task["status"] == "stale" and task["version"] == 8 and len(calls) == 2
    assert not task_sources.validate_version(None, task, source)
    assert len(calls) == 2
    assert not task_sources.validate_version(
        None, {**task, "status": "cancelled"}, source
    )
    assert len(calls) == 2
