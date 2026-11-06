"""Request-scoped MySQL connections, matching the original SQL transaction policy."""
from __future__ import annotations

import datetime as dt
import os
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal

import pymysql


@dataclass
class QueryResult:
    rows: list[dict[str, str | None]]
    affected: int


def bind_sql(sql: str) -> str:
    """Convert original question-mark parameters without touching quoted literals."""
    result = []
    quote = None
    escaped = False
    for char in sql:
        if escaped:
            result.append(char if char != '%' else '%%')
            escaped = False
        elif char == '\\' and quote:
            result.append(char)
            escaped = True
        elif quote:
            result.append(char if char != '%' else '%%')
            if char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
            result.append(char)
        elif char == '?':
            result.append('%s')
        else:
            result.append(char if char != '%' else '%%')
    return ''.join(result)


def row_value(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode('utf-8')
    if isinstance(value, dt.datetime):
        return str(value)
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


class Database:
    def __init__(self, connection):
        self.connection = connection
        self.in_transaction = False

    @classmethod
    def from_environment(cls):
        name = os.environ.get('SCZX_DB_NAME', 'sczx_local')
        if not name.startswith('sczx_'):
            raise ValueError('迁移版只连接 sczx_ 前缀的独立MySQL数据库')
        options = dict(host=os.environ.get('SCZX_DB_HOST', '127.0.0.1'),
                       port=int(os.environ.get('SCZX_DB_PORT', '3307')),
                       user=os.environ.get('SCZX_DB_USER', 'sczx'),
                       password=os.environ.get('SCZX_DB_PASSWORD', ''),
                       database=name, charset='utf8mb4', autocommit=True,
                       connect_timeout=5, read_timeout=30, write_timeout=30)
        if os.environ.get('SCZX_DB_SOCKET'):
            options['unix_socket'] = os.environ['SCZX_DB_SOCKET']
        return cls(pymysql.connect(**options))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def query(self, sql: str, params=()) -> QueryResult:
        with self.connection.cursor() as cursor:
            if params:
                cursor.execute(bind_sql(sql), tuple(params))
            else:
                cursor.execute(sql)
            names = [item[0] for item in cursor.description] if cursor.description else []
            rows = [{name: row_value(value) for name, value in zip(names, row)}
                    for row in cursor.fetchall()] if names else []
            return QueryResult(rows, cursor.rowcount)

    @contextmanager
    def transaction(self):
        if self.in_transaction:
            raise ValueError('不支持嵌套事务')
        self.connection.begin()
        self.in_transaction = True
        try:
            yield self
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise
        finally:
            self.in_transaction = False
