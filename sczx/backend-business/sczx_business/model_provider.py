"""按能力选池；网络协议与教学业务隔离。"""
import asyncio
import base64
import json
import math
import os
import time
from pathlib import Path

import httpx
from pydantic import ValidationError

from .ai_schemas import CAPABILITIES, CAPABILITY_LABELS, OCRResult, GuidanceResult, RankingResult


class ModelError(Exception):
    def __init__(self, message, *, retryable=False, retry_after=2):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


class ModelProvider:
    def __init__(self):
        self.cursors = {}
        self.cooldowns = {}
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(100, connect=15), trust_env=False)

    def entries(self, capability):
        if capability == "document_parse": return [{"name": "文档解析", "model": "Document parser", "transport": "algorithm"}]
        if capability == "retrieval":
            return [{"name": "BM25 中文检索", "model": "BM25", "transport": "algorithm"}]
        if os.getenv("SCZX_MODEL_TRANSPORT", "codex_cli") == "codex_cli":
            from .codex_provider import MODEL, SUPPORTED
            return [{"name": "Codex CLI · low", "model": MODEL, "transport": "codex_cli"}] if capability in SUPPORTED else []
        path = Path(os.getenv("SCZX_MODEL_CONFIG", str(Path(__file__).resolve().parents[1] / "config/model_pool.json")))
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text())
            entries = payload.get("entries", [])
            return [entry for entry in entries if not entry.get("disabled") and capability in entry.get("capabilities", []) and entry.get("model") and entry.get("base_url") and os.getenv(entry.get("api_key_env", ""))]
        except (ValueError, TypeError, AttributeError):
            raise ModelError("模型配置格式无效，请检查配置文件。")

    def configured(self):
        return {cap: [{"name": e.get("name", "外部服务"), "model": e["model"]} for e in self.entries(cap)] for cap in CAPABILITIES}

    async def close(self):
        await self.client.aclose()

    async def call(self, capability, data, *, file=None, request_id=None):
        entries = self.entries(capability)
        if not entries and os.getenv("SCZX_MODEL_TRANSPORT", "codex_cli") == "codex_cli":
            from .codex_provider import UNSUPPORTED
            raise ModelError(UNSUPPORTED.get(capability, "Codex CLI 暂不可用。"))
        if not entries:
            raise ModelError(f"{CAPABILITY_LABELS.get(capability, '此能力')}尚未配置可用服务。")
        start = self.cursors.get(capability, 0) % len(entries)
        self.cursors[capability] = start + 1
        ordered = entries[start:] + entries[:start]
        last_error = None
        for entry in ordered:
            pool_id = (entry.get("base_url", "codex_cli"), entry.get("api_key_env"), capability, entry["model"])
            if self.cooldowns.get(pool_id, 0) > time.monotonic():
                last_error = ModelError("服务正在限流冷却，请稍后重试。", retryable=True, retry_after=max(2, self.cooldowns[pool_id] - time.monotonic()))
                continue
            try:
                result = await self._call(entry, capability, data, file, request_id)
                return result, entry["model"], entry.get("name", "外部服务")
            except ModelError as error:
                error.model = entry["model"]
                error.provider = entry.get("name", "外部服务")
                last_error = error
                if "限流" in str(error):
                    self.cooldowns[pool_id] = time.monotonic() + error.retry_after
                # Other compatible entries may still be available after credential errors.
        raise last_error or ModelError("没有可用模型服务。")

    async def _call(self, entry, capability, data, file, request_id=None):
        if capability == "document_parse":
            from .document_parser import parse_material
            return await asyncio.to_thread(parse_material, data["materialId"], request_id)
        if capability == 'retrieval':
            from .retrieval import retrieve
            spec={k:data[k] for k in ('query','filters','context','includePrerequisites','limit') if k in data}
            result=retrieve(spec,data.get('documents',[]),data.get('knowledge',[]))
            candidates=result.pop('candidateItems',[])
            result['rerankAttempted']=bool(data.get('rerank') and candidates)
            if data.get('rerank') and candidates:
                started=time.monotonic()
                try:
                    compact=[]
                    for item in candidates:
                        fields={k:item.get(k) for k in ('title','grade','subject','knowledgeIds','experience')}
                        fields['content']=item.get('content','')[:5000]
                        compact.append({'id':item['id'],'text':json.dumps(fields,ensure_ascii=False)[:10000]})
                    ranking,model,source=await self.call('rerank',{'query':data['query'],'context':spec.get('context',{}),'filters':spec.get('filters',{}),'candidates':compact},request_id=request_id)
                    ranking=RankingResult.model_validate({'ranking':ranking['ranking']}).model_dump()['ranking']
                    expected={item['id'] for item in candidates};ids=[item['id'] for item in ranking];scores=[item['score'] for item in ranking]
                    if len(ids)!=len(expected) or set(ids)!=expected or len(set(ids))!=len(ids) or scores!=sorted(scores,reverse=True):raise ValueError('invalid candidate permutation')
                    by_id={item['id']:item for item in candidates}
                    result['items']=[{**by_id[item['id']],'relevanceScore':item['score']} for item in ranking][:spec.get('limit',8)]
                    result.update(rerankApplied=True,rerankModel=model,method='field-bm25+knowledge+context+codex')
                except (ModelError,ValidationError,ValueError,KeyError,TypeError) as error:
                    result['warning']='语义重排未完成，已完整保留本次BM25结果。'
                    result['rerankFailure']=type(error).__name__
                result['rerankElapsedMs']=round((time.monotonic()-started)*1000,3)
            return result
        if entry.get("transport") == "codex_cli":
            from .codex_provider import call
            return await call(capability, data, file)
        paths = {"text": "/chat/completions", "ocr": "/chat/completions", "embedding": "/embeddings", "rerank": "/rerank", "asr": "/audio/transcriptions", "tts": "/audio/speech"}
        chat_rerank = capability == "rerank" and entry.get("protocol") == "chat_rerank"
        if chat_rerank: paths["rerank"] = "/chat/completions"
        url = entry["base_url"].rstrip("/") + entry.get("paths", {}).get(capability, paths[capability])
        headers = {"Authorization": "Bearer " + os.environ[entry["api_key_env"]]}
        try:
            seconds = float(entry.get("timeout_seconds", 100))
            if not math.isfinite(seconds) or not 1 <= seconds <= 120:
                raise ValueError("timeout")
        except (ValueError, TypeError):
            raise ModelError("模型请求超时配置需为1至120秒。") from None
        timeout = httpx.Timeout(seconds, connect=min(15, seconds))
        if request_id:
            headers["X-Request-ID"] = request_id
        body = {"model": entry["model"]}
        schema = None
        if capability in ("text", "ocr") or chat_rerank:
            schema = RankingResult if chat_rerank else OCRResult if capability == "ocr" else GuidanceResult
            if data.get("examCandidate"):
                from .exam_schemas import ExamCandidate
                schema=ExamCandidate
            from .subject_prompts import instruction as subject_instruction
            instruction = ("你是图像文字转录器，只返回图中实际可见内容。text不得出现讲解、思考提示、追问、图外背景、学科或年级推断；空白答案保留为空；uncertainties只记录看不清的字符。" if capability in ("ocr","document_ocr") else subject_instruction(data))
            if chat_rerank:
                instruction = "你是教学经验检索的语义重排器。根据query评价candidates与教学困难的相关程度，排序后返回JSON。每个候选ID必须恰好出现一次，score在0到1之间，按score降序。分值是本组候选的相对相关程度，不是正确概率。只使用给定候选，不增加新ID。"
            instruction += "\nSchema:" + json.dumps(schema.model_json_schema(), ensure_ascii=False)
            if data.get("repairStructure"):
                instruction += "\n前次输出未通过结构校验。本次必须重新组织为完整合法JSON，包含Schema所有必需字段。"
            if capability == "ocr":
                if not file or not file[2].startswith("image/"):
                    raise ModelError("识别需要已上传的原始题图。")
                content = [{"type": "text", "text": "逐字识别题目，保留原文、选项、公式和学科符号，区分题干与学生答案；模糊处列入uncertainties。"}, {"type": "image_url", "image_url": {"url": f"data:{file[2]};base64,{base64.b64encode(file[1]).decode()}"}}]
            else:
                content = json.dumps(data, ensure_ascii=False)
                if not chat_rerank:
                    instruction += "\n先给可操作的提示，再分步解释。mathClaims仅列可通过符号等价直接核对的等式左右表达式；不要以模型自述代替校验。"
            body["messages"] = [{"role": "system", "content": instruction}, {"role": "user", "content": content}]
            if entry.get("json_mode", True):
                body["response_format"] = {"type": "json_object"}
        elif capability == "embedding":
            body["input"] = data["texts"]
        elif capability == "rerank":
            body.update(query=data["query"], documents=[item["text"] for item in data["candidates"]])
        elif capability == "tts":
            body.update(input=data["text"], voice=data.get("voice") or entry.get("voice", "alloy"), response_format="mp3")
        try:
            if capability == "asr":
                if not file or not file[2].startswith("audio/"):
                    raise ModelError("转写需要已上传的音频。")
                response = await self.client.post(url, headers=headers, data={"model": entry["model"]}, files={"file": file}, timeout=timeout)
            else:
                response = await self.client.post(url, headers=headers, json=body, timeout=timeout)
                if schema and response.status_code in (400, 422) and "response_format" in body:
                    body.pop("response_format")
                    response = await self.client.post(url, headers=headers, json=body, timeout=timeout)
            if response.status_code >= 400:
                status = response.status_code
                message = "服务限流，请稍后重试。" if status == 429 else "模型认证失败，请检查配置。" if status in (401,403) else "模型或接口不受支持，请检查能力配置。" if status in (400,404,405,422) else "外部模型服务暂时不可用。"
                delay = response.headers.get("retry-after", "2")
                delay = min(60, max(2, float(delay))) if delay.replace(".", "", 1).isdigit() else 2
                raise ModelError(message, retryable=status == 429 or status >= 500, retry_after=delay)
            if capability == "tts":
                audio = response.content
                has_audio_header = audio.startswith((b"ID3", b"RIFF", b"OggS", b"fLaC")) or (len(audio) > 2 and audio[0] == 255 and audio[1] & 224 == 224)
                if not has_audio_header or "json" in response.headers.get("content-type", ""):
                    raise ModelError("语音合成没有返回有效音频。")
                return {"audio": response.content, "contentType": response.headers.get("content-type", "audio/mpeg")}
            payload = response.json()
            if schema:
                raw = payload["choices"][0]["message"]["content"]
                if not isinstance(raw, str):
                    raise ModelError("模型未返回可解析的文本结果。", retryable=True)
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
                result = schema.model_validate_json(raw).model_dump()
                if chat_rerank:
                    ids = [item["id"] for item in result["ranking"]]
                    expected = [item["id"] for item in data["candidates"]]
                    scores = [item["score"] for item in result["ranking"]]
                    if len(ids) != len(expected) or set(ids) != set(expected) or len(set(ids)) != len(ids) or scores != sorted(scores, reverse=True):
                        raise ValueError("LLM rerank candidates")
                    result.update(candidateCount=len(expected), method="llm", scoreMeaning="本组候选的相对相关程度，不是正确概率")
                return result
            if capability == "embedding":
                values = sorted(payload["data"], key=lambda item: item["index"])
                vectors = [item["embedding"] for item in values]
                if len(vectors) != len(data["texts"]) or [item["index"] for item in values] != list(range(len(vectors))) or not vectors or not vectors[0]:
                    raise ValueError("vector count")
                dim = len(vectors[0])
                if any(len(v) != dim or any(isinstance(n, bool) or not isinstance(n, (int,float)) or not math.isfinite(n) for n in v) for v in vectors):
                    raise ValueError("vector shape")
                return {"vectors": vectors, "dimensions": dim, "count": len(vectors)}
            if capability == "rerank":
                results = payload.get("results", payload.get("data"))
                candidates = data["candidates"]
                indexes = [item["index"] for item in results]
                if len(set(indexes)) != len(indexes) or any(isinstance(i,bool) or not isinstance(i,int) or i < 0 or i >= len(candidates) for i in indexes) or not indexes:
                    raise ValueError("rerank indexes")
                ranked = []
                for item in results:
                    score = item.get("relevance_score", item.get("score"))
                    if isinstance(score,bool) or not isinstance(score,(float,int)) or not math.isfinite(score): raise ValueError("rerank score")
                    ranked.append({"id": candidates[item["index"]]["id"], "score": score})
                return {"ranking": ranked, "candidateCount": len(candidates)}
            text = payload["text"]
            if not isinstance(text,str) or not text.strip(): raise ValueError("empty transcript")
            result = {"text": text.strip()}
            if isinstance(payload.get("segments"), list):
                segments = []
                for item in payload["segments"]:
                    start, end = item.get("start"), item.get("end")
                    if not all(isinstance(n, (int,float)) and not isinstance(n,bool) and math.isfinite(n) for n in (start,end)) or not 0 <= start <= end or not isinstance(item.get("text"),str):
                        raise ValueError("ASR timestamps")
                    segments.append({"start":start,"end":end,"text":item["text"]})
                result["segments"] = segments
            return result
        except ModelError:
            raise
        except httpx.TransportError:
            raise ModelError("连接模型服务超时或网络不可用，请重试。", retryable=True) from None
        except (ValueError, KeyError, TypeError, IndexError, ValidationError):
            raise ModelError("模型返回的内容不符合结果结构。", retryable=True) from None
