import argparse
import os
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config

from .seed import ensure_seed


def main() -> None:
    parser = argparse.ArgumentParser(prog="sczx-business")
    parser.add_argument("action", choices=["migrate", "seed", "resources"])
    action = parser.parse_args().action
    database=urlparse(os.getenv("SCZX_DATABASE_URL","mysql+pymysql://root@127.0.0.1:23317/sczx")).path.lstrip("/")
    if os.getenv("SCZX_ENV")=="production" or not database.startswith("sczx_test_"):raise SystemExit("正式迁移/初始化须经deploy/manage.py预检和批准，不直接migrate head或seed。")
    if action == "migrate":
        command.upgrade(Config("alembic.ini"), "head")
    elif action == "seed":
        ensure_seed()
        print("初始化内容完成；已存在的内容未覆盖。")
    else:
        from sqlalchemy import select
        from .database import SessionLocal
        from .models import Account
        from .curated_resources import import_resources
        with SessionLocal.begin() as db:
            admin=db.scalar(select(Account).where(Account.role=='admin').order_by(Account.created_at).limit(1))
            if not admin:raise SystemExit('请先初始化管理员账号。')
            result=import_resources(db,admin.id,apply=True)
        print('教学方法摘要：新增'+str(len(result['created']))+'，待审核'+str(len(result['pending']))+'，保留已有'+str(len(result['skipped'])))


if __name__ == "__main__":
    main()
