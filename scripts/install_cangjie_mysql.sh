#!/usr/bin/env bash
# Download and unpack client dependencies only; do not modify system packages.
set -euo pipefail
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
target="$project_dir/.runtime/mysql-client"
mkdir -p "$target/packages" "$target/root"
cd "$target/packages"
apt-get download libmysqlclient-dev libmysqlclient21 libssl-dev libssl1.1
for archive in ./*.deb; do dpkg-deb -x "$archive" "$target/root"; done
test -f "$target/root/usr/include/mysql/mysql.h"
echo 'MySQL C 客户端已解压到项目 .runtime/mysql-client，系统安装未改动'
