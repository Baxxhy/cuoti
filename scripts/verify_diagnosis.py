#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.diagnosis import align_steps


def main() -> int:
    cases = json.loads((ROOT / "data/functional_validation/diagnosis_cases.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        refs = [SimpleNamespace(id=f"r{i}", text=text) for i, text in enumerate(case["reference_steps"])]
        students = [SimpleNamespace(id=f"s{i}", text=text) for i, text in enumerate(case["student_steps"])]
        aligned = align_steps(refs, students, case["subject"], case["question"])
        first = next((item for item in aligned if item["is_first_error"]), None)
        predicted_step = first["index"] if first else None; predicted_type = first["alignment"] if first else "none"
        step_ok = predicted_step is not None and abs(predicted_step - case["gold_first_error_step"]) <= 1
        type_ok = predicted_type == case["gold_error_type"]
        results.append({"case_id": case["case_id"], "gold_step": case["gold_first_error_step"],
                        "predicted_step": predicted_step, "gold_type": case["gold_error_type"],
                        "predicted_type": predicted_type, "step_ok": step_ok, "type_ok": type_ok})
    step_pass = sum(item["step_ok"] for item in results); type_pass = sum(item["type_ok"] for item in results)
    assert step_pass >= 20 and type_pass >= 20, (step_pass, type_pass)
    report = {"passed": True, "case_count": 24, "first_error_step_pass": step_pass,
              "error_type_pass": type_pass, "threshold": 20, "results": results}
    target = ROOT / "reports/verification/diagnosis.json"; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("passed", "case_count", "first_error_step_pass", "error_type_pass", "threshold")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
