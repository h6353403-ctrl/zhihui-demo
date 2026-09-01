"""SeedDream 文生图（火山方舟 OpenAI 兼容 images/generations）。"""
import json

import httpx


async def generate_image(base_url: str, api_key: str, model: str, prompt: str, size: str) -> str:
    if not api_key:
        raise RuntimeError("缺少图像模型 API Key，请检查 backend/.env")
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{base_url}/images/generations",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "prompt": prompt,
                "size": size,
                "response_format": "url",
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"图像生成失败（{resp.status_code}）：{resp.text[:300]}")
    data = resp.json()
    first = (data.get("data") or [{}])[0]
    url = first.get("url") or (
        f"data:image/png;base64,{first['b64_json']}" if first.get("b64_json") else None
    )
    if not url:
        raise RuntimeError("图像生成未返回图片：" + json.dumps(data, ensure_ascii=False)[:200])
    return url
