"""Shared, read-only format audit using the actual frontend formula renderer."""

import json
import subprocess
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def audit_formats(rows: list[dict]) -> dict:
    if not rows:
        return {"questions": 0, "fields": 0, "formulas": 0, "findings": []}
    with tempfile.TemporaryDirectory(prefix="zhiwei-formats-") as folder:
        source = Path(folder) / "questions.jsonl"
        report = Path(folder) / "report.json"
        source.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        done = subprocess.run(
            ["node", "frontend/scripts/audit-formulas.mjs", str(source), str(report)],
            cwd=PROJECT,
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode not in (0, 1) or not report.is_file():
            raise RuntimeError("题库公式审计未完成；未修改数据，请检查前端依赖和审计脚本")
        result = json.loads(report.read_text(encoding="utf-8"))
        if bool(result["findings"]) != bool(done.returncode):
            raise RuntimeError("公式审计结果不一致；未修改数据")
        return result


def format_reviews(report: dict) -> list[dict]:
    grouped: dict[str, dict] = {}
    for finding in report["findings"]:
        row = grouped.setdefault(
            finding["id"],
            {"id": finding["id"], "content_hash": finding["content_hash"], "fields": []},
        )
        row["fields"].append(finding["field"])
    return list(grouped.values())
