"""Read-only checks for the unified backend; never probe a paid model."""

import json
import sys
from urllib.request import ProxyHandler, build_opener

from cuoti_backend.config import Settings, configuration


def check_services() -> bool:
    backend = f"http://127.0.0.1:{Settings.load().port}"
    _, values = configuration()
    frontend = f"http://127.0.0.1:{values.get('ZHIWEI_FRONTEND_PORT', '5175')}"
    checks = [
        ("Python 统一后端", backend + "/livez", "service", "cuoti-python"),
        ("MySQL 与历史表结构", backend + "/readyz", "status", "database_ready"),
        ("前端", frontend, None, None),
    ]
    good = True
    opener = build_opener(ProxyHandler({}))
    for label, url, key, expected in checks:
        try:
            with opener.open(url, timeout=3) as response:
                if key:
                    payload = json.load(response)
                    if not isinstance(payload, dict) or payload.get(key) != expected:
                        raise ValueError("unexpected service")
            print(f"通过：{label}")
        except (OSError, ValueError):
            print(f"未就绪：{label}，请检查本地配置与服务日志", file=sys.stderr)
            good = False
    return good


if __name__ == "__main__":
    raise SystemExit(0 if check_services() else 1)
