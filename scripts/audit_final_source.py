"""Verify that the final algorithm runtime has no legacy business dependency."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGORITHMS = ROOT / "backend-algorithms"


def audit():
    assert not (ROOT / "backend").exists(), "旧Python业务后端不得恢复"
    modules = {
        ".".join(path.relative_to(ALGORITHMS).with_suffix("").parts).removesuffix(".__init__"): path
        for path in ALGORITHMS.rglob("*.py")
        if "tests" not in path.parts and "__pycache__" not in path.parts
    }

    def imports(path):
        found = set()
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [name.name for name in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module, *(node.module + "." + item.name for item in node.names)]
            for name in names:
                assert name.split(".")[0] not in {"app", "sqlalchemy", "asyncmy", "alembic"}, (path, name)
                if name in modules:
                    found.add(name)
        return found

    pending = ["service"]
    for script in (ROOT / "scripts").glob("*.py"):
        pending.extend(imports(script))
    reached = set()
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        reached.add(name)
        if name in modules:
            pending.extend(imports(modules[name]) - reached)
    unused = sorted(name for name, path in modules.items() if name not in reached and path.name != "__init__.py")
    assert not unused, ("算法模块缺少实际入口引用", unused)
    print(json.dumps({"runtime_modules": len(modules), "unreachable_modules": 0, "legacy_backend": False}))


if __name__ == "__main__":
    audit()
