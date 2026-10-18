#!/usr/bin/env python3
"""将项目 API 池副本中的模型字段精确迁移为 Qwen。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MODEL_FIELDS = {"model", "model_name", "default_model", "primary_model", "chat_model", "vision_model"}


def migrate(value: object, source: str, target: str) -> int:
    changed = 0
    if isinstance(value, dict):
        for key, item in value.items():
            if key in MODEL_FIELDS and isinstance(item, str) and item.casefold() == source.casefold():
                value[key] = target
                changed += 1
            else:
                changed += migrate(item, source, target)
    elif isinstance(value, list):
        for item in value:
            changed += migrate(item, source, target)
    return changed


def normalize_all_models(value: object, target: str) -> int:
    """Force every recognized model field to the one allowed logical model."""
    changed = 0
    if isinstance(value, dict):
        for key, item in value.items():
            if key in MODEL_FIELDS and isinstance(item, str):
                if item != target:
                    value[key] = target
                    changed += 1
            else:
                changed += normalize_all_models(item, target)
    elif isinstance(value, list):
        for item in value:
            changed += normalize_all_models(item, target)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="backend/config/api_pool.json")
    parser.add_argument("--from-model", default="Qwen3.6-35B-A3B")
    parser.add_argument("--to-model", default="Qwen")
    parser.add_argument("--all-models", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    path = Path(args.path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    count = normalize_all_models(payload, args.to_model) if args.all_models else migrate(payload, args.from_model, args.to_model)
    if not args.dry_run:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"changed_model_fields={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
