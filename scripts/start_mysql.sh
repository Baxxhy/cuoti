#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# MySQL 8.0 的表空间发现会跳过隐藏目录（包括扫描起点）。
# 数据目录不可用点开头，否则正常重启也会找不到已有 UNDO 表空间。
DATA_DIR="$ROOT_DIR/mysql-data"
LEGACY_DATA_DIR="$ROOT_DIR/.mysql-data"
RUN_DIR="$ROOT_DIR/.mysql-run"
TMP_DIR="$ROOT_DIR/.mysql-tmp"
if mysqladmin --socket="$RUN_DIR/mysqld.sock" -uroot ping >/dev/null 2>&1; then
  echo "mysql=already_running"
  exit 0
fi
if [ -f "$RUN_DIR/mysqld.pid" ] && kill -0 "$(cat "$RUN_DIR/mysqld.pid")" 2>/dev/null; then
  echo "MySQL 进程仍在启动，但尚未通过健康检查；请检查数据目录中的 error.log。" >&2
  exit 1
fi
if [ ! -e "$DATA_DIR" ] && [ -d "$LEGACY_DATA_DIR/mysql" ]; then
  # 只在数据库停止时整体改名，保留所有表和日志，不删除 UNDO 文件。
  mv "$LEGACY_DATA_DIR" "$DATA_DIR"
  echo "mysql=data_directory_migrated mysql-data"
fi
mkdir -p "$DATA_DIR" "$RUN_DIR" "$TMP_DIR"
chown -R mysql:mysql "$DATA_DIR" "$RUN_DIR" "$TMP_DIR"
if [ ! -d "$DATA_DIR/mysql" ]; then
  runuser -u mysql -- sh -c "cd '$DATA_DIR' && exec mysqld --no-defaults --initialize-insecure --datadir='$DATA_DIR'"
fi
if ! runuser -u mysql -- sh -c "cd '$DATA_DIR' && exec mysqld --no-defaults --datadir='$DATA_DIR' --tmpdir='$TMP_DIR' --socket='$RUN_DIR/mysqld.sock' --pid-file='$RUN_DIR/mysqld.pid' --port=3307 --bind-address=127.0.0.1 --mysqlx=0 --log-error='$DATA_DIR/error.log' --daemonize"; then
  echo "MySQL 启动失败；原数据库已保留，请检查 $DATA_DIR/error.log。不要删除或重新初始化数据目录。" >&2
  exit 1
fi
for _ in $(seq 1 30); do
  mysqladmin --socket="$RUN_DIR/mysqld.sock" -uroot ping >/dev/null 2>&1 && break
  sleep 1
done
if ! mysqladmin --socket="$RUN_DIR/mysqld.sock" -uroot ping >/dev/null 2>&1; then
  echo "MySQL 尚未就绪；请检查 $DATA_DIR/error.log。" >&2
  exit 1
fi
mysql --socket="$RUN_DIR/mysqld.sock" -uroot -e "CREATE DATABASE IF NOT EXISTS minddimension CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER IF NOT EXISTS 'minddimension'@'localhost' IDENTIFIED WITH mysql_native_password BY 'minddimension'; GRANT ALL PRIVILEGES ON minddimension.* TO 'minddimension'@'localhost'; FLUSH PRIVILEGES;"
echo "mysql=ready port=3307"
