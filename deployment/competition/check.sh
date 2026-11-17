#!/usr/bin/env bash
set -euo pipefail
container=${CUOTI_CONTAINER_NAME:-cuoti-delivery-app}
docker inspect --format '应用状态：{{.State.Status}}；健康检查：{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container"
docker exec -i "$container" /opt/python/bin/python3.13 - <<'PY'
import json
import urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for name, url in [
    ('Python 业务后端', 'http://127.0.0.1:8002/livez'),
    ('MySQL 结构', 'http://127.0.0.1:8002/readyz'),
    ('检索存储', 'http://qdrant:6333/'),
    ('页面', 'http://127.0.0.1:8080/'),
]:
    with opener.open(url, timeout=10) as response:
        if name == 'Python 业务后端':
            assert json.load(response)['service'] == 'cuoti-python'
    print(name + '：可访问')
from pathlib import Path
if Path('/opt/retrieval/bin/python').exists():
    opener.open('http://127.0.0.1:8011/health', timeout=10).close()
    print('BGE 检索计算：可访问')
else:
    print('未随镜像附带本地 BGE；请配置外部检索计算服务。')
print('健康检查不代表模型输出质量；真实调用需有效配置。')
PY
