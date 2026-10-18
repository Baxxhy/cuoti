"""Prepare a fresh local Cangjie database/configuration without overwriting data."""

import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def main():
    config = PROJECT / ".env.cangjie"
    if config.exists() or config.is_symlink():
        raise RuntimeError(
            "已有 .env.cangjie，未修改；请使用 make dev-final 启动或检查现有配置"
        )
    database = "zhiwei_cangjie_local"
    user = "zhiwei_cj_local"
    socket_path = os.environ.get(
        "CANGJIE_TEST_MYSQL_SOCKET", str(PROJECT / ".mysql-run/mysqld.sock")
    )
    port = os.environ.get("CANGJIE_TEST_MYSQL_PORT", "3307")
    if not re.fullmatch(r"[0-9]+", port):
        raise RuntimeError("本地 MySQL 端口格式不正确")
    admin = ["mysql", "--no-defaults", "--socket=" + socket_path, "-uroot", "-NBe"]

    def sql(statement):
        result = subprocess.run(
            [*admin, statement], capture_output=True, text=True, check=False
        )
        if result.returncode:
            raise RuntimeError("本地 MySQL 管理连接或新库准备失败，未输出连接凭据")
        return result.stdout.strip()

    if (
        sql(
            f"SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='{database}'"
        )
        != "0"
    ):
        raise RuntimeError("计划使用的独立库已存在，拒绝覆盖；请手工配置 .env.cangjie")
    if sql(f"SELECT COUNT(*) FROM mysql.user WHERE user='{user}'") != "0":
        raise RuntimeError("计划使用的独立数据库账号已存在，拒绝重置密码")

    def free_port(preferred):
        for candidate in range(preferred, preferred + 30):
            with socket.socket() as listener:
                try:
                    listener.bind(("127.0.0.1", candidate))
                    return str(candidate)
                except OSError:
                    continue
        raise RuntimeError("本地服务端口不可用")

    password = secrets.token_hex(32)
    settings = {
        "CANGJIE_DB_HOST": "127.0.0.1",
        "CANGJIE_DB_PORT": port,
        "CANGJIE_DB_NAME": database,
        "CANGJIE_DB_USER": user,
        "CANGJIE_DB_PASSWORD": password,
        "CANGJIE_BACKEND_PORT": free_port(8002),
        "CANGJIE_ALGORITHM_PORT": free_port(8012),
        "ZHIWEI_FRONTEND_PORT": free_port(5174),
        "CANGJIE_API_POOL_PATH": str(PROJECT / "backend/config/api_pool.json"),
        "CANGJIE_QDRANT_COLLECTION": database + "_questions_v1",
    }
    # Fresh names only. Password travels through stdin, never process arguments.
    statement = f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER '{user}'@'localhost' IDENTIFIED WITH mysql_native_password BY '{password}'; GRANT ALL PRIVILEGES ON `{database}`.* TO '{user}'@'localhost';"
    made = subprocess.run(
        ["mysql", "--no-defaults", "--socket=" + socket_path, "-uroot"],
        input=statement,
        text=True,
        capture_output=True,
        check=False,
    )
    if made.returncode:
        raise RuntimeError("新库准备未完成，请检查本地 MySQL；不会删除或重置已有资源")
    descriptor = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(
            "# Local configuration, generated once; never commit credentials.\n"
        )
        for key, value in settings.items():
            output.write(f"{key}={shlex.quote(value)}\n")
    env = {**os.environ, **settings}
    for action in ("init-db", "seed-knowledge"):
        result = subprocess.run(
            ["bash", "scripts/cangjie.sh", action],
            cwd=PROJECT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(
                "独立库初始化或知识准备未完成，配置已保留；请检查仓颉环境，不要重复初始化非空库"
            )
    print("本地独立库、知识卡和私有配置已准备，未导入演示学生或成绩。")
    print(
        "运行 make dev-final；前端 http://127.0.0.1:" + settings["ZHIWEI_FRONTEND_PORT"]
    )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError):
        error = sys.exc_info()[1]
        print(
            str(error)
            if isinstance(error, RuntimeError)
            else "本地初始化环境不可用，请检查配置权限",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
