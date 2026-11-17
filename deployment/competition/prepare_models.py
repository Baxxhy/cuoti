"""Reuse public CPU BGE artifacts from an existing delivery image, never its app."""

import argparse
import json
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


def prepare(image, context):
    if context.exists() and any(context.iterdir()):
        raise RuntimeError("模型上下文非空，请指定新目录")
    payload = context / "payload"
    payload.mkdir(parents=True)
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
    ).strip()
    name = "cuoti-model-artifacts-" + uuid4().hex[:12]
    subprocess.run(
        [
            "docker",
            "create",
            "--name",
            name,
            "--label",
            "app=cuoti-model-artifacts",
            "--entrypoint",
            "/bin/true",
            image,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    try:
        for source, target in [
            ("/opt/retrieval", payload / "retrieval"),
            ("/opt/app/.models/bge", payload / "app/.models/bge"),
            ("/opt/app/.models/faster-whisper", payload / "app/.models/faster-whisper"),
        ]:
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["docker", "cp", name + ":" + source, str(target)], check=True
            )
    finally:
        subprocess.run(
            ["docker", "rm", "-v", name], check=True, stdout=subprocess.DEVNULL
        )
    for path in payload.rglob("*"):
        if (
            path.name in {"token", "stored_tokens", "api_pool.json", ".env"}
            or "cangjie" in path.name.lower()
        ):
            raise RuntimeError("模型资源包含不应分发的配置或产物；未构建镜像")
    (context / "模型来源.json").write_text(
        json.dumps(
            {
                "source_image_id": image_id,
                "copied": [
                    "/opt/retrieval",
                    "/opt/app/.models/bge",
                    "/opt/app/.models/faster-whisper",
                ],
                "business_code_copied": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    (context / "Dockerfile").write_text(
        (ROOT / "deployment/competition/Dockerfile.models").read_text()
    )
    print(
        "只复制公共 BGE、语音权重与原 CPU 推理环境，未复制旧业务程序、运行库或私有配置："
        + str(context),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="复用已有离线 BGE 模型缓存；不运行旧业务程序"
    )
    parser.add_argument("--source-image", required=True)
    parser.add_argument(
        "--context", type=Path, default=ROOT / ".runtime/python-delivery/models-context"
    )
    args = parser.parse_args()
    prepare(args.source_image, args.context.resolve())


if __name__ == "__main__":
    main()
