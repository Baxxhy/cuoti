"""Read-only checks for the final architecture; never probe a paid model."""

from __future__ import annotations

import json
import os
import sys
from urllib.request import urlopen


def check_services() -> bool:
    backend = f"http://127.0.0.1:{os.getenv('CANGJIE_BACKEND_PORT', '8002')}"
    algorithms = f"http://127.0.0.1:{os.getenv('CANGJIE_ALGORITHM_PORT', '8012')}"
    frontend = f"http://127.0.0.1:{os.getenv('ZHIWEI_FRONTEND_PORT', '5175')}"
    checks = [
        ("仓颉业务服务", backend + "/livez", "service", "zhiwei-cangjie"),
        ("仓颉 MySQL/表版本", backend + "/readyz", "status", "database_ready"),
        ("Python 算法服务", algorithms + "/livez", "service", "zhiwei-algorithms"),
        ("前端", frontend, None, None),
    ]
    good = True
    for label, url, key, expected in checks:
        try:
            with urlopen(url, timeout=3) as response:
                if key:
                    payload = json.load(response)
                    if not isinstance(payload, dict) or payload.get(key) != expected:
                        raise ValueError("unexpected service")
            print(f"通过：{label}")
        except (OSError, ValueError):
            # Do not print response bodies, connection strings or environment values.
            print(f"未就绪：{label}，请检查本地配置与服务日志", file=sys.stderr)
            good = False
    return good


if __name__ == "__main__":
    raise SystemExit(0 if check_services() else 1)
