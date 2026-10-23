#!/usr/bin/env bash
set -euo pipefail
docker inspect --format '应用状态：{{.State.Status}}；健康检查：{{if .State.Health}}{{.State.Health.Status}}{{end}}' cuoti-delivery-app
docker exec cuoti-delivery-app /opt/python/bin/python3.13 -c 'import urllib.request,json; urls=[("业务", "http://127.0.0.1:8002/readyz"),("算法","http://127.0.0.1:8012/livez"),("检索计算","http://127.0.0.1:8011/health"),("检索存储","http://qdrant:6333/"),("页面","http://127.0.0.1:8080/")]; [(urllib.request.urlopen(u,timeout=10).read(),print(n+"：可访问")) for n,u in urls]; print("AI 请求还需有效密钥；服务可访问不代表模型调用已成功。")'
