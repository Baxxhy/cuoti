"""Real Cangjie voice storage with a deterministic internal compute transport."""

import base64
import hashlib
import io
import json
import secrets
import socket
import subprocess
import tempfile
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from smoke_cangjie_accounts import request


def voice_pipeline(env, query, token, other):
    project = Path(__file__).resolve().parents[1]
    state = {"fail": False, "bad_hash": False, "probes": 0}
    audio = b"ID3-speech-fixture"
    secret = secrets.token_hex(32)
    provider = {
        "logical_model": "Qwen",
        "actual_models": ["Qwen"],
        "total_entries": 1,
        "unique_keys": 1,
        "text_entries": 1,
        "vision_entries": 1,
        "global_index": 0,
        "text_index": 0,
        "vision_index": 0,
        "last_entry": None,
        "last_status": "idle",
        "recent_rotation": [],
    }

    class Compute(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            assert self.headers["Authorization"] == "Bearer " + secret
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            operation = body["operation"]
            status = 502 if state["fail"] and operation.startswith("voice_") else 200
            if operation == "system_state":
                state["probes"] += int(body.get("probe_provider", False))
                result = {
                    "provider": provider,
                    "voice": {
                        "stt_model": "faster-whisper-small",
                        "tts_model": "edge-tts",
                        "loaded": False,
                        "status": "not_loaded",
                    },
                }
            elif operation == "voice_transcribe":
                assert base64.b64decode(body["audio_base64"]) and body[
                    "audio_suffix"
                ] in [".wav", ".webm"]
                result = {
                    "text": "先移项再求解",
                    "metadata": {"model": "faster-whisper-small", "duration_ms": 12},
                }
            else:
                assert (
                    operation == "voice_synthesize" and body["text"] == "先移项再求解"
                )
                result = {
                    "audio_base64": base64.b64encode(audio).decode(),
                    "sha256": "bad"
                    if state["bad_hash"]
                    else hashlib.sha256(audio).hexdigest(),
                    "metadata": {
                        "model": "edge-tts",
                        "duration_ms": 8,
                        "voice": body["voice"],
                    },
                }
            payload = json.dumps({"operation": operation, "result": result}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    compute = ThreadingHTTPServer(("127.0.0.1", 0), Compute)
    thread = threading.Thread(target=compute.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    process = None
    try:
        with (
            tempfile.TemporaryDirectory(prefix="zhiwei-voice-smoke-") as directory,
            tempfile.TemporaryFile() as output,
        ):
            root = Path(directory)
            worker_env = {
                **env,
                "CANGJIE_BACKEND_PORT": str(port),
                "CANGJIE_ALGORITHM_URL": f"http://127.0.0.1:{compute.server_port}",
                "CANGJIE_ALGORITHM_SECRET": secret,
                "CANGJIE_MEDIA_ROOT": str(root / "media"),
            }
            process = subprocess.Popen(
                ["bash", "scripts/cangjie.sh", "run"],
                cwd=project,
                env=worker_env,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            deadline = time.monotonic() + 90
            while True:
                if process.poll() is not None:
                    raise RuntimeError("voice Cangjie process stopped")
                try:
                    with urlopen(endpoint + "/livez", timeout=1):
                        break
                except (HTTPError, URLError, TimeoutError):
                    if time.monotonic() > deadline:
                        raise RuntimeError("voice Cangjie startup timed out") from None
                    time.sleep(0.1)
            assert request(endpoint, "GET", "/api/v1/system/providers") == provider
            assert (
                request(endpoint, "POST", "/api/v1/system/providers/probe", {})
                == provider
                and state["probes"] == 1
            )
            assert (
                request(endpoint, "GET", "/api/v1/system/health")["image_recognition"]
                is True
            )
            q = request(
                endpoint,
                "POST",
                "/api/v1/questions/manual",
                {"question_text": "语音功能验证"},
                token=token,
            )
            work = query(
                env, f"SELECT id FROM student_works WHERE question_id='{q['id']}'"
            ).strip()
            owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
            with io.BytesIO() as stream:
                with wave.open(stream, "wb") as source:
                    source.setnchannels(1)
                    source.setsampwidth(2)
                    source.setframerate(16000)
                    source.writeframes(b"\0\0" * 100)
                wav = stream.getvalue()

            def upload(account=token, raw=wav, expected=200, filename="record.wav"):
                boundary = "voice-" + uuid4().hex
                body = (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
                    + raw
                    + f"\r\n--{boundary}--\r\n".encode()
                )
                try:
                    response = urlopen(
                        Request(
                            endpoint
                            + "/api/v1/voice/transcribe?"
                            + urlencode({"question_id": q["id"], "work_id": work}),
                            data=body,
                            headers={
                                "Authorization": "Bearer " + account,
                                "Content-Type": "multipart/form-data; boundary="
                                + boundary,
                            },
                        ),
                        timeout=20,
                    )
                except HTTPError as error:
                    response = error
                with response:
                    data = json.load(response)
                    assert response.status == expected, (response.status, data)
                    return data.get("data")

            upload(other, expected=404)
            upload(raw=b"", expected=400)
            stt = upload()
            assert (
                stt["text"] == "先移项再求解"
                and stt["editable"]
                and stt["status"] == "completed"
            )
            assert (
                query(
                    env, f"SELECT explanation FROM student_works WHERE id='{work}'"
                ).strip()
                == stt["text"]
            )
            with urlopen(endpoint + stt["audio_url"]) as response:
                assert (
                    response.read() == wav
                    and response.headers.get_content_type() == "audio/wav"
                )
            assert upload(filename="record.unknown")["audio_path"].endswith(".webm")
            request(
                endpoint,
                "POST",
                "/api/v1/voice/synthesize",
                {"text": " "},
                token=token,
                expected=400,
            )
            request(
                endpoint,
                "POST",
                "/api/v1/voice/synthesize",
                {"text": stt["text"], "question_id": q["id"]},
                token=other,
                expected=404,
            )
            tts = request(
                endpoint,
                "POST",
                "/api/v1/voice/synthesize",
                {"text": stt["text"], "question_id": q["id"]},
                token=token,
            )
            assert tts["model_name"] == "edge-tts" and not tts["browser_fallback"]
            with urlopen(endpoint + tts["audio_url"]) as response:
                assert (
                    response.read() == audio
                    and response.headers.get_content_type() == "audio/mpeg"
                )
            state["bad_hash"] = True
            request(
                endpoint,
                "POST",
                "/api/v1/voice/synthesize",
                {"text": stt["text"]},
                token=token,
                expected=502,
            )
            state["bad_hash"] = False
            state["fail"] = True
            upload(expected=502)
            request(
                endpoint,
                "POST",
                "/api/v1/voice/synthesize",
                {"text": stt["text"]},
                token=token,
                expected=502,
            )
            assert (
                query(
                    env,
                    f"SELECT COUNT(*) FROM voice_records WHERE user_id='{owner}' AND status='failed'",
                ).strip()
                == "1"
            )
            assert (
                len(list((root / "media/uploads/voice" / owner).iterdir())) == 4
            )  # three original uploads plus one successful TTS
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        compute.shutdown()
        compute.server_close()
        thread.join(timeout=5)
    print(
        "Cangjie voice passed: actual HTTP/storage, transcript update, audio URLs, TTS, failed records, checksums and owner isolation"
    )
