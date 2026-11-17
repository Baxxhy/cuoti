"""Python evaluation deployment, retaining existing MySQL volumes and identities."""

import json
import os
import re
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

ROOT = Path("/opt/app")
DATA = Path("/data")
DATABASE = "zhiwei_cangjie_delivery"  # Historical name: retain the existing volume.
PYTHON = "/opt/python/bin/python3.13"
children = []


def shutdown():
    for child in reversed(children):
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 40
    for child in reversed(children):
        try:
            child.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()


def stop(*_):
    raise SystemExit(0)


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def start(args, **kwargs):
    child = subprocess.Popen(args, start_new_session=True, **kwargs)
    children.append(child)
    return child


def wait(check, seconds=180):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except (OSError, ValueError):
            pass
        if any(child.poll() is not None for child in children):
            raise RuntimeError("子服务已退出，请查看部署日志")
        time.sleep(1)
    raise RuntimeError("启动超时，请查看部署日志")


def credentials():
    file = DATA / "secrets.json"
    if not file.exists():
        if (DATA / "mysql/mysql").exists():
            raise RuntimeError("已有 MySQL 数据但缺少原密钥文件，拒绝生成新密码")
        descriptor = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            json.dump(
                {
                    key: secrets.token_hex(32)
                    for key in ["db", "auth", "algorithm", "root"]
                },
                output,
            )
    value = json.loads(file.read_text())
    if any(
        not isinstance(value.get(key), str)
        or re.fullmatch(r"[0-9a-f]{64}", value[key]) is None
        for key in ["db", "auth", "algorithm", "root"]
    ):
        raise RuntimeError("原密钥文件格式不正确；未重置数据库或账号")
    return value


def environment(value):
    env = {
        **os.environ,
        "CUOTI_DB_HOST": "127.0.0.1",
        "CUOTI_DB_PORT": "3307",
        "CUOTI_DB_NAME": DATABASE,
        "CUOTI_DB_USER": "cuoti",
        "CUOTI_DB_PASSWORD": value["db"],
        "CUOTI_AUTH_SECRET": value["auth"],
        "CUOTI_ALGORITHM_SECRET": value["algorithm"],
        "CUOTI_MEDIA_ROOT": str(DATA / "media"),
        "CUOTI_PROJECT_ROOT": str(DATA),
        "CUOTI_QUESTION_BANK_ROOT": str(DATA / "question_bank_assets"),
        "CUOTI_ENV_FILE": str(DATA / ".env.python"),
        "CUOTI_HOST": "127.0.0.1",
        "CUOTI_PORT": "8002",
        "CUOTI_API_POOL_PATH": os.environ.get(
            "CUOTI_API_POOL_PATH", str(ROOT / "config/api_pool.json")
        ),
        "CUOTI_AI_USE_ENV_PROXY": os.environ.get(
            "CUOTI_AI_USE_ENV_PROXY",
            os.environ.get("CANGJIE_AI_USE_ENV_PROXY", "false"),
        ),
        "CUOTI_LEARNING_TASK_WORKER_ENABLED": os.environ.get(
            "CUOTI_LEARNING_TASK_WORKER_ENABLED", "true"
        ),
        "PYTHONPATH": ":".join(
            str(ROOT / name)
            for name in ["backend-python", "backend-algorithms", "deployment"]
        ),
        "PYTHONHOME": "/opt/python",
        "SSL_CERT_FILE": "/opt/certs/ca-certificates.crt",
        "ZHIWEI_PDF_CHROMIUM": "/opt/chromium/chrome",
        "HF_HUB_OFFLINE": "1",
    }
    env.setdefault(
        "CUOTI_QDRANT_URL", os.environ.get("CANGJIE_QDRANT_URL", "http://qdrant:6333")
    )
    env.setdefault(
        "CUOTI_QDRANT_COLLECTION",
        os.environ.get("CANGJIE_QDRANT_COLLECTION", DATABASE + "_questions_v1"),
    )
    return env


def mysql(value):
    data = DATA / "mysql"
    if data.exists() and any(data.iterdir()) and not (data / "mysql").is_dir():
        raise RuntimeError("MySQL 数据目录非空且不完整；拒绝重新初始化")
    fresh = not (data / "mysql").is_dir()
    data.mkdir(exist_ok=True)
    base = [
        "/opt/mysql/bin/mysqld",
        "--no-defaults",
        "--user=root",
        "--basedir=/opt/mysql",
        "--datadir=" + str(data),
        "--lc-messages-dir=/opt/mysql/share",
        "--plugin-dir=/opt/mysql/lib/plugin",
        "--secure-file-priv=NULL",
    ]
    if fresh:
        run([*base, "--initialize-insecure"])
    start(
        [
            *base,
            "--bind-address=127.0.0.1",
            "--port=3307",
            "--socket=/tmp/cuoti-mysql.sock",
            "--pid-file=/tmp/cuoti-mysql.pid",
            "--mysqlx=0",
            "--skip-log-bin",
            "--innodb-buffer-pool-size=128M",
        ]
    )
    config = DATA / "mysql-client.cnf"
    config.write_text(
        "[client]\nuser=root\npassword="
        + value["root"]
        + "\nsocket=/tmp/cuoti-mysql.sock\ndefault-character-set=utf8mb4\n"
    )
    config.chmod(0o600)
    configured = ["/opt/mysql/bin/mysql", "--defaults-extra-file=" + str(config)]
    insecure = [
        "/opt/mysql/bin/mysql",
        "--no-defaults",
        "--socket=/tmp/cuoti-mysql.sock",
        "-uroot",
    ]

    def connects(command):
        return (
            subprocess.run(
                [*command, "-NBe", "SELECT 1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            == 0
        )

    admin = None

    def ready():
        nonlocal admin
        if connects(configured):
            admin = configured
            return True
        if not (DATA / "root-configured").exists() and connects(insecure):
            run(
                insecure,
                input=f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{value['root']}';",
                text=True,
            )
            admin = configured
            return True
        return False

    wait(ready)
    # Never reset an existing account's password; the persisted secrets remain authoritative.
    run(
        admin,
        input=f"CREATE DATABASE IF NOT EXISTS {DATABASE} CHARACTER SET utf8mb4; "
        f"CREATE USER IF NOT EXISTS 'cuoti'@'localhost' IDENTIFIED WITH mysql_native_password BY '{value['db']}'; "
        f"GRANT ALL ON {DATABASE}.* TO 'cuoti'@'localhost';",
        text=True,
    )
    (DATA / "root-configured").write_text("1\n")
    return admin


def prepare_database(admin, env):
    count = subprocess.check_output(
        [
            *admin,
            "-NBe",
            f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='{DATABASE}'",
        ],
        text=True,
    ).strip()
    command = [PYTHON, "-m", "cuoti_backend.manage_db"]
    if count == "0":
        run([*command, "init"], cwd=ROOT, env=env)
        run([*command, "seed-knowledge"], cwd=ROOT, env=env)
        if os.environ.get("CUOTI_DEMO_DATA", "true").lower() == "true":
            run(
                [*admin, DATABASE],
                input=(ROOT / "deployment/demo.sql").read_text(),
                text=True,
            )
    else:
        status = json.loads(
            subprocess.check_output([*command, "status"], cwd=ROOT, env=env, text=True)
        )
        if status.get("missing"):
            if os.environ.get("CUOTI_UPGRADE_DB", "false").lower() != "true":
                raise RuntimeError(
                    "已有数据库需升级；请备份并显式设置 CUOTI_UPGRADE_DB=true，未改结构"
                )
            run([*command, "upgrade"], cwd=ROOT, env=env)
    (DATA / "initialized").write_text("1\n")


def main():
    os.umask(0o077)
    DATA.mkdir(exist_ok=True)
    value = credentials()
    env = environment(value)
    admin = mysql(value)
    prepare_database(admin, env)
    retrieval = Path("/opt/retrieval/bin/python")
    if retrieval.is_file():
        retrieval_env = {
            **env,
            "PYTHONHOME": "/opt/retrieval",
            "PYTHONPATH": str(ROOT),
            "LD_LIBRARY_PATH": "/opt/retrieval/lib:/opt/native",
            "RETRIEVAL_MODEL_CACHE": str(ROOT / ".models/bge"),
            "RETRIEVAL_EMBEDDING_DEVICE": "cpu",
            "RETRIEVAL_RERANKER_DEVICE": "cpu",
            "OMP_NUM_THREADS": "4",
        }
        start(
            [
                str(retrieval),
                "-m",
                "uvicorn",
                "scripts.retrieval_inference_server:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8011",
                "--no-access-log",
            ],
            cwd=ROOT,
            env=retrieval_env,
        )
    start([PYTHON, "-m", "cuoti_backend"], cwd=ROOT, env=env)
    opener = build_opener(ProxyHandler({}))
    wait(lambda: opener.open("http://127.0.0.1:8002/readyz", timeout=3).status == 200)
    if retrieval.is_file():
        wait(
            lambda: opener.open("http://127.0.0.1:8011/health", timeout=3).status == 200
        )
    start(
        [
            PYTHON,
            "-m",
            "uvicorn",
            "gateway:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
            "--no-access-log",
        ],
        cwd=ROOT,
        env=env,
    )
    print("Python 统一后端已就绪：容器端口 8080；请在网页注册学生账号。", flush=True)
    while all(child.poll() is None for child in children):
        time.sleep(1)
    raise RuntimeError("运行中的子服务退出")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- Keep connection credentials out of supervisor errors.
        print(
            "部署失败：" + type(error).__name__ + "；请检查服务日志与数据库版本。",
            flush=True,
        )
        sys.exit(1)
    finally:
        shutdown()
