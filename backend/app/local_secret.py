"""Persist a local signing secret outside source control, safely across workers."""

from __future__ import annotations

import fcntl
import os
import secrets
from pathlib import Path


def load_local_secret(path: Path = Path(".runtime/auth-secret")) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, "r+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        value = stream.read().strip()
        if not value:
            value = secrets.token_urlsafe(48)
            stream.seek(0)
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if len(value) < 32:
            raise RuntimeError("本地会话密钥文件不完整，请配置 AUTH_SECRET 或检查 .runtime/auth-secret")
        return value
