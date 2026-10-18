#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/functional_validation"


def main() -> int:
    images = json.loads((DATA / "images.json").read_text(encoding="utf-8"))
    diagnoses = json.loads((DATA / "diagnosis_cases.json").read_text(encoding="utf-8"))
    agent = json.loads((DATA / "agent_cases.json").read_text(encoding="utf-8"))
    e2e = json.loads((DATA / "e2e_cases.json").read_text(encoding="utf-8"))
    assert [len(images), len(diagnoses), len(agent), len(e2e)] == [24, 24, 12, 6]
    assert Counter(item["subject"] for item in images) == {"数学": 16, "物理": 5, "历史": 3}
    assert Counter(item["interference"] for item in images) == {"clear": 8, "annotated": 8, "degraded": 8}
    required = {"case_id", "image", "question", "formulas", "student_answer", "student_steps",
                "teacher_comment", "subject", "interference"}
    red_cases = 0
    for item in images:
        assert required <= set(item)
        image = cv2.imread(str(ROOT / item["image"])); assert image is not None and image.size > 0
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.bitwise_or(cv2.inRange(hsv, np.array([0, 80, 60]), np.array([12, 255, 255])),
                              cv2.inRange(hsv, np.array([165, 80, 60]), np.array([180, 255, 255])))
        red_cases += int(np.count_nonzero(mask) > 100)
    assert red_cases >= 8
    assert len({item["gold_error_type"] for item in diagnoses}) >= 9
    assert all(len(item["expected_pipeline"]) >= 12 for item in e2e)
    report = {"passed": True, "dataset": "MindTrace-Functional-Validation-v1", "images": 24,
              "subjects": dict(Counter(item["subject"] for item in images)),
              "interference": dict(Counter(item["interference"] for item in images)),
              "red_annotation_cases": red_cases, "diagnoses": 24, "agent_branches": 12, "e2e": 6}
    target = ROOT / "reports/verification/functional_data.json"; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
