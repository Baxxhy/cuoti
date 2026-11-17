"""Explicit local database maintenance. Application startup never changes schema."""

import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from . import schema
from .config import Settings
from .database import Database
from .protocol import ApiError


def backup(settings):
    folder = Path(settings.project_root) / ".runtime/backups"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = folder / f"mysql-{stamp}-{uuid4().hex[:8]}.sql"
    partial = target.with_suffix(".sql.partial")

    def quoted(value):
        return (
            '"'
            + str(value)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            + '"'
        )

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", prefix="cuoti-mysql-", suffix=".cnf"
        ) as config:
            config.write(
                "[client]\n"
                + "\n".join(
                    key + "=" + quoted(value)
                    for key, value in {
                        "host": settings.db_host,
                        "port": settings.db_port,
                        "user": settings.db_user,
                        "password": settings.db_password.get_secret_value(),
                        "default-character-set": "utf8mb4",
                    }.items()
                )
            )
            config.flush()
            descriptor = os.open(partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                done = subprocess.run(
                    [
                        "mysqldump",
                        "--defaults-extra-file=" + config.name,
                        "--single-transaction",
                        "--no-tablespaces",
                        "--routines",
                        "--triggers",
                        "--set-gtid-purged=OFF",
                        "--column-statistics=0",
                        "--databases",
                        settings.db_name,
                    ],
                    stdout=output,
                    stderr=subprocess.PIPE,
                    timeout=600,
                    check=False,
                )
            if done.returncode or not partial.stat().st_size:
                raise ApiError(503, "数据库备份失败；未执行维护，不输出连接凭据")
        partial.rename(target)
        return str(target)
    except (OSError, subprocess.SubprocessError):
        raise ApiError(503, "数据库备份工具不可用；未执行维护") from None
    finally:
        partial.unlink(missing_ok=True)


def maintain(database, settings, operation):
    if database.engine is None:
        raise ApiError(503, "尚未配置 MySQL 数据库")
    if operation == "backup":
        return {"backup": backup(settings)}
    with database.engine.connect() as connection:
        if operation == "init":
            schema.initialize(connection)
            return {"initialized": True, "versions": sorted(schema.applied(connection))}
        versions = schema.applied(connection)
        missing = schema.VERSIONS - versions
        if operation == "status":
            return {"versions": sorted(versions), "missing": sorted(missing)}
        if operation == "upgrade" and not missing:
            return {"upgraded": False, "versions": sorted(versions)}
        if "001_initial" not in versions:
            raise ApiError(409, "缺少历史初始版本，不能维护")
        saved = backup(settings)
        if operation == "upgrade":
            schema.upgrade(connection)
        elif operation == "seed-knowledge":
            connection.rollback()
            with connection.begin():
                schema.seed(connection)
        else:
            raise ApiError(422, "未知数据库维护命令")
        return {"completed": operation, "backup": saved}


def main():
    parser = argparse.ArgumentParser(
        description="Python 后端数据库维护；已有数据修改前自动备份"
    )
    parser.add_argument(
        "operation", choices=["init", "upgrade", "status", "backup", "seed-knowledge"]
    )
    args = parser.parse_args()
    settings = Settings.load()
    database = Database(settings)
    try:
        print(
            json.dumps(maintain(database, settings, args.operation), ensure_ascii=False)
        )
    except (ApiError, SQLAlchemyError) as error:
        print(
            json.dumps(
                {
                    "code": error.status if isinstance(error, ApiError) else 503,
                    "message": error.message
                    if isinstance(error, ApiError)
                    else "数据库维护失败，请检查配置和版本；不会自动清空数据库",
                },
                ensure_ascii=False,
            )
        )
        raise SystemExit(1) from None
    finally:
        database.close()


if __name__ == "__main__":
    main()
