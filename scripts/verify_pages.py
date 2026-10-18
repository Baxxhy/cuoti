#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(ROOT / "frontend/.playwright-libs/root/usr/lib/x86_64-linux-gnu")
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / "frontend/.playwright-browsers")
    subprocess.run(["pnpm", "--dir", "frontend", "run", "test:e2e", "--", "--grep", "全部功能页"],
                   cwd=ROOT, env=env, check=True)
    print("学生端页面三档手机视口验收通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
