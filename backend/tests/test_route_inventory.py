"""The active student API contract excludes collaboration routes."""

import ast
import json
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_actual_python_routes_match_active_inventory():
    active = json.loads((ROOT / "docs/cangjie/routes.json").read_text())
    actual = set()
    for source in ("main.py", "learning_api.py"):
        tree = ast.parse((ROOT / "backend/app" / source).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if (
                    not isinstance(decorator, ast.Call)
                    or not isinstance(decorator.func, ast.Attribute)
                    or not decorator.args
                ):
                    continue
                if decorator.func.attr not in {"get", "post", "patch", "put", "delete"} or not isinstance(
                    decorator.args[0], ast.Constant
                ):
                    continue
                path = decorator.args[0].value
                if not path.startswith("/api/v1"):
                    path = "/api/v1" + path
                actual.add((decorator.func.attr.upper(), path))
    assert actual == {(row["method"], row["path"]) for row in active}
    retired = json.loads((ROOT / "docs/cangjie/routes_retired.json").read_text())
    assert not actual & {(row["method"], row["path"]) for row in retired}


@pytest.mark.asyncio
async def test_retired_routes_are_actually_unavailable():
    from app.main import app

    retired = json.loads((ROOT / "docs/cangjie/routes_retired.json").read_text())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for row in retired:
            path = row["path"].replace("{session_id}", "removed-test-session")
            response = await client.request(row["method"], path)
            assert response.status_code == 404, (row["method"], path, response.status_code)
