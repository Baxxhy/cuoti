"""Local launch environment: retain identities and data without a compiler."""

import fcntl
import os
import secrets
from pathlib import Path

from .config import Settings, configuration
from .protocol import ApiError


def environment():
    path, values = configuration()
    env = {key: str(value) for key, value in values.items() if value is not None}
    settings = Settings.load()
    settings.database_url()  # Require an explicit database; never initialize here.
    if (
        settings.db_password.get_secret_value()
        == "replace-with-your-local-database-password"
    ):
        raise ApiError(503, "请先填写本地数据库配置")
    root = Path(settings.project_root)
    for field, name in [
        ("auth_secret", "cuoti-auth-secret"),
        ("algorithm_secret", "cuoti-algorithm-secret"),
    ]:
        value = getattr(settings, field).get_secret_value()
        if not value:
            folder = root / ".runtime"
            folder.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(folder / name, os.O_RDWR | os.O_CREAT, 0o600)
            with os.fdopen(descriptor, "r+") as output:
                fcntl.flock(output, fcntl.LOCK_EX)
                value = output.read().strip()
                if not value:
                    value = secrets.token_hex(48)
                    output.write(value)
                    output.flush()
        if len(value) < 32:
            raise ApiError(503, "服务密钥长度不足，请检查本地配置")
        env["CUOTI_" + field.upper()] = value
    env["CUOTI_ENV_FILE"] = str(path)
    env["CUOTI_PORT"] = str(settings.port)
    env["CUOTI_MEDIA_ROOT"] = settings.media_root
    env.setdefault(
        "CUOTI_API_POOL_PATH",
        settings.api_pool_path or str(root / "config/api_pool.json"),
    )
    # The standalone launch owns task execution; explicit false still wins.
    env.setdefault("CUOTI_LEARNING_TASK_WORKER_ENABLED", "true")
    env["ZHIWEI_BACKEND_URL"] = f"http://127.0.0.1:{settings.port}"
    env.setdefault("ZHIWEI_FRONTEND_PORT", "5175")
    code = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(code / "backend-python"),
            str(code / "backend-algorithms"),
            env.get("PYTHONPATH", ""),
        ]
    )
    return env
