"""Compatibility entry point for the unified backend administrator command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend-python"))
from cuoti_backend.manage_user import main

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("操作已中断；请用 --check 核对账号是否已创建", file=sys.stderr)
        raise SystemExit(1) from None
