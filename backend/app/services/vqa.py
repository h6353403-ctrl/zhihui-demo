"""VLM 视觉质检（Qwen-VL，DashScope 国际版）。

看图判断三个维度：Logo 完整性、文字越界/乱码、画面调性统一。
"""
import asyncio

import httpx

from .jsonutil import extract_json


async def visual_qa(
    base_url: str,
    api_key: str,
    model: str,
    image_url: str,
    style_name: str,
    style_prompt: str,
    retries: int = 2,
):
    if not api_key:
        raise RuntimeError("缺少 Qwen-VL API Key，请检查 backend/.env")

    prompt = f"""你是小红书品牌图文质检员。请仔细观察这张封面图，从以下三个维度判断质量：

1. Logo/品牌元素完整性：图中是否有 Logo、品牌名或品牌标识出现变形、扭曲、残缺？若图中没有 Logo 或品牌文字，判 pass 并说明「未出现 Logo」。
2. 文字越界/乱码：图中文字是否有越界、被裁切、乱码、笔画残缺、重叠遮挡？若图中没有文字，判 pass 并说明「无文字」。
3. 画面调性统一：画面整体风格是否符合「{style_name}（{style_prompt}）」的调性？是否出现与调性明显冲突的元素？

判定标准：level 只能取 pass（合格）、review（可疑，需人工复核）、block（明显问题）。
只输出 JSON，不要任何解释或 markdown：
{{"items":[{{"item":"Logo完整性","level":"pass","note":"30字内"}},{{"item":"文字越界","level":"pass","note":"30字内"}},{{"item":"调性统一","level":"pass","note":"30字内"}}]}}"""

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
    }
    last_err = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                    json=payload,
                )
        except httpx.HTTPError as e:
            last_err = RuntimeError(f"VLM 请求网络错误：{e}")
        else:
            if resp.status_code == 200:
                data = resp.json()
                text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                if not text:
                    raise RuntimeError("VLM 返回为空")
                return extract_json(text)
            if 500 <= resp.status_code < 600:
                last_err = RuntimeError(f"VLM 服务暂不可用（{resp.status_code}）：{resp.text[:300]}")
            else:
                raise RuntimeError(f"VLM 请求失败（{resp.status_code}）：{resp.text[:300]}")
        if attempt < retries:
            await asyncio.sleep(2 ** attempt)
    raise last_err
