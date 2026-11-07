import argparse

from alembic import command
from alembic.config import Config

from .seed import ensure_seed


def main() -> None:
    parser = argparse.ArgumentParser(prog="sczx-business")
    parser.add_argument("action", choices=["migrate", "seed"])
    action = parser.parse_args().action
    if action == "migrate":
        command.upgrade(Config("alembic.ini"), "head")
    else:
        ensure_seed()
        print("初始化内容完成；已存在的内容未覆盖。")


if __name__ == "__main__":
    main()
