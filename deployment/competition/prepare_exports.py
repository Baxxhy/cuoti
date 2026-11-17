"""Collect the existing offline formula renderer; do not copy user configuration."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def collect(payload, *, frontend=None, chromium=None):
    frontend = Path(frontend or ROOT / "frontend")
    chromium = Path(chromium or os.environ.get("ZHIWEI_PDF_CHROMIUM", ""))
    if not chromium.is_file():
        candidates = sorted(
            (frontend / ".playwright-browsers").glob("chromium-*/chrome-linux64/chrome")
        )
        if not candidates:
            raise RuntimeError(
                "缺少 Chromium；请先运行 make install-browser 或设置 ZHIWEI_PDF_CHROMIUM"
            )
        chromium = candidates[-1]
    if not (frontend / "node_modules").is_dir() or not shutil.which("node"):
        raise RuntimeError("缺少 Node 或前端排版依赖")
    for source, target in [
        (Path(shutil.which("node")), payload / "python/bin/node"),
        (frontend / "package.json", payload / "app/frontend/package.json"),
        (frontend / "node_modules", payload / "app/frontend/node_modules"),
        (frontend / "src/utils", payload / "app/frontend/src/utils"),
        (chromium.parent, payload / "chromium"),
        (
            ROOT / "scripts/render_math_pdf.cjs",
            payload / "app/scripts/render_math_pdf.cjs",
        ),
        (Path("/usr/share/fonts/opentype/noto"), payload / "fonts/noto"),
        (Path("/etc/fonts"), payload / "fontconfig"),
    ]:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                symlinks=source.name == "node_modules",
                dirs_exist_ok=True,
            )
        else:
            shutil.copy2(source, target)
    # Fonts are mounted by the Dockerfile into their normal system locations.
    return payload / "chromium/chrome"


def verify_image(image):
    # Use Docker's actual image filesystem; do not bind a client-only build path.
    command = [
        "docker",
        "run",
        "-i",
        "--rm",
        "--network",
        "none",
        "--entrypoint",
        "/opt/python/bin/node",
        image,
        "/opt/app/scripts/render_math_pdf.cjs",
    ]
    sample = json.dumps(
        {
            "title": "Runtime check",
            "questions": [{"question_text": "$x+x=2x$", "score": 10}],
            "answers": False,
            "output": "/tmp/check.pdf",
        }
    )
    done = subprocess.run(
        command, input=sample, capture_output=True, text=True, timeout=120, check=False
    )
    if done.returncode:
        raise RuntimeError("镜像内数学 PDF 生成失败；请检查运行库和前端排版依赖")
    print("镜像内 Node、KaTeX、Chromium 数学 PDF 真实生成通过")


def main():
    parser = argparse.ArgumentParser(
        description="为已准备的 Python 交付上下文补齐公式排版资源"
    )
    parser.add_argument(
        "--payload",
        type=Path,
        default=ROOT / ".runtime/python-delivery/context/payload",
    )
    parser.add_argument(
        "--check-image", help="在已构建镜像内部验证真实数学 PDF，不调用 AI"
    )
    args = parser.parse_args()
    if args.check_image:
        verify_image(args.check_image)
        return
    collect(args.payload)
    print("公式排版资源已收集；完整依赖检查请运行 prepare_payload.py")


if __name__ == "__main__":
    main()
