#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from functional_flow import run_functional_case


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id")
    args = parser.parse_args()
    image_manifest = json.loads((ROOT / "data/functional_validation/images.json").read_text(encoding="utf-8"))
    image_by_id = {item["case_id"]: item for item in image_manifest}
    cases = json.loads((ROOT / "data/functional_validation/e2e_cases.json").read_text(encoding="utf-8"))
    if args.case_id:
        cases = [case for case in cases if case["case_id"] == args.case_id]
        assert cases, args.case_id
    results = []
    client = httpx.Client(timeout=360)
    run_id = int(time.time())
    for index, case in enumerate(cases):
        started = time.perf_counter()
        try:
            flow = run_functional_case(
                client, case, image_by_id[case["image_case_id"]],
                f"e2e-{run_id}-{index + 1}@minddimension.local",
            )
            required = {"qwen_vision": flow["qwen_vision"], "qwen_text": flow["qwen_text"],
                        "mysql": bool(flow["question_id"]),
                        "visualization": bool(flow["visualization_id"]), "export": Path(flow["export_path"]).exists()}
            assert all(required.values()), required
            results.append({"case_id": case["case_id"], "name": case["name"], "subject": case["subject"],
                            "passed": True, "duration_seconds": round(time.perf_counter() - started, 2),
                            "checks": required, "flow": flow})
        except (AssertionError, httpx.HTTPError, KeyError, ValueError, RuntimeError) as exc:
            results.append({"case_id": case["case_id"], "name": case["name"], "subject": case["subject"],
                            "passed": False, "duration_seconds": round(time.perf_counter() - started, 2),
                            "error": f"{type(exc).__name__}: {str(exc)[:400]}"})
    target = ROOT / "reports/verification/live_e2e.json"; target.parent.mkdir(parents=True, exist_ok=True)
    if args.case_id and target.exists():
        old_results = json.loads(target.read_text(encoding="utf-8"))["results"]
        replacements = {item["case_id"]: item for item in results}
        results = [replacements.get(item["case_id"], item) for item in old_results]
    passed = sum(item["passed"] for item in results)
    report = {"passed": passed == len(results), "case_count": len(results), "passed_count": passed,
              "threshold": len(results), "subjects": {subject: sum(item["passed"] and item["subject"] == subject for item in results)
                                             for subject in ("数学", "物理", "历史")}, "results": results}
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("passed", "case_count", "passed_count", "threshold", "subjects")}, ensure_ascii=False))
    assert report["passed"], [(item["case_id"], item.get("error")) for item in results if not item["passed"]]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
