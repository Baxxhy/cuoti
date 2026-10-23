#!/usr/bin/env bash
set -eo pipefail
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
sdk_dir=${CANGJIE_SDK_DIR:-$project_dir/.runtime/cangjie/cangjie}
if [[ ! -f "$sdk_dir/envsetup.sh" ]]; then
  echo '缺少仓颉 SDK；请先运行 bash scripts/install_cangjie.sh' >&2
  exit 1
fi
source "$sdk_dir/envsetup.sh"
export CANGJIE_STDX_PATH=${CANGJIE_STDX_PATH:-$project_dir/.runtime/cangjie/linux_x86_64_cjnative/dynamic/stdx}
export CANGJIE_MYSQL_NATIVE="$project_dir/.runtime/mysql-client"
mysql_root=${CANGJIE_MYSQL_CLIENT_ROOT:-$CANGJIE_MYSQL_NATIVE/root/usr}
if [[ ! -f "$mysql_root/include/mysql/mysql.h" || ! -f "$mysql_root/include/openssl/evp.h" ]]; then
  echo '缺少 MySQL/OpenSSL 开发文件；请运行 bash scripts/install_cangjie_mysql.sh' >&2
  exit 1
fi
mkdir -p "$CANGJIE_MYSQL_NATIVE"
# Bulk import launches many short-lived commands; reuse the already-built
# native bridge unless its sources changed. Other build/run modes still rebuild.
bridge="$CANGJIE_MYSQL_NATIVE/libzhiwei_mysql.so"
if [[ ${1:-build} != question-bank-built || ! -f "$bridge" ||
      "$project_dir/backend-cangjie/native/mysql_bridge.c" -nt "$bridge" ||
      "$project_dir/backend-cangjie/native/crypto_bridge.c" -nt "$bridge" ||
      "$project_dir/backend-cangjie/native/media_bridge.c" -nt "$bridge" ]]; then
native_tmp=$(mktemp "$CANGJIE_MYSQL_NATIVE/.libzhiwei_mysql.XXXXXX.so")
trap 'rm -f "$native_tmp"' EXIT
cc -std=c11 -Wall -Wextra -Werror -fPIC -shared "$project_dir/backend-cangjie/native/mysql_bridge.c" \
  "$project_dir/backend-cangjie/native/crypto_bridge.c" \
  "$project_dir/backend-cangjie/native/media_bridge.c" \
  -I"$mysql_root/include" -I"$mysql_root/include/x86_64-linux-gnu" -I"$mysql_root/include/mysql" \
  -L"$mysql_root/lib/x86_64-linux-gnu" -lmysqlclient -lcrypto -lpthread \
  -o "$native_tmp"
mv -f "$native_tmp" "$CANGJIE_MYSQL_NATIVE/libzhiwei_mysql.so"
fi
export LD_LIBRARY_PATH="$CANGJIE_MYSQL_NATIVE:$mysql_root/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="$CANGJIE_STDX_PATH:${LD_LIBRARY_PATH:-}"
if [[ -n ${CANGJIE_OPENSSL_LIB_DIR:-} ]]; then
  export LD_LIBRARY_PATH="$CANGJIE_OPENSSL_LIB_DIR:$LD_LIBRARY_PATH"
elif [[ -n ${CONDA_EXE:-} && -d "${CONDA_EXE%/bin/conda}/lib" ]]; then
  export LD_LIBRARY_PATH="${CONDA_EXE%/bin/conda}/lib:$LD_LIBRARY_PATH"
elif command -v conda >/dev/null; then
  export LD_LIBRARY_PATH="$(conda info --base)/lib:$LD_LIBRARY_PATH"
fi
if [[ ${1:-build} == run || ${1:-build} == run-built ]] && [[ -z ${CANGJIE_AUTH_SECRET:-} ]]; then
  secret_file="$project_dir/.runtime/cangjie-auth-secret"
  (
    umask 077
    exec 9<>"$secret_file"
    flock -x 9
    if [[ ! -s "$secret_file" ]]; then openssl rand -hex 48 >&9; fi
  )
  export CANGJIE_AUTH_SECRET=$(cat "$secret_file")
fi
cd "$project_dir/backend-cangjie"
case "${1:-build}" in
  build) cjpm build ;;
  run) cjpm build && exec ./target/release/bin/main ;;
  run-built) exec ./target/release/bin/main ;;
  create-user-built) exec ./target/release/bin/main --create-local-user ;;
  question-bank-built) exec ./target/release/bin/main --question-bank ;;
  seed-knowledge) cjpm build && exec ./target/release/bin/main --seed-knowledge ;;
  upgrade-db) cjpm build && exec ./target/release/bin/main --upgrade-db ;;
  init-db) cjpm build && exec ./target/release/bin/main --init-db ;;
  *) echo '用法：bash scripts/cangjie.sh [build|run|init-db|upgrade-db|seed-knowledge|create-user-built|question-bank-built]' >&2; exit 2 ;;
esac
