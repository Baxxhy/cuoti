import argparse
import os
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config

from .seed import ensure_seed


def main() -> None:
    parser = argparse.ArgumentParser(prog="sczx-business")
    parser.add_argument("action", choices=["migrate", "seed"])
    action = parser.parse_args().action
    database=urlparse(os.getenv("SCZX_DATABASE_URL","mysql+pymysql://root@127.0.0.1:23317/sczx")).path.lstrip("/")
    if os.getenv("SCZX_ENV")=="production" or not database.startswith("sczx_test_"):raise SystemExit("正式迁移/初始化须经deploy/manage.py预检和批准，不直接migrate head或seed。")
    if action == "migrate":
        command.upgrade(Config("alembic.ini"), "head")
    else:
        ensure_seed()
        print("初始化内容完成；已存在的内容未覆盖。")


if __name__ == "__main__":
    main()
