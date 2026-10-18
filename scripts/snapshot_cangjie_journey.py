"""Generate fixed projection results from the original Python implementation."""

import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.learning_journey import build_learning_journey


def row(identifier, **fields):
    return {
        "id": identifier,
        "created_at": "2026-10-15T10:00:00+00:00",
        "updated_at": "2026-10-15T10:00:00+00:00",
        **fields,
    }


def original(data, now):
    def record(item):
        return SimpleNamespace(
            **{
                key: datetime.fromisoformat(value)
                if key in {"created_at", "updated_at", "due_at"}
                else value
                for key, value in item.items()
            }
        )

    return build_learning_journey(
        record(data["question"]),
        **{
            key: record(data[key]) if data[key] else None
            for key in ("analysis", "diagnosis", "job", "ocr")
        },
        **{
            key: [record(value) for value in data[key]]
            for key in ("sessions", "practices", "plans", "reviews")
        },
        now=datetime.fromisoformat(now),
    )


def generate():
    base = {
        "question": row(
            "q",
            title="一次方程",
            question_text="3x=15",
            subject="数学",
            question_type="填空题",
            status="confirmed",
            confirmed=True,
        ),
        "analysis": None,
        "diagnosis": None,
        "job": None,
        "ocr": None,
        "sessions": [],
        "practices": [],
        "plans": [],
        "reviews": [],
    }
    cases = []

    def add(name, **changes):
        data = {**deepcopy(base), **changes}
        now = "2026-10-16T12:34:56.123456+00:00"
        cases.append(
            {"name": name, "input": data, "now": now, "expected": original(data, now)}
        )

    add("diagnosis-required")
    add(
        "crop-before-running",
        question={**base["question"], "status": "awaiting_crop", "confirmed": False},
        job=row("j", status="running"),
    )
    for status in ("pending", "running", "failed", "completed"):
        add(
            "unconfirmed-" + status,
            question={**base["question"], "confirmed": False},
            job=row("j", status=status),
        )
    base["diagnosis"] = row("d", root_misconception="移项符号", user_confirmed=True)
    base["analysis"] = row("a", verified=True)
    base["ocr"] = row("o")
    add("learning-not-started")
    for flags in (
        {},
        {"understanding_passed": True},
        {"understanding_passed": True, "teach_back_passed": True},
        {"near_transfer": True},
        {"near_transfer": True, "far_transfer": True},
        {"near_transfer": True, "far_transfer": True, "assisted": True},
        {"near_transfer": True, "far_transfer": True, "transfer_insufficient": True},
        {
            "understanding_passed": True,
            "teach_back_passed": True,
            "near_transfer": True,
            "far_transfer": True,
            "question_changed": True,
        },
    ):
        for status in ("active", "completed"):
            add(
                f"session-{len(cases)}", sessions=[row("s", status=status, state=flags)]
            )
    sessions = [
        row("older", status="active", state={}, created_at="2026-10-14T10:00:00+00:00"),
        row(
            "newer",
            status="active",
            state={},
            created_at="2026-10-15T10:00:00.000001+00:00",
        ),
    ]
    add("newest-active", sessions=sessions)
    # Before 00:00 Asia/Shanghai is due; exactly midnight belongs to the next day.
    plans = [
        row("today", status="pending", due_at="2026-10-16T15:59:59.999999+00:00"),
        row("tomorrow", status="pending", due_at="2026-10-16T16:00:00+00:00"),
        row("done", status="completed", due_at="2026-01-01T00:00:00+00:00"),
    ]
    add("day-boundary", plans=plans)
    add("active-before-due", plans=plans, sessions=sessions)
    records = []
    for index, details in enumerate(
        (
            {},
            {"can_update_learning": False},
            {"can_update_learning": True},
            {"can_update_learning": True, "question_changed": True},
            {"question_changed": True},
        )
    ):
        for correct in (True, False):
            records.append(
                row(
                    f"r{index}-{correct}",
                    grading_details=details,
                    correct=correct,
                    grade="good",
                )
            )
    add(
        "evidence-filter",
        practices=records,
        reviews=[
            *records,
            row(
                "waiting",
                grade="pending",
                correct=True,
                grading_details={"can_update_learning": True},
            ),
        ],
    )
    add(
        "event-limit-stable-order",
        sessions=[
            row(
                f"s{i}",
                status="completed",
                state={},
                updated_at=f"2026-10-15T10:00:{i:02d}+00:00",
            )
            for i in range(50)
        ],
        practices=records,
        reviews=records,
    )
    path = ROOT / "backend-cangjie/tests/journey_parity.json"
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n")
    print(f"Original journey fixtures: {len(cases)}")


if __name__ == "__main__":
    generate()
