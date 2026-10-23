from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

import edge_tts


class VoiceProvider:
    def __init__(self) -> None:
        self.model_name = "faster-whisper-small"
        self.model_dir = Path(".models/faster-whisper")
        self._model: Any = None
        self._lock = asyncio.Lock()
        self.last_status = "not_loaded"

    def _load_model(self) -> Any:
        if self._model is None:
            os.environ.setdefault("HF_HOME", str(Path(".models/huggingface").resolve()))
            from faster_whisper import WhisperModel

            self.model_dir.mkdir(parents=True, exist_ok=True)
            self._model = WhisperModel(
                "small",
                device="cpu",
                compute_type="int8",
                download_root=str(self.model_dir.resolve()),
                cpu_threads=max(1, min(8, os.cpu_count() or 2)),
            )
        return self._model

    def _transcribe_sync(self, path: Path) -> tuple[str, dict[str, Any]]:
        started = time.perf_counter()
        model = self._load_model()
        segments, info = model.transcribe(str(path), language="zh", beam_size=5, vad_filter=True)
        segment_list = list(segments)
        text = "".join(segment.text.strip() for segment in segment_list).strip()
        duration = max((segment.end for segment in segment_list), default=0.0)
        return text, {
            "language": info.language,
            "language_probability": round(info.language_probability, 4),
            "audio_duration_seconds": round(duration, 3),
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "segment_count": len(segment_list),
            "model": self.model_name,
        }

    async def transcribe(self, path: Path) -> tuple[str, dict[str, Any]]:
        async with self._lock:
            try:
                text, metadata = await asyncio.to_thread(self._transcribe_sync, path)
                self.last_status = "ready"
                return text, metadata
            except Exception:
                self.last_status = "failed"
                raise

    async def synthesize(
        self, text: str, target: Path, voice: str = "zh-CN-XiaoxiaoNeural"
    ) -> dict[str, Any]:
        started = time.perf_counter()
        target.parent.mkdir(parents=True, exist_ok=True)
        await edge_tts.Communicate(text=text, voice=voice).save(str(target))
        self.last_status = "ready"
        return {
            "model": "edge-tts",
            "voice": voice,
            "duration_ms": round((time.perf_counter() - started) * 1000),
        }

    def health_check(self) -> dict[str, Any]:
        return {
            "stt_model": self.model_name,
            "tts_model": "edge-tts",
            "status": self.last_status,
            "loaded": self._model is not None,
        }


voice_provider = VoiceProvider()
