#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.auth import hash_password
from app.db import SessionLocal
from app.models import Base, StudentProfile, User


async def reset_student(email: str, password: str, name: str, grade: str) -> str:
    async with SessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing is not None:
            selected: dict[str, set[str]] = {"users": {existing.id}}
            changed = True
            while changed:
                changed = False
                for table in Base.metadata.sorted_tables:
                    if "id" not in table.c:
                        continue
                    for foreign_key in table.foreign_keys:
                        parent = foreign_key.column.table.name
                        if parent not in selected:
                            continue
                        values = set(await db.scalars(select(table.c.id).where(
                            foreign_key.parent.in_(selected[parent])
                        )))
                        before = len(selected.get(table.name, set()))
                        selected.setdefault(table.name, set()).update(values)
                        changed = changed or len(selected[table.name]) > before
            for table in reversed(Base.metadata.sorted_tables):
                ids = selected.get(table.name)
                if ids:
                    await db.execute(delete(table).where(table.c.id.in_(ids)))

        user = User(email=email, name=name, role="student", password_hash=hash_password(password))
        db.add(user)
        await db.flush()
        db.add(StudentProfile(user_id=user.id, grade=grade, learning_goal="建立自己的错题学习记录"))
        await db.commit()
        return user.id


async def main() -> None:
    parser = argparse.ArgumentParser(description="将本地学生账号重置为空白新用户")
    parser.add_argument("--email", default="1@1.com")
    parser.add_argument("--password", default="123")
    parser.add_argument("--name", default="小维")
    parser.add_argument("--grade", default="高一")
    args = parser.parse_args()
    user_id = await reset_student(args.email, args.password, args.name, args.grade)
    print(f"fresh_student={args.email} user_id={user_id} grade={args.grade}")


if __name__ == "__main__":
    asyncio.run(main())
