"""Build a portable Python/MySQL payload from the active Linux environment."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

from prepare_exports import collect as collect_exports

ROOT = Path(__file__).resolve().parents[2]
EXCLUDE_LIBRARIES = re.compile(
    r"^(libc\.so|libm\.so|libpthread\.so|libdl\.so|librt\.so|libutil\.so|libresolv\.so|ld-linux)"
)


def copy(source, target):
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            symlinks=False,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                ".git",
                ".pytest_cache",
                "tests",
                "*.pyc",
                ".env",
                ".env.*",
                "api_pool.json",
                "backups",
                ".runtime",
                ".venv",
                "build",
                "*.egg-info",
                "*.tar.gz",
            ),
        )
    else:
        shutil.copy2(source, target)


def collect_libraries(payload, binaries, library_paths):
    native = payload / "native"
    native.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "LD_LIBRARY_PATH": os.pathsep.join([str(native), *map(str, library_paths)]),
    }
    # Wheel-private FFmpeg/BLAS libraries may only carry sibling-relative RPATHs.
    # Include their folders for discovery, then collect exact named dependencies.
    private = sorted(
        {str(path.parent) for path in binaries if ".libs" in str(path.parent)}
    )
    env["LD_LIBRARY_PATH"] += os.pathsep + os.pathsep.join(private)
    queue, seen = list(binaries), set()
    while queue:
        binary = queue.pop()
        if str(binary) in seen:
            continue
        seen.add(str(binary))
        done = subprocess.run(
            ["ldd", str(binary)], env=env, capture_output=True, text=True, check=False
        )
        if "=> not found" in done.stdout:
            missing = re.findall(r"(\S+) => not found", done.stdout)
            raise RuntimeError(
                "运行库缺失：" + ",".join(missing) + "；文件：" + binary.name
            )
        for name, path in re.findall(r"\s+(\S+) => (/\S+)", done.stdout):
            if EXCLUDE_LIBRARIES.match(name):
                continue
            target = native / name
            if not target.exists():
                copy(path, target)
                queue.append(target)


def prepare(context):
    if context.exists() and any(context.iterdir()):
        raise RuntimeError("构建上下文非空，请指定新的 --context；不会覆盖已有程序包")
    payload = context / "payload"
    payload.mkdir(parents=True)
    print("收集 Python 业务代码与已构建前端", flush=True)
    for name in ["backend-python", "backend-algorithms"]:
        copy(ROOT / name, payload / "app" / name)
    copy(ROOT / "frontend/dist/build/h5", payload / "app/web")
    copy(
        ROOT / "scripts/retrieval_inference_server.py",
        payload / "app/scripts/retrieval_inference_server.py",
    )
    copy(ROOT / "config/api_pool.example.json", payload / "app/config/api_pool.json")
    for name in ["entry.py", "gateway.py", "demo.sql"]:
        copy(ROOT / "deployment/competition" / name, payload / "app/deployment" / name)
    print("收集当前 Python 解释器、标准库及项目依赖", flush=True)
    copy(Path(sys.executable).resolve(), payload / "python/bin/python3.13")
    stdlib = Path(sysconfig.get_path("stdlib"))
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError(
            "当前离线交付镜像使用 Python 3.13；请从对应项目环境运行收集工具"
        )
    for source in stdlib.iterdir():
        if source.name not in {
            "site-packages",
            "__pycache__",
            "test",
            "tests",
            "idlelib",
            "tkinter",
            "turtledemo",
        }:
            copy(source, payload / "python/lib/python3.13" / source.name)
    site = payload / "python/lib/python3.13/site-packages"
    copy(sysconfig.get_path("purelib"), site)
    # Remove editable import hooks pointing at the build host. Source uses PYTHONPATH.
    for source in site.glob("__editable__*"):
        if source.is_file():
            source.unlink()
    for command in ["mysqld", "mysql", "mysqladmin", "mysqldump"]:
        executable = shutil.which(command)
        if not executable:
            raise RuntimeError("缺少 MySQL 工具：" + command)
        copy(executable, payload / "mysql/bin" / command)
    copy("/usr/share/mysql", payload / "mysql/share")
    copy("/usr/lib/mysql/plugin", payload / "mysql/lib/plugin")
    copy("/usr/lib/mysql/private", payload / "mysql/lib/private")
    copy("/etc/ssl/certs/ca-certificates.crt", payload / "certs/ca-certificates.crt")
    print("收集真实 Node、Chromium 与前端数学排版依赖", flush=True)
    chromium = collect_exports(payload)
    browser_libs = Path(
        os.environ.get(
            "CUOTI_BROWSER_LIBRARIES",
            ROOT / "frontend/.playwright-libs/root/usr/lib/x86_64-linux-gnu",
        )
    )
    binaries = [
        payload / "python/bin/python3.13",
        payload / "python/bin/node",
        chromium,
        *list((payload / "mysql/bin").iterdir()),
        *list((payload / "mysql/lib/plugin").glob("*.so")),
        *list((payload / "python").rglob("*.so*")),
    ]
    # Conda's libffi.so.7 can alias ABI 8; system p11-kit needs the real ABI 7.
    # Keep the matching system terminal ABI too, instead of an unversioned build.
    for name in ["libffi.so.7", "libtinfo.so.6"]:
        system = Path("/lib/x86_64-linux-gnu") / name
        if system.is_file():
            copy(system.resolve(), payload / "native" / name)
    print("解析 Python、MySQL 与浏览器的动态库依赖，不收集仓颉桥接", flush=True)
    collect_libraries(payload, binaries, [Path(sys.base_prefix) / "lib", browser_libs])
    for source in [
        Path(sys.base_prefix) / "lib/python3.13/LICENSE.txt",
        Path("/usr/share/doc/mysql-server/copyright"),
        Path("/usr/share/doc/fonts-noto-cjk/copyright"),
        Path(shutil.which("node")).parent.parent / "LICENSE",
    ]:
        if source.is_file():
            copy(
                source, payload / "licenses" / (source.parent.name + "-" + source.name)
            )
    copy(ROOT / "deployment/competition/Dockerfile", context / "Dockerfile")
    forbidden = [
        path
        for path in payload.rglob("*")
        if "cangjie" in path.name.lower() or path.name == "libzhiwei_mysql.so"
    ]
    # Compatibility configuration strings in Python source are expected; runtime files are not.
    if forbidden:
        raise RuntimeError("交付资源中发现仓颉命名产物，请检查收集目录")
    (context / "资源清单.json").write_text(
        json.dumps(
            {
                "python": sys.version.split()[0],
                "business_backend": "FastAPI",
                "cangjie_runtime": False,
                "source_dirty": bool(
                    subprocess.check_output(
                        ["git", "status", "--porcelain"], cwd=ROOT, text=True
                    )
                ),
                "source_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("Python 交付上下文已准备：" + str(context), flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="收集 Python 交付资源；不读取学生数据或私有配置"
    )
    parser.add_argument(
        "--context", type=Path, default=ROOT / ".runtime/python-delivery/context"
    )
    args = parser.parse_args()
    prepare(args.context.resolve())


if __name__ == "__main__":
    main()
