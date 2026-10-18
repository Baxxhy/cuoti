#!/usr/bin/env python3
"""Create real accounts without invoking destructive demo initialization."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import SessionLocal
from app.services.account_setup import ROLES, create_account, link_guardian


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="创建真实用户或建立家长关系；不覆盖已有账号"
    )
    commands = root.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="创建独立账号，不导入演示数据")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--role", choices=ROLES, required=True)
    create.add_argument("--grade", default="初二")
    create.add_argument(
        "--password-stdin",
        action="store_true",
        help="从标准输入读取一行密码，不放到命令参数",
    )
    link = commands.add_parser("link-guardian", help="将已有家长账号关联到已有学生")
    link.add_argument("--guardian-email", required=True)
    link.add_argument("--student-email", required=True)
    return root


async def execute(args: argparse.Namespace) -> None:
    async with SessionLocal() as db:
        if args.command == "create":
            password = (
                sys.stdin.readline().rstrip("\r\n")
                if args.password_stdin
                else getpass.getpass("账号密码（至少 8 个字符，不显示）：")
            )
            if not args.password_stdin and password != getpass.getpass(
                "再次输入密码："
            ):
                raise ValueError("两次密码不一致")
            user = await create_account(
                db,
                email=args.email,
                name=args.name,
                role=args.role,
                password=password,
                grade=args.grade,
            )
            print(f"账号已创建：{user.email}，身份：{user.role}")
        else:
            created = await link_guardian(
                db, guardian_email=args.guardian_email, student_email=args.student_email
            )
            print("家长关系已建立" if created else "家长关系已存在，未重复添加")


def main() -> int:
    try:
        asyncio.run(execute(parser().parse_args()))
    except ValidationError:
        print("账号字段无效，请检查邮箱、姓名、年级和密码长度。", file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except IntegrityError:
        print("账号或关系已被其他操作创建，请核对后重试。", file=sys.stderr)
        return 1
    except (SQLAlchemyError, OSError):
        # Driver exceptions may contain database credentials or statement values.
        print("无法完成账号操作，请检查 MySQL 连接和迁移状态。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
