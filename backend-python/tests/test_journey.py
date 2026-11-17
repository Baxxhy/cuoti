from cuoti_backend.journey import build, recent

NOW = "2026-11-17T15:00:00+00:00"


def source():
    return {
        "question": {
            "id": "q",
            "created_at": NOW,
            "title": "题目",
            "question_text": "3x=15",
            "subject": "数学",
            "question_type": "计算题",
            "confirmed": True,
            "status": "ready",
        }
    }


def test_journey_evidence_and_chinese_day_boundary():
    data = source()
    data.update(
        diagnosis={"id": "d", "created_at": NOW},
        sessions=[
            {
                "id": "s",
                "created_at": NOW,
                "updated_at": NOW,
                "status": "completed",
                "state": {
                    "understanding_passed": True,
                    "teach_back_passed": True,
                    "near_transfer": True,
                    "far_transfer": True,
                    "assisted": True,
                },
            }
        ],
        practices=[
            {
                "id": "p",
                "created_at": NOW,
                "correct": True,
                "grading_details": {
                    "can_update_learning": True,
                    "question_changed": True,
                },
            }
        ],
        reviews=[
            {
                "id": "r",
                "created_at": NOW,
                "grade": "pending",
                "correct": True,
                "grading_details": {"can_update_learning": True},
            }
        ],
        plans=[
            {"id": "today", "status": "pending", "due_at": "2026-11-17T15:59:59+00:00"},
            {
                "id": "tomorrow",
                "status": "pending",
                "due_at": "2026-11-17T16:00:00+00:00",
            },
        ],
    )
    result = build(data, NOW)
    assert result["review"] == {
        "completed": 0,
        "due": 1,
        "next_due_at": "2026-11-17T15:59:59+00:00",
    }
    assert result["practice"] == {
        "attempts": 1,
        "verified_attempts": 0,
        "correct": 0,
        "pending": 0,
    }
    assert result["next_action"]["url"].endswith("plan=today")
    assert result["stages"][2]["completed"] is True
    assert result["stages"][3]["completed"] is False
    data["sessions"][0]["state"]["question_changed"] = True
    assert build(data, NOW)["stages"][2]["completed"] is False


def test_journey_navigation_priority_and_stable_event_limit():
    data = source()
    assert "diagnosis" in build(data, NOW)["next_action"]["url"]
    data["question"]["confirmed"] = False
    assert "ocr" in build(data, NOW)["next_action"]["url"]
    data.update(job={"id": "job", "status": "running"})
    assert "job=job" in build(data, NOW)["next_action"]["url"]
    data["question"]["status"] = "awaiting_crop"
    assert "crop" in build(data, NOW)["next_action"]["url"]
    events = [{"id": str(index), "time": NOW} for index in range(40)]
    assert [item["id"] for item in recent(events)] == [
        str(index) for index in range(30)
    ]
