import asyncio
import base64
import hashlib
import io
import json
import sys

import httpx
import pytest
import service
from app.providers.api_pool import ApiPoolProvider
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from service import create_app

SECRET = "algorithm-test-secret-" + "x" * 32
HEADERS = {"Authorization": "Bearer " + SECRET}


def test_learning_task_handwriting_http_contract(tmp_path):
    class Reader:
        async def close(self):
            pass

        async def generate_multimodal(self, prompt, images, schema, **kwargs):
            return schema(
                final_answer="x=4",
                steps=["2x=8", "x=4"],
                transcription="2x=8\nx=4",
                uncertain=True,
                confidence=0.7,
            )

    app = create_app(secret=SECRET, pool_path=tmp_path / "missing.json")
    with TestClient(app) as client:
        app.state.provider = Reader()
        response = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={
                "operation": "learning_task",
                "task_context": {
                    "question_id": "q1",
                    "question_text": "解方程：2x+3=11",
                    "expected": "x=4",
                },
                "task_action": {
                    "kind": "recognize_handwriting",
                    "handwriting_id": "photo-1",
                    "image_base64": image_input(),
                },
            },
        )
        assert response.status_code == 200, response.json()
        result = response.json()["result"]
        assert result["student_view"]["handwriting"]["suggested_text"] == "x=4"
        assert result["attempt"] is None and not result["learning_eligible"]
        assert "image_base64" not in json.dumps(result)


def image_input():
    image = Image.new("RGB", (100, 80), "white")
    ImageDraw.Draw(image).rectangle((20, 10, 40, 30), fill="red")
    output = io.BytesIO()
    image.save(output, "PNG")
    return base64.b64encode(output.getvalue()).decode()


def test_compute_boundary_and_images(tmp_path):
    app = create_app(secret=SECRET, pool_path=tmp_path / "missing.json")
    with TestClient(app) as client:
        assert client.get("/livez").json()["database"] is False
        assert (
            not {"app.db", "app.models", "app.main", "app.config"} & sys.modules.keys()
        )
        assert client.post("/v1/compute", json={}).status_code == 401
        assert (
            client.post(
                "/v1/compute", headers={"Authorization": SECRET}, json={}
            ).status_code
            == 401
        )
        assert client.get("/api/v1/questions").status_code == 404
        assert (
            client.post(
                "/v1/compute",
                headers=HEADERS,
                json={
                    "operation": "crop",
                    "image_base64": image_input(),
                    "box": [0, 0, 2, 1],
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/compute",
                headers=HEADERS,
                json={"operation": "normalize", "image_base64": "not base64"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/compute",
                headers=HEADERS,
                json={
                    "operation": "normalize",
                    "image_base64": image_input(),
                    "path": "/etc/passwd",
                },
            ).status_code
            == 422
        )
        for operation in ("normalize", "crop", "preprocess"):
            payload = {"operation": operation, "image_base64": image_input()}
            if operation == "crop":
                payload["box"] = [0, 0, 0.5, 0.5]
            response = client.post("/v1/compute", headers=HEADERS, json=payload)
            assert response.status_code == 200
            result = response.json()["result"]
            assets = result["assets"] if operation == "preprocess" else [result]
            for asset in assets:
                raw = base64.b64decode(asset["image_base64"])
                assert hashlib.sha256(raw).hexdigest() == asset["sha256"]
                with Image.open(io.BytesIO(raw)) as decoded:
                    assert decoded.size == (
                        (50, 40) if operation == "crop" else (100, 80)
                    )
            if operation == "preprocess":
                assert result["metrics"]["red_ratio"] > 0
                assert [a["kind"] for a in assets] == ["clean", "red_mask", "overlay"]
        unavailable = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={"operation": "recognize", "image_base64": image_input()},
        )
        assert unavailable.status_code == 503 and str(tmp_path) not in unavailable.text
        compare = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={"operation": "math_compare", "left": "2*(x+1)", "right": "2*x+2"},
        )
        assert compare.json()["result"] == {"equivalent": True, "verified": True}
        solve = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={"operation": "math_solve", "text": "解方程：2*x+3=11"},
        )
        assert solve.json()["result"] == {"answer": "x=4", "verified": True}


def test_recognition_uses_pool_rotation_and_schema_retry(tmp_path):
    pool = tmp_path / "pool.json"
    pool.write_text(
        json.dumps(
            [
                {
                    "base_url": f"http://pool{i}.test/v1",
                    "api_key": f"fixture-key-{i}",
                    "model": "Qwen",
                }
                for i in range(2)
            ]
        )
    )
    provider = ApiPoolProvider(pool)
    asyncio.run(provider._client.aclose())
    visited = []
    successful = 0
    fail = False

    def upstream(request):
        nonlocal successful
        if fail:
            raise RuntimeError("fixture-key-sensitive")
        visited.append(request.url.host)
        body = json.loads(request.content)
        assert body["model"] == "Qwen"
        if request.url.host == "pool0.test":
            return httpx.Response(503, json={"error": "fixture-key-0 must not leak"})
        successful += 1
        recognition = (
            {}
            if successful == 1
            else {
                "subject": "math",
                "question_type": "calculation",
                "question_text": "计算 1+1",
                "has_answer": False,
                "has_working": False,
                "has_teacher_annotation": False,
                "recognition_confidence": 0.9,
            }
        )
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(recognition)}}]}
        )

    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(secret=SECRET, pool_path=pool)
    app.state.provider = provider
    with TestClient(app) as client:
        response = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={"operation": "recognize", "image_base64": image_input()},
        )
        assert response.status_code == 200, response.text
        assert response.json()["result"]["recognition"]["subject"] == "数学"
        assert visited == ["pool0.test", "pool1.test", "pool0.test", "pool1.test"]
        assert "fixture-key" not in response.text
        fail = True
        failed = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={"operation": "recognize", "image_base64": image_input()},
        )
        assert failed.status_code == 503 and "fixture-key" not in failed.text


def test_secret_required():
    with pytest.raises(ValueError, match="CANGJIE_ALGORITHM_SECRET"):
        create_app(secret="short")


def test_stream_size_limit(monkeypatch):
    monkeypatch.setattr("service.MAX_REQUEST_BYTES", 32)
    with TestClient(create_app(secret=SECRET)) as client:
        response = client.post(
            "/v1/compute", headers=HEADERS, content=iter([b"x" * 20, b"x" * 20])
        )
        assert response.status_code == 413


def test_analysis_schema_math_and_multimodal(tmp_path, monkeypatch):
    written = []
    save = service.save_original

    def record_image(raw, path):
        written.append(path)
        return save(raw, path)

    monkeypatch.setattr(service, "save_original", record_image)
    pool = tmp_path / "analysis-pool.json"
    pool.write_text(
        json.dumps(
            [
                {
                    "base_url": "http://analysis.test/v1",
                    "api_key": "fixture-key-private",
                    "model": "Qwen",
                }
            ]
        )
    )
    provider = ApiPoolProvider(pool)
    asyncio.run(provider._client.aclose())
    state = {"mode": "good", "calls": 0, "images": 0}

    def upstream(request):
        state["calls"] += 1
        body = json.loads(request.content)
        assert body["model"] == "Qwen"
        content = body["messages"][-1]["content"]
        if isinstance(content, list):
            state["images"] += sum(part["type"] == "image_url" for part in content)
        if state["mode"] == "fail":
            return httpx.Response(503, json={"error": "fixture-key-private"})
        output = {
            "reference_steps": ["2*x=8", "x=4"],
            "final_answer": "x=999",
            "subject": "错误学科",
            "knowledge_points": ["方程"],
            "answer_verified": True,
        }
        if state["mode"] == "invalid":
            output["reference_steps"] = {"bad": "shape"}
        if state["mode"] == "empty":
            output["final_answer"] = ""
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(output)}}]}
        )

    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(secret=SECRET, pool_path=pool)
    app.state.provider = provider
    with TestClient(app) as client:

        def compute(**extra):
            return client.post(
                "/v1/compute",
                headers=HEADERS,
                json={"operation": "analyze", "text": "解方程：2*x+3=11", **extra},
            )

        response = compute(images_base64=[image_input()], student_steps=["x=3"])
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["analysis"]["final_answer"] == "x=4"
        assert result["analysis"]["answer_verified"] is True
        assert result["analysis"]["subject"] == "数学"
        assert result["reference_math_valid"] == [True, True]
        assert state["images"] == 1
        assert written and all(not path.exists() for path in written)
        choice = compute(options=[{"label": "A", "text": "4"}]).json()["result"]
        assert choice["analysis"]["answer_verified"] is False
        assert choice["reference_math_valid"] == [False, False]
        assert compute(images_base64=["bad"]).status_code == 422
        assert compute(text=" ").status_code == 422
        state["mode"] = "invalid"
        assert compute(subject="物理").status_code == 503
        state["mode"] = "empty"
        assert compute(subject="物理").status_code == 503
        state["mode"] = "fail"
        fallback = compute().json()["result"]["analysis"]
        assert fallback["answer_verified"] is True and fallback["final_answer"] == "x=4"
        failed = compute(subject="物理")
        assert failed.status_code == 503 and "fixture-key" not in failed.text
        assert (
            not {"app.db", "app.models", "app.main", "app.config"} & sys.modules.keys()
        )


def test_learning_task_remaining_budget_cancels_instead_of_returning_late_result(
    tmp_path,
):
    class Slow:
        cancelled = False

        async def close(self):
            pass

        async def generate_structured(self, *args, **kwargs):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    app = create_app(secret=SECRET, pool_path=tmp_path / "absent.json")
    with TestClient(app) as client:
        slow = Slow()
        app.state.provider = slow
        before = __import__("time").monotonic()
        response = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={
                "operation": "learning_task",
                "task_budget_ms": 25,
                "task_context": {
                    "question_id": "q1",
                    "question_text": "解方程2x+3=11",
                    "expected": "x=4",
                    "student_steps": ["2x=14"],
                },
                "task_action": {"kind": "hint"},
            },
        )
        assert response.status_code == 503 and "result" not in response.json()
        assert slow.cancelled and __import__("time").monotonic() - before < 2
        assert SECRET not in response.text


@pytest.mark.parametrize("budget", [0, 38001, True])
def test_task_budget_cannot_be_disabled_or_extended(tmp_path, budget):
    app = create_app(secret=SECRET, pool_path=tmp_path / "absent.json")
    with TestClient(app) as client:
        response = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={"operation": "learning_task", "task_budget_ms": budget},
        )
        assert response.status_code == 422
