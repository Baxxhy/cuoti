#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || {
  echo '此安装入口当前支持 Linux x86_64。' >&2; exit 1;
}
cache_dir="$project_dir/.runtime/cangjie-downloads"
install_dir="$project_dir/.runtime/cangjie"
mkdir -p "$cache_dir" "$install_dir"
sdk_archive="$cache_dir/sdk-1.0.5.tar.gz"
stdx_archive="$cache_dir/stdx-1.0.5.1.zip"
sdk_url='https://cangjie-lang.cn/v1/files/auth/downLoad?nsId=142267&fileName=cangjie-sdk-linux-x64-1.0.5.tar.gz&objectKey=698acf46bd66ae22b62330b0'
stdx_url='https://gitcode.com/Cangjie/cangjie_stdx/releases/download/v1.0.5.1/cangjie-stdx-linux-x64-1.0.5.1.zip'
if [[ ! -f "$sdk_archive" ]]; then
  curl --fail --location --retry 3 --max-time 900 "$sdk_url" -o "$sdk_archive.part"
  mv "$sdk_archive.part" "$sdk_archive"
fi
printf '%s  %s\n' 'bacad84df8e0281c5395bab4c40e481e3ea6cc712eed5c953903b0d561a14562' "$sdk_archive" | sha256sum --check -
if [[ ! -f "$stdx_archive" ]]; then
  curl --fail --location --retry 3 --max-time 300 "$stdx_url" -o "$stdx_archive.part"
  unzip -tq "$stdx_archive.part"
  mv "$stdx_archive.part" "$stdx_archive"
fi
tar --no-same-owner -xzf "$sdk_archive" -C "$install_dir"
unzip -oq "$stdx_archive" -d "$install_dir"
"$install_dir/cangjie/bin/cjc" --version
