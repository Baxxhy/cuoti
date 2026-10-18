"""Original speech algorithms with temporary files; no business storage or database."""

import base64
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.voice import VoiceProvider


class VoiceComputeError(RuntimeError):
    pass


async def transcribe_audio(provider: VoiceProvider, encoded: str, suffix: str):
    try:
        data = base64.b64decode(encoded, validate=True)
        if not data or len(data) > 15 * 1024 * 1024:
            raise ValueError("audio size")
        with TemporaryDirectory(prefix="zhiwei-voice-compute-") as directory:
            source = Path(directory) / ("input" + suffix)
            source.write_bytes(data)
            text, metadata = await provider.transcribe(source)
            return {"text": text, "metadata": metadata}
    except Exception:  # noqa: BLE001 -- provider failures are sanitized at the compute boundary
        raise VoiceComputeError("speech transcription unavailable") from None


async def synthesize_audio(provider: VoiceProvider, text: str, voice: str):
    try:
        if not text.strip():
            raise ValueError("text required")
        with TemporaryDirectory(prefix="zhiwei-voice-compute-") as directory:
            target = Path(directory) / "speech.mp3"
            metadata = await provider.synthesize(text, target, voice)
            data = target.read_bytes()
            if not data or len(data) > 64 * 1024 * 1024:
                raise ValueError("audio result size")
            return {
                "metadata": metadata,
                "audio_base64": base64.b64encode(data).decode(),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
    except Exception:  # noqa: BLE001 -- provider failures are sanitized at the compute boundary
        raise VoiceComputeError("speech synthesis unavailable") from None
