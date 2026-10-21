from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageDraw
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
MODEL_KEYS = ("model", "model_name", "default_model", "primary_model", "chat_model", "vision_model")
LOGICAL_MODEL = "Qwen"


@dataclass(slots=True)
class PoolEntry:
    base_url: str
    credential: str
    model: str
    entry_id: str
    supports_text: bool = True
    supports_image: bool = True
    supports_json_mode: bool | None = None
    cooldown_until: float = 0


@dataclass
class PoolState:
    global_index: int = 0
    text_index: int = 0
    vision_index: int = 0
    last_entry: str | None = None
    last_status: str = "idle"
    calls: list[str] = field(default_factory=list)


class ApiPoolUnavailable(RuntimeError):
    pass




def _find_entries(value: object) -> list[PoolEntry]:
    found: list[PoolEntry] = []

    def visit(node: object) -> None:
        if isinstance(node, dict):
            if node.get("disabled") is True:
                return
            base_url = next(
                (node.get(k) for k in ("base_url", "url", "endpoint", "api_base") if node.get(k)), None
            )
            credential = next((node.get(k) for k in ("key", "api_key", "token") if node.get(k)), None)
            model = next((node.get(k) for k in MODEL_KEYS if node.get(k)), None)
            if (
                isinstance(base_url, str)
                and base_url
                and isinstance(credential, str)
                and credential
                and isinstance(model, str)
                and model
            ):
                fingerprint = hashlib.sha256(json.dumps(node, sort_keys=True).encode()).hexdigest()[:12]
                found.append(PoolEntry(base_url.rstrip("/"), credential, model, fingerprint))
                return
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return found


class ApiPoolProvider:
    def __init__(self, path: str | Path, allowed_hosts: set[str] | None = None, *, trust_env: bool = True):
        self.path = Path(path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.entries = _find_entries(payload)
        if not self.entries:
            raise ValueError("API池中没有可用条目")
        invalid_hosts = [
            entry.entry_id
            for entry in self.entries
            if allowed_hosts is not None and urlparse(entry.base_url).hostname not in allowed_hosts
        ]
        if invalid_hosts:
            raise ValueError(f"API池包含非许可提供商: count={len(invalid_hosts)}")
        invalid_models = [entry.entry_id for entry in self.entries if entry.model != LOGICAL_MODEL]
        if invalid_models:
            raise ValueError(f"API池包含非{LOGICAL_MODEL}模型配置: count={len(invalid_models)}")
        self.text_entries = self.entries.copy()
        self.vision_entries = self.entries.copy()
        self.state = PoolState()
        self._lock = asyncio.Lock()
        self._probe_lock = asyncio.Lock()
        self._probed = False
        self._client = httpx.AsyncClient(timeout=90, trust_env=trust_env)

    async def close(self) -> None:
        await self._client.aclose()

    async def _next_entry(self, vision: bool, excluded: set[str] | None = None) -> PoolEntry | None:
        """从全局游标取得下一个Key；文本和图片请求共享同一个循环位置。"""
        eligible = self.vision_entries if vision else self.text_entries
        eligible_ids = {entry.entry_id for entry in eligible}
        excluded_ids = excluded or set()
        async with self._lock:
            total = len(self.entries)
            if not total:
                return None
            start = self.state.global_index % total
            for offset in range(total):
                index = (start + offset) % total
                entry = self.entries[index]
                if entry.entry_id not in eligible_ids or entry.entry_id in excluded_ids:
                    continue
                self.state.global_index = (index + 1) % total
                self.state.text_index = self.state.global_index % max(1, len(self.text_entries))
                self.state.vision_index = self.state.global_index % max(1, len(self.vision_entries))
                return entry
        return None

    async def _ordered(self, vision: bool) -> list[PoolEntry]:
        """保留给健康检查和测试的有序视图；第一次始终是全局下一Key。"""
        entries = self.vision_entries if vision else self.text_entries
        first = await self._next_entry(vision)
        if first is None:
            return []
        start = entries.index(first)
        return entries[start:] + entries[:start]

    @staticmethod
    def _url(entry: PoolEntry) -> str:
        base = entry.base_url.rstrip("/")
        return base + "/chat/completions" if not base.endswith("/chat/completions") else base

    async def _request_entry(
        self,
        entry: PoolEntry,
        messages: list[dict[str, Any]],
        json_mode: bool = False,
    ) -> str:
        request_payload: dict[str, Any] = {
            "model": entry.model,
            "messages": messages,
            "temperature": 0.1,
        }
        if json_mode:
            request_payload["response_format"] = {"type": "json_object"}
            # 当前Qwen结构化任务不需要长推理。vLLM默认思考会把输出额度消耗在reasoning，
            # 导致content为空并显著拖慢拍题识别。
            request_payload["chat_template_kwargs"] = {"enable_thinking": False}
            request_payload["max_tokens"] = 2048
        headers = {"Authorization": f"Bearer {entry.credential}", "Content-Type": "application/json"}
        response: httpx.Response | None = None
        if json_mode and entry.supports_json_mode is not False:
            try:
                # 这里只做能力协商。部分兼容网关接收response_format后不报400却一直挂起，
                # 因此用短探测超时并记住结果，后续请求不再重复等待。
                response = await self._client.post(
                    self._url(entry),
                    headers=headers,
                    json=request_payload,
                    timeout=15,
                )
                if response.status_code == 400:
                    entry.supports_json_mode = False
                    response = None
                else:
                    entry.supports_json_mode = True
            except httpx.TimeoutException:
                entry.supports_json_mode = False
                response = None
        if response is None:
            request_payload.pop("response_format", None)
            response = await self._client.post(
                self._url(entry),
                headers=headers,
                json=request_payload,
            )
        if response.status_code == 429:
            retry = response.headers.get("Retry-After", "30")
            entry.cooldown_until = time.time() + (float(retry) if retry.replace(".", "", 1).isdigit() else 30)
            raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content)

    async def _request(
        self,
        messages: list[dict[str, Any]],
        vision: bool = False,
        json_mode: bool = False,
    ) -> tuple[str, PoolEntry]:
        attempted = 0
        eligible = self.vision_entries if vision else self.text_entries
        visited: set[str] = set()
        while len(visited) < len(eligible):
            entry = await self._next_entry(vision, visited)
            if entry is None:
                break
            visited.add(entry.entry_id)
            if entry.cooldown_until > time.time():
                continue
            attempted += 1
            try:
                content = await self._request_entry(entry, messages, json_mode=json_mode)
                self.state.last_entry = entry.entry_id
                self.state.last_status = "ok"
                self.state.calls = (self.state.calls + [entry.entry_id])[-20:]
                return str(content), entry
            except (httpx.HTTPError, KeyError, ValueError, TypeError):
                continue
        self.state.last_status = "unavailable"
        raise ApiPoolUnavailable(f"AI_POOL_UNAVAILABLE: attempted={attempted}")

    async def generate_text(self, prompt: str, system: str = "你是错题帮教学助手。") -> str:
        content, _ = await self._request(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
        return content

    async def generate_structured(self, prompt: str, schema: type[T], system: str = "只返回合法JSON。") -> T:
        text, _ = await self._request(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": prompt
                    + "\nJSON Schema:\n"
                    + json.dumps(schema.model_json_schema(), ensure_ascii=False),
                },
            ],
            json_mode=True,
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
        return schema.model_validate_json(cleaned)

    async def generate_multimodal(
        self,
        prompt: str,
        images: list[bytes],
        schema: type[T],
        system: str = "只输出JSON；区分印刷题干、学生书写和教师批注；不确定时返回空值。",
    ) -> T:
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": prompt
                + "\nJSON Schema:\n"
                + json.dumps(schema.model_json_schema(), ensure_ascii=False),
            }
        ]
        for raw in images:
            encoded = base64.b64encode(raw).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}})
        text, _ = await self._request(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            vision=True,
            json_mode=True,
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
        return schema.model_validate_json(cleaned)

    async def probe(self) -> dict[str, Any]:
        async with self._probe_lock:
            if self._probed:
                return self.health_check()
            result = await self._probe_entries()
            self._probed = True
            return result

    async def _probe_entries(self) -> dict[str, Any]:
        text_ok: list[PoolEntry] = []
        vision_ok: list[PoolEntry] = []
        image = Image.new("RGB", (256, 128), "white")
        ImageDraw.Draw(image).text((24, 48), "Question: 2 + 3 = ?", fill="black")
        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        encoded = base64.b64encode(image_buffer.getvalue()).decode()
        for entry in self.entries:
            try:
                answer = await self._request_entry(
                    entry,
                    [
                        {"role": "system", "content": "只回答结果。"},
                        {"role": "user", "content": "2+3等于多少？"},
                    ],
                )
                if "5" in answer:
                    text_ok.append(entry)
                vision_answer = await self._request_entry(
                    entry,
                    [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "读取图片算式并只回答结果数字。"},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{encoded}"},
                                },
                            ],
                        }
                    ],
                )
                if "5" in vision_answer:
                    vision_ok.append(entry)
            except (httpx.HTTPError, KeyError, ValueError, TypeError):
                pass
        # 探测只是启动期的能力提示，不能因为一次网络抖动把真实调用池永久清空。
        # 全部探测失败时保留启动时加载的候选条目，让正式请求继续逐个轮询并自行容错。
        self.text_entries = text_ok or self.entries.copy()
        self.vision_entries = vision_ok or self.entries.copy()
        self.state.last_status = "ok" if text_ok and vision_ok else "degraded"
        return self.health_check()

    def health_check(self) -> dict[str, Any]:
        return {
            "logical_model": LOGICAL_MODEL,
            "actual_models": sorted({e.model for e in self.entries}),
            "total_entries": len(self.entries),
            "unique_keys": len({e.credential for e in self.entries}),
            "text_entries": len(self.text_entries),
            "vision_entries": len(self.vision_entries),
            "global_index": self.state.global_index,
            "text_index": self.state.text_index,
            "vision_index": self.state.vision_index,
            "last_entry": self.state.last_entry,
            "last_status": self.state.last_status,
            "recent_rotation": self.state.calls,
        }
