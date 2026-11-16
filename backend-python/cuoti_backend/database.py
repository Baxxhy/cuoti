from contextlib import contextmanager

from fastapi import Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .config import Settings


class Database:
    """One engine per app, with a separate session for each unit of work."""

    def __init__(self, settings: Settings):
        self.engine = None
        self.sessions = None
        if settings.db_name and settings.db_user:
            self.engine = create_engine(
                settings.database_url(),
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                connect_args={
                    "connect_timeout": settings.db_timeout,
                    "read_timeout": settings.db_timeout,
                    "write_timeout": settings.db_timeout,
                },
            )
            self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self):
        if self.sessions is None:
            from .protocol import ApiError

            raise ApiError(503, "尚未配置 MySQL 数据库")
        # No implicit commit. Future business services own write transactions.
        with self.sessions() as session:
            yield session

    def probe(self):
        with self.session() as session:
            session.execute(text("SELECT 1")).scalar_one()

    def close(self):
        if self.engine is not None:
            self.engine.dispose()


def get_session(request: Request):
    with request.app.state.database.session() as session:
        yield session
