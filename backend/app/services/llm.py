"""OpenAI 兼容 Chat Completions 调用（DeepSeek / GLM 均适用）。

- 统一封装请求，返回解析后的 JSON 对象
- 对 5xx 与网络错误做指数退避重试（4xx 与解析错误不重试，避免无谓扣费）
- JSON 提取走 jsonutil，容错 markdown、多对象、尾逗号等
"""
import asyncio
import json

import httpx

from .jsonutil import extract_json

__all__ = ["chat_completion", "extract_json"]


async def chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    max_tokens: int = 1000,
    retries: int = 2,
):
    if not api_key:
        raise RuntimeError("缺少模型 API Key，请检查 backend/.env")

    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = await _post(base_url, api_key, model, prompt, max_tokens)
        except httpx.HTTPError as e:
            last_err = RuntimeError(f"模型请求网络错误：{e}")
        else:
            if resp.status_code == 200:
                data = resp.json()
                text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                if not text:
                    raise RuntimeError("模型返回为空：" + json.dumps(data, ensure_ascii=False)[:200])
                return extract_json(text)

            if 500 <= resp.status_code < 600:
                last_err = RuntimeError(f"模型服务暂不可用（{resp.status_code}）：{resp.text[:300]}")
            else:
                # 4xx 通常是凭证/参数错误，重试无意义
                raise RuntimeError(f"模型请求失败（{resp.status_code}）：{resp.text[:300]}")

        if attempt < retries:
            await asyncio.sleep(2 ** attempt)

    raise last_err


async def _post(base_url: str, api_key: str, model: str, prompt: str, max_tokens: int):
    async with httpx.AsyncClient(timeout=180) as client:
        return await client.post(
            f"{base_url}/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是结构化输出引擎。只输出一个合法 JSON 对象，不要 markdown 代码块，不要任何解释或前言。",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
        )
