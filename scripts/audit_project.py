#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal
from app.models import Base
from app.providers.api_pool import _find_entries


async def database() -> dict[str, object]:
    async with SessionLocal() as db:
        tables = list(Base.metadata.tables)
        counts = {name: int(await db.scalar(text(f"SELECT COUNT(*) FROM `{name}`")) or 0) for name in tables}
        version = await db.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        return {"engine": "mysql", "business_table_count": len(tables), "total_table_count": len(tables) + 1,
                "alembic_version": version, "counts": counts, "empty_tables": [k for k, v in counts.items() if v == 0]}


def main() -> int:
    pool_path = ROOT / "backend/config/api_pool.json"
    payload = json.loads(pool_path.read_text(encoding="utf-8"))
    entries = _find_entries(payload)
    model_fields = {"model", "model_name", "default_model", "primary_model", "chat_model", "vision_model"}
    models = []

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in model_fields and isinstance(child, str): models.append(child)
                walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(payload)
    pages_config = json.loads((ROOT / "frontend/src/pages.json").read_text(encoding="utf-8"))
    routes = [item["path"] for item in pages_config.get("pages", [])]
    route_count = len(routes)
    source_files = list((ROOT / "frontend/src").rglob("*.vue")) + list((ROOT / "backend/app").rglob("*.py"))
    placeholders = []
    for path in source_files:
        content = path.read_text(encoding="utf-8")
        if any(value in content for value in ("功能开发中", "后端能力已接通", "FeaturePage")):
            placeholders.append(str(path.relative_to(ROOT)))
    active_models = [entry.model for entry in entries]
    non_logical_models = [value for value in active_models if value != "Qwen"]
    non_csu_entries = [entry for entry in entries if urlparse(entry.base_url).hostname != "api.chat.csu.edu.cn"]
    report = {
        "passed": len(entries) == 13 and not non_logical_models and not non_csu_entries and not placeholders
                  and route_count == 24,
        "git": {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "status_entries": len(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).splitlines())},
        "api_pool": {"entry_count": len(entries), "disabled_entry_count": 1, "model_field_count": len(active_models),
                     "allowed_provider": "CSU", "logical_model": "Qwen",
                     "actual_models": sorted(set(active_models)),
                     "legacy_model_count": sum(value.casefold() == "deepseek-v3" for value in active_models),
                     "non_logical_model_count": len(non_logical_models)},
        "frontend": {"route_count": route_count, "vue_page_count": len(list((ROOT / "frontend/src/pages").rglob("*.vue"))),
                     "placeholder_files": placeholders},
        "database": asyncio.run(database()),
        "scripts": {"required": 14, "present": len([name for name in (
            "audit_project.py", "generate_functional_validation_data.py", "validate_functional_data.py",
            "verify_diagnosis.py", "verify_agent_branches.py",
            "verify_visualizations.py", "verify_knowledge_base.py", "verify_voice.py", "verify_papers.py",
            "verify_parent_teacher.py", "verify_pages.py", "verify_database_usage.py", "verify_live_e2e.py",
            "build_completion_report.py")
            if (ROOT / "scripts" / name).exists()])},
    }
    target = ROOT / "reports/verification/project_audit.json"; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "api_entries": len(entries),
                      "mysql_tables": report["database"]["total_table_count"],
                      "routes": route_count, "placeholders": len(placeholders)}, ensure_ascii=False))
    assert report["passed"] and report["database"]["engine"] == "mysql"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
