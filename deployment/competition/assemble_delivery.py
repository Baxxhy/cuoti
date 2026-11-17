"""Assemble public Python source and deployment documents, never live data."""

import argparse
import shutil
import subprocess
import zipfile
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "deployment/competition"


def assemble(bundle):
    bundle.mkdir(parents=True, exist_ok=True)
    doc = Document()
    for name in ["Normal", "Title", "Heading 1", "Heading 2", "Heading 3"]:
        style = doc.styles[name]
        style.font.name = "宋体" if name == "Normal" else "黑体"
        style.font.size = Pt(12 if name == "Normal" else 16)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.element.get_or_add_rPr().get_or_add_rFonts().set(
            qn("w:eastAsia"), style.font.name
        )
    for line in (SOURCE / "部署说明.md").read_text().splitlines():
        if not line:
            continue
        if line.startswith("# "):
            doc.add_heading(line[2:], 0)
        elif line.startswith("## "):
            doc.add_heading(line[3:], 1)
        else:
            doc.add_paragraph(line.replace("**", "").replace("`", ""))
    doc.save(bundle / "部署说明.docx")
    for pattern in [
        "*.sh",
        "*.md",
        "*.docx",
        "*.yaml",
        "*.lock.txt",
        "configuration.env.example",
    ]:
        for file in SOURCE.glob(pattern):
            if file.name not in {"README.md", "部署说明.docx"}:
                shutil.copy2(file, bundle / file.name)
    shutil.copy2(
        ROOT / "docs/迁移方案/竞赛容器与离线镜像迁移验收记录.md", bundle / "验收记录.md"
    )
    scripts = bundle / "部署源码"
    scripts.mkdir(exist_ok=True)
    for name in [
        "entry.py",
        "gateway.py",
        "demo.sql",
        "Dockerfile",
        "Dockerfile.models",
        "prepare_payload.py",
        "prepare_exports.py",
        "prepare_models.py",
    ]:
        shutil.copy2(SOURCE / name, scripts / name)
    tracked = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        .decode()
        .split("\0")
    )
    prefixes = (
        "frontend/",
        "backend-algorithms/",
        "backend-python/",
        "scripts/",
        "docs/迁移方案/",
    )
    selected = []
    for name in tracked:
        if not name or not (
            name.startswith(prefixes)
            or name
            in {
                "README.md",
                "AGENTS.md",
                "Makefile",
                ".env.python.example",
                "config/api_pool.example.json",
            }
        ):
            continue
        path = Path(name)
        if path.name in {
            "cangjie.sh",
            "install_cangjie.sh",
            "install_cangjie_mysql.sh",
        }:
            continue
        if (
            path.name in {".env", ".env.python", ".env.cangjie", "api_pool.json"}
            or path.suffix in {".zip", ".mp4"}
            or any(
                part in path.parts
                for part in ["node_modules", "__pycache__", ".models", ".runtime"]
            )
        ):
            continue
        if (ROOT / name).is_file():
            selected.append(name)
    selected += [
        name
        for name in tracked
        if name.startswith("deployment/competition/")
        and (ROOT / name).is_file()
        and Path(name).name not in {".env", ".env.python", ".env.cangjie"}
        and not name.endswith((".tar.gz", ".zip"))
        and "backups" not in Path(name).parts
    ]
    with zipfile.ZipFile(bundle / "项目源码.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(selected)):
            archive.write(ROOT / name, name)
    print("公开部署文档和 Python 源码已组装：" + str(len(set(selected))) + " 个文件")


def main():
    parser = argparse.ArgumentParser(
        description="组装公开程序包说明与 Python 源码，不收集学生数据和真实密钥"
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=ROOT / ".runtime/python-delivery/bundle/错题帮_Python可运行程序包",
    )
    args = parser.parse_args()
    assemble(args.bundle)


if __name__ == "__main__":
    main()
