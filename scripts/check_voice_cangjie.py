#!/usr/bin/env python3
"""Explicit real speech check through Cangjie; writes two caller-owned voice records."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import io
import json
import sys
from urllib.parse import urljoin, urlsplit

import av
import httpx

SENTENCE = "因为等式两边同时减去相同的数，所以移项表现为变号。"


def check(base: str, token: str) -> dict:
    origin = urlsplit(base)
    if origin.scheme not in {"http", "https"} or origin.path.rstrip("/") != "/api/v1":
        raise ValueError("请输入仓颉的完整 /api/v1 地址")
    if origin.username or origin.password or origin.query or origin.fragment:
        raise ValueError("服务地址不能包含凭据、查询或片段")
    root = f"{origin.scheme}://{origin.netloc}"
    with httpx.Client(timeout=150) as client:
        identity = client.get(root + "/livez")
        identity.raise_for_status()
        if identity.json().get("service") != "zhiwei-cangjie":
            raise ValueError("目标不是仓颉业务服务")
        headers = {"Authorization": f"Bearer {token}"}
        user = client.get(base + "/auth/me", headers=headers)
        user.raise_for_status()
        if not user.json().get("data", {}).get("id"):
            raise ValueError("无法确认当前账号")
        response = client.post(
            base + "/voice/synthesize", headers=headers, json={"text": SENTENCE}
        )
        response.raise_for_status()
        tts = response.json()["data"]
        if (
            tts.get("browser_fallback") is not False
            or tts.get("model_name") != "edge-tts"
        ):
            raise ValueError("未得到真实服务端合成结果")
        audio_url = urljoin(root + "/", tts["audio_url"])
        if urlsplit(audio_url).netloc != origin.netloc:
            raise ValueError("音频链接不属于当前服务")
        audio = client.get(audio_url)
        audio.raise_for_status()
        with av.open(io.BytesIO(audio.content)) as stream:
            frames = sum(1 for _ in stream.decode(audio=0))
        if len(audio.content) < 1000 or not frames:
            raise ValueError("下载音频未通过解码检查")
        response = client.post(
            base + "/voice/transcribe",
            headers=headers,
            files={"file": ("check.mp3", audio.content, "audio/mpeg")},
        )
        response.raise_for_status()
        stt = response.json()["data"]
        transcript = stt.get("text", "")
        if (
            stt.get("status") != "completed"
            or stt.get("model_name") != "faster-whisper-small"
        ):
            raise ValueError("转写未完成")
        keywords = {word: word in transcript for word in ("等式", "两边", "变号")}
        if not all(keywords.values()):
            raise ValueError("转写未识别出固定句子的关键内容")
        return {
            "passed": True,
            "source_text": SENTENCE,
            "transcript": transcript,
            "keyword_check": keywords,
            "tts": {
                "record_id": tts["id"],
                "model": tts["model_name"],
                "bytes": len(audio.content),
                "sha256": hashlib.sha256(audio.content).hexdigest(),
                "decoded_frames": frames,
            },
            "stt": {
                "record_id": stt["id"],
                "model": stt["model_name"],
                "status": stt["status"],
            },
            "student_trial": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8002/api/v1")
    parser.add_argument(
        "--token-stdin",
        action="store_true",
        required=True,
        help="从标准输入读取当前账号访问令牌，不放入命令行",
    )
    args = parser.parse_args()
    token = (
        getpass.getpass("访问令牌（不回显）：")
        if sys.stdin.isatty()
        else sys.stdin.readline()
    ).strip()
    if not token:
        print("未提供访问令牌", file=sys.stderr)
        return 2
    try:
        result = check(args.api_base.rstrip("/"), token)
    except httpx.HTTPStatusError as error:
        print(f"语音检查失败：HTTP {error.response.status_code}", file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001 -- CLI boundary must not expose signed URLs or request data
        # Never echo signed URLs, request headers or upstream error payloads.
        print(f"语音检查未通过（{type(error).__name__}）", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
