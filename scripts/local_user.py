"""Collect a local operator's input; Cangjie owns validation, hashing and writes."""

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROLES = {"admin": "管理员"}


def native(payload):
    result = subprocess.run(
        ["bash", str(PROJECT / "scripts/cangjie.sh"), "create-user-built"],
        cwd=PROJECT,
        input=json.dumps(payload, ensure_ascii=False) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        body = json.loads(result.stdout)
        if not isinstance(body, dict):
            raise TypeError
    except (ValueError, TypeError):
        raise RuntimeError("仓颉账号命令未返回有效结果，请检查本地运行环境") from None
    if result.returncode:
        # Only known native error codes carry curated, non-secret messages.
        if body.get("code") in (409, 422, 503) and isinstance(body.get("message"), str):
            raise RuntimeError(body["message"])
        raise RuntimeError("账号未创建，请检查独立数据库与当前版本")
    return body


def main():
    parser = argparse.ArgumentParser(
        description="创建专用本地管理员账号，不更改已有账号"
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=ROLES)
    parser.add_argument("--name", help="账号显示姓名，默认使用角色名称")
    parser.add_argument(
        "--check", action="store_true", help="只检查数据库和邮箱，不输入密码、不写库"
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="从标准输入读取一行密码，供本地自动化使用",
    )
    args = parser.parse_args()
    if not os.environ.get("CANGJIE_DB_NAME"):
        parser.error("请先在本地 .env.cangjie 或环境变量中显式配置独立数据库")
    if args.check and args.password_stdin:
        parser.error("--check 不需要密码，不能与 --password-stdin 同用")
    # Build before collecting secrets; compiler output is never mixed with stdin.
    built = subprocess.run(
        ["bash", str(PROJECT / "scripts/cangjie.sh"), "build"],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=False,
    )
    if built.returncode:
        raise RuntimeError(
            "仓颉构建失败；请单独运行 bash scripts/cangjie.sh build 检查环境"
        )
    payload = {
        "email": args.email,
        "role": args.role,
        "name": args.name or ROLES[args.role],
    }
    checked = native({**payload, "check_only": True})
    if args.check:
        print(json.dumps(checked, ensure_ascii=False))
        return
    if not checked.get("available"):
        raise RuntimeError("邮箱已存在；未修改身份、密码或学习记录，请使用专用的新邮箱")
    if args.password_stdin:
        password = sys.stdin.readline(1025).removesuffix("\n").removesuffix("\r")
    else:
        if not sys.stdin.isatty():
            raise RuntimeError(
                "非交互执行请显式使用 --password-stdin；密码不要放入命令参数或环境变量"
            )
        print(
            f"目标数据库：{checked['database']}；账号：{checked['email']}；身份：{ROLES[args.role]}",
            file=sys.stderr,
        )
        password = getpass.getpass("设置密码（至少12个字符）：")
        if password != getpass.getpass("再次输入密码："):
            raise RuntimeError("两次密码不同，未创建账号")
    if not 12 <= len(password) <= 256 or "\n" in password or "\r" in password:
        raise RuntimeError("密码须为12—256个字符的单行文字，未创建账号")
    print(json.dumps(native({**payload, "password": password}), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError):
        # RuntimeError messages are authored here or in the native command.
        message = sys.exc_info()[1]
        print(
            str(message)
            if isinstance(message, RuntimeError)
            else "本地账号命令无法执行，请检查运行环境",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except (KeyboardInterrupt, EOFError):
        print("操作已中断；请用 --check 核对账号是否已创建", file=sys.stderr)
        raise SystemExit(1) from None
