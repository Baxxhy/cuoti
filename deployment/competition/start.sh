#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v docker >/dev/null || { echo '请先安装并启动 Docker Engine。'; exit 1; }
docker info >/dev/null
if [[ ! -f .env ]]; then
  cp configuration.env.example .env
  chmod 600 .env
  echo '已创建 .env。请填写 AI 服务密钥，再执行 bash start.sh。'
  echo '也可以保持空值启动基础页面；AI 功能需要有效密钥和网络。'
  exit 0
fi
if ! docker image inspect cuoti-submission:20261023 >/dev/null 2>&1; then
  echo '正在导入交付镜像，请耐心等待。'
  docker load -i images.tar.gz
fi
if ! docker image inspect cuoti-qdrant:20261023 >/dev/null 2>&1; then docker load -i images.tar.gz; fi
docker network inspect cuoti-delivery >/dev/null 2>&1 || docker network create --label app=cuoti-delivery cuoti-delivery >/dev/null
for volume in cuoti-delivery-data cuoti-delivery-index; do docker volume inspect "$volume" >/dev/null 2>&1 || docker volume create --label app=cuoti-delivery "$volume" >/dev/null; done
for name in cuoti-delivery-qdrant cuoti-delivery-app; do
 if docker container inspect "$name" >/dev/null 2>&1; then
  owner=$(docker inspect --format '{{index .Config.Labels "app"}}' "$name")
  [[ "$owner" == cuoti-delivery ]] || { echo "容器名 $name 已被其他项目占用，停止操作。"; exit 1; }
 fi
done
if docker container inspect cuoti-delivery-qdrant >/dev/null 2>&1; then docker start cuoti-delivery-qdrant >/dev/null
else docker run -d --name cuoti-delivery-qdrant --label app=cuoti-delivery --network cuoti-delivery --network-alias qdrant --restart unless-stopped -v cuoti-delivery-index:/qdrant/storage cuoti-qdrant:20261023 >/dev/null; fi
if docker container inspect cuoti-delivery-app >/dev/null 2>&1; then
 echo '正在重建交付容器以读取最新配置，学习数据保留在独立卷中。'
 docker stop -t 60 cuoti-delivery-app >/dev/null
 docker rm cuoti-delivery-app >/dev/null
fi
docker run -d --name cuoti-delivery-app --label app=cuoti-delivery --network cuoti-delivery --restart unless-stopped --env-file .env -e CANGJIE_QDRANT_URL=http://qdrant:6333 -v cuoti-delivery-data:/data -p "${CUOTI_BIND:-127.0.0.1}:${CUOTI_PORT:-5175}:8080" cuoti-submission:20261023 >/dev/null
echo "正在初始化。访问：http://127.0.0.1:${CUOTI_PORT:-5175}；首次启动需等待数据库初始化。"
echo '运行 bash check.sh 查看就绪状态；停止使用 bash stop.sh。'
