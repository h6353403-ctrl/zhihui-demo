"""阿里云视觉智能开放平台 · 商品分割（SegmentCommodity），RPC 签名调用。"""
import base64
import datetime
import hashlib
import hmac
import json
import urllib.parse
import uuid

import httpx

from ..core.config import settings


def _percent_encode(s) -> str:
    return urllib.parse.quote(str(s), safe="-_.~")


def _rpc_signature(secret: str, method: str, params: dict) -> str:
    canonical = "&".join(f"{_percent_encode(k)}={_percent_encode(v)}" for k, v in sorted(params.items()))
    string_to_sign = f"{method}&%2F&{_percent_encode(canonical)}"
    h = hmac.new((secret + "&").encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(h.digest()).decode("utf-8")


async def segment_commodity(oss_image_url: str) -> str:
    """对上海 OSS 上的图片做商品抠图，返回透明背景图 URL。"""
    if not settings.ALIYUN_AK_ID or not settings.ALIYUN_AK_SECRET:
        raise RuntimeError("缺少阿里云 AK/SK，请检查 backend/.env")

    params = {
        "Format": "JSON",
        "Version": "2019-12-30",
        "AccessKeyId": settings.ALIYUN_AK_ID,
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "SignatureVersion": "1.0",
        "SignatureNonce": str(uuid.uuid4()),
        "Action": "SegmentCommodity",
        "ImageURL": oss_image_url,
    }
    params["Signature"] = _rpc_signature(settings.ALIYUN_AK_SECRET, "POST", params)

    body = "&".join(f"{_percent_encode(k)}={_percent_encode(v)}" for k, v in params.items())
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            settings.SEGMENT_ENDPOINT,
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    data = resp.json()
    if resp.status_code != 200 or "Data" not in data:
        raise RuntimeError(f"抠图失败（{resp.status_code}）：{json.dumps(data, ensure_ascii=False)[:300]}")
    return data["Data"].get("ImageURL", "")
