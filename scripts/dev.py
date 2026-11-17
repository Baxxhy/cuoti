"""Small foreground supervisor; stop only the process groups launched here."""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from cuoti_backend.config import Settings, configuration
from cuoti_backend.database import Database
from cuoti_backend.protocol import ApiError
from cuoti_backend.runtime import environment
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]


def available(env, frontend):
    ports = [int(env["CUOTI_PORT"])]
    if frontend:
        ports.append(int(env["ZHIWEI_FRONTEND_PORT"]))
    if len(set(ports)) != len(ports):
        raise RuntimeError("前后端端口不能相同")
    for port in ports:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise RuntimeError(
                    f"端口 {port} 已被占用，请调整端口；不会停止已有服务"
                ) from None


def supervise(commands, env):
    children = []
    previous = {}

    def interrupted(signum, _):
        raise KeyboardInterrupt

    try:
        for signum in [signal.SIGINT, signal.SIGTERM]:
            previous[signum] = signal.signal(signum, interrupted)
        for command in commands:
            children.append(
                subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True)
            )
        while True:
            for child in children:
                if child.poll() is not None:
                    return child.returncode or 1
            time.sleep(0.2)
    except KeyboardInterrupt:
        return 0
    finally:
        for child in reversed(children):
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for child in reversed(children):
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser(
        description="启动统一 Python 后端及前端；不初始化数据库"
    )
    parser.add_argument(
        "action", choices=["start", "check", "backend"], default="start", nargs="?"
    )
    args = parser.parse_args()
    if args.action == "check":
        from health import check_services

        _, values = configuration()
        os.environ.update(
            {key: str(value) for key, value in values.items() if value is not None}
        )
        return 0 if check_services() else 1
    env = environment()
    available(env, args.action == "start")
    # Check the selected database before any worker starts. No writes or AI probes.
    database = Database(Settings.load())
    try:
        database.probe()
    finally:
        database.close()
    command = [sys.executable, "-m", "cuoti_backend"]
    if args.action == "backend":
        os.execve(sys.executable, command, env)
    commands = [
        command,
        [
            "npm",
            "--prefix",
            "frontend",
            "run",
            "dev:h5",
            "--",
            "--port",
            env["ZHIWEI_FRONTEND_PORT"],
            "--strictPort",
        ],
    ]
    print(
        f"启动 Python 后端和前端；页面 http://127.0.0.1:{env['ZHIWEI_FRONTEND_PORT']}，Ctrl+C 停止本次服务。",
        flush=True,
    )
    return supervise(commands, env)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ApiError, OSError, ValueError, RuntimeError, SQLAlchemyError) as error:
        message = (
            error.message
            if isinstance(error, ApiError)
            else str(error)
            if type(error) is RuntimeError
            else "启动失败，请检查数据库、端口和本地配置；未输出凭据"
        )
        print(message, file=sys.stderr)
        raise SystemExit(1) from None
