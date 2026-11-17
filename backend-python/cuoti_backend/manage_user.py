"""Local administrator creation, with no public role-escalation endpoint."""

import argparse
import getpass
import json
import sys
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .account_schemas import email_field, text_field
from .accounts import duplicate_email
from .config import Settings
from .database import Database
from .models import User
from .protocol import ApiError
from .security import hash_password


def create_admin(db, settings, body):
    email = email_field(body)
    name = text_field(body, "name", 100)
    check = body.get("check_only", False)
    if type(check) is not bool:
        raise ApiError(422, "check_only 必须是布尔值")
    if not settings.db_name:
        raise ApiError(422, "请显式设置数据库名称")
    password_hash = ""
    if not check:
        password = text_field(body, "password", 256, trim=False)
        if len(password) < 12 or "\n" in password or "\r" in password:
            raise ApiError(422, "角色账号密码至少12个字符")
        password_hash = hash_password(password)
    try:
        with db.begin():
            version = db.execute(
                text(
                    "SELECT version FROM cangjie_schema_versions WHERE version='009_task_sources'"
                )
            ).scalar_one_or_none()
            if version is None:
                raise ApiError(409, "请先完成数据库升级，命令不会自动初始化或升级")
            result = {"database": settings.db_name, "email": email, "role": "admin"}
            if check:
                user = db.scalar(select(User).where(User.email == email))
                result.update(available=user is None, created=False)
                if user is not None:
                    result["existing_role"] = user.role
            else:
                user = User(
                    id=str(uuid4()),
                    email=email,
                    name=name,
                    role="admin",
                    password_hash=password_hash,
                )
                db.add(user)
                db.flush()
                result.update(id=user.id, created=True)
        return result
    except IntegrityError as error:
        duplicate_email(
            error, "邮箱已存在；未修改身份、密码或学习记录，请使用专用的新邮箱"
        )


def main():
    parser = argparse.ArgumentParser(
        description="创建专用本地管理员账号，不修改已有账号"
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="管理员")
    parser.add_argument("--role", choices=["admin"], default="admin")
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="从标准输入读取密码；不要将密码放入命令参数",
    )
    args = parser.parse_args()
    if args.check and args.password_stdin:
        parser.error("--check 不需要密码，不能与 --password-stdin 同用")
    settings = Settings.load()
    database = Database(settings)
    try:
        body = {"email": args.email, "name": args.name, "check_only": True}
        with database.session() as db:
            checked = create_admin(db, settings, body)
        if args.check:
            print(json.dumps(checked, ensure_ascii=False))
            return
        if not checked["available"]:
            raise ApiError(
                409, "邮箱已存在；未修改身份、密码或学习记录，请使用专用的新邮箱"
            )
        if args.password_stdin:
            password = sys.stdin.readline(1025).removesuffix("\n").removesuffix("\r")
        else:
            if not sys.stdin.isatty():
                raise ApiError(
                    422, "非交互执行请使用 --password-stdin；密码不要放入命令参数"
                )
            password = getpass.getpass("管理员密码（至少12个字符）：")
            if getpass.getpass("再次输入密码：") != password:
                raise ApiError(422, "两次密码不一致")
        body.update(check_only=False, password=password)
        with database.session() as db:
            print(json.dumps(create_admin(db, settings, body), ensure_ascii=False))
    except (ApiError, SQLAlchemyError) as error:
        message = (
            error.message
            if isinstance(error, ApiError)
            else "账号未创建，请检查数据库配置"
        )
        print(json.dumps({"message": message}, ensure_ascii=False))
        raise SystemExit(1) from None
    finally:
        database.close()


if __name__ == "__main__":
    main()
