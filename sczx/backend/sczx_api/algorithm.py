"""Bounded authenticated calls to the standalone Python computation service."""
import base64
import hashlib
import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from .task_policy import TaskBudgetExceeded


def compute(payload, timeout=200, budget=None):
    if budget is not None:budget.check('algorithm_start')
    endpoint = os.environ.get('SCZX_ALGORITHM_URL', 'http://127.0.0.1:8012')
    secret = os.environ.get('SCZX_ALGORITHM_SECRET', '')
    if len(secret.encode()) < 32 or not endpoint.startswith('http://127.0.0.1:'):
        raise HTTPException(503, '内部算法服务未配置')
    try:
        parsed = urlsplit(endpoint)
        if not parsed.port or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise ValueError
    except ValueError:
        raise HTTPException(503, '内部算法地址无效') from None
    try:
        with httpx.Client(trust_env=False, timeout=timeout) as client:
            with client.stream('POST', endpoint + '/v1/compute', json=payload, headers={'Authorization': 'Bearer ' + secret}) as response:
                if budget is not None:budget.check('algorithm_response')
                if response.status_code != 200:
                    code, detail = {502: (502, '语音计算暂时不可用'), 422: (422, '图片或计算数据无效')}.get(response.status_code, (503, '内部算法计算暂时不可用'))
                    raise HTTPException(code, detail)
                data = bytearray()
                chunks=iter(response.iter_bytes())
                while True:
                    if budget is not None:budget.check('algorithm_read')
                    chunk=next(chunks,None)
                    if budget is not None:budget.check('algorithm_read')
                    if chunk is None:break
                    data.extend(chunk)
                    if len(data) > 128 * 1024 * 1024:
                        raise HTTPException(503, '算法结果过大')
                import json
                result = json.loads(data)
                if result.get('operation') != payload['operation']:
                    raise HTTPException(503, '算法结果不匹配')
                if not isinstance(result['result'], dict): raise ValueError
                return result['result']
    except (HTTPException,TaskBudgetExceeded):
        raise
    except Exception:
        raise HTTPException(503, '内部算法服务暂时不可用') from None


def image_bytes(asset):
    try:
        data = base64.b64decode(asset['image_base64'], validate=True)
        if not data or len(data) > 64 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != asset['sha256']:
            raise ValueError
        return data
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, '算法图片校验失败') from None
