#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

import httpx
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal
from app.models import VoiceRecord

BASE = "http://127.0.0.1:8000/api/v1"
SENTENCE = "因为等式两边同时减去相同的数，所以移项表现为变号。"


def unpack(response: httpx.Response):
    response.raise_for_status()
    body = response.json()
    assert body["success"], body
    return body["data"]


async def database_evidence(user_id: str, stt_id: str, tts_id: str) -> dict[str, object]:
    async with SessionLocal() as db:
        stt, tts = await db.get(VoiceRecord, stt_id), await db.get(VoiceRecord, tts_id)
        count = int(await db.scalar(select(func.count()).select_from(VoiceRecord).where(
            VoiceRecord.user_id == user_id)) or 0)
        assert stt and tts
        assert stt.model_name == "faster-whisper-small" and stt.status == "completed"
        assert tts.model_name == "edge-tts" and tts.status == "completed"
        assert Path(stt.audio_path).exists() and Path(tts.audio_path).exists()
        return {"records_for_user": count, "stt_model": stt.model_name, "tts_model": tts.model_name,
                "stt_audio_saved": True, "tts_audio_saved": True}


def main() -> int:
    client = httpx.Client(timeout=300)
    user = unpack(client.post(BASE + "/auth/login", json={"email": "e2e@minddimension.local", "password": "123456"}))
    headers = {"Authorization": f"Bearer {user['access_token']}"}
    tts = unpack(client.post(BASE + "/voice/synthesize", headers=headers, json={"text": SENTENCE}))
    assert tts["model_name"] == "edge-tts" and tts["browser_fallback"] is False
    tts_path = ROOT / tts["audio_url"].removeprefix("/")
    assert tts_path.exists() and tts_path.stat().st_size > 1_000
    with tts_path.open("rb") as audio:
        stt = unpack(client.post(BASE + "/voice/transcribe", headers=headers,
                                 files={"file": (tts_path.name, audio, "audio/mpeg")}))
    assert stt["model_name"] == "faster-whisper-small"
    assert stt["metadata"]["language"] == "zh" and stt["metadata"]["segment_count"] >= 1
    assert len(stt["text"]) >= 10 and all(word in stt["text"] for word in ("等式", "两边", "变号"))
    status = unpack(client.get(BASE + "/system/voice", headers=headers))
    assert status["loaded"] and status["status"] == "ready"
    database = asyncio.run(database_evidence(user["id"], stt["id"], tts["id"]))
    report = {
        "passed": True, "source_text": SENTENCE, "transcript": stt["text"],
        "stt": stt["metadata"], "tts": {"model": tts["model_name"], "bytes": tts_path.stat().st_size,
                                            "sha256": hashlib.sha256(tts_path.read_bytes()).hexdigest()},
        "database": database, "browser_fallback_used": False,
    }
    target = ROOT / "reports/verification/voice.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "transcript": stt["text"], "stt": stt["metadata"],
                      "tts_bytes": tts_path.stat().st_size, "database": database}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
