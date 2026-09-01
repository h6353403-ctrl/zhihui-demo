"""阿里云 OSS 上传与预签名（手写 V1 签名，避免额外 SDK 依赖）。

策略：bucket 保持私有（安全默认），抠图前用「预签名 GET URL」让视觉智能临时下载。
"""
import base64
import datetime
import hashlib
import hmac
import time
import urllib.parse
import uuid

import httpx

from ..core.config import settings


def _oss_signature(secret: str, method: str, content_type: str, date: str, resource: str) -> str:
    string_to_sign = f"{method}\n\n{content_type}\n{date}\n{resource}"
    h = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(h.digest()).decode("utf-8")


async def upload_to_oss(content: bytes, object_key: str, content_type: str = "image/png") -> str:
    """上传文件到 OSS（对象保持私有），返回 object_key。"""
    if not settings.ALIYUN_AK_ID or not settings.ALIYUN_AK_SECRET or not settings.OSS_BUCKET:
        raise RuntimeError("缺少阿里云 OSS 配置，请检查 backend/.env")

    date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    resource = f"/{settings.OSS_BUCKET}/{object_key}"
    signature = _oss_signature(settings.ALIYUN_AK_SECRET, "PUT", content_type, date, resource)

    url = f"https://{settings.OSS_BUCKET}.{settings.OSS_ENDPOINT}/{object_key}"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.put(
            url,
            content=content,
            headers={
                "Content-Type": content_type,
                "Date": date,
                "Authorization": f"OSS {settings.ALIYUN_AK_ID}:{signature}",
            },
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"OSS 上传失败（{resp.status_code}）：{resp.text[:300]}")
    return object_key


def presigned_get_url(object_key: str, expires: int = 600) -> str:
    """生成 OSS 预签名 GET URL，供阿里云视觉智能服务端临时下载私有对象。"""
    expires_ts = int(time.time()) + expires
    resource = f"/{settings.OSS_BUCKET}/{object_key}"
    string_to_sign = f"GET\n\n\n{expires_ts}\n{resource}"
    h = hmac.new(
        settings.ALIYUN_AK_SECRET.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1
    )
    signature = base64.b64encode(h.digest()).decode("utf-8")
    # Signature 是 base64，含 +/=，需 URL 编码后放入 query
    encoded_sig = urllib.parse.quote(signature, safe="")
    return (
        f"https://{settings.OSS_BUCKET}.{settings.OSS_ENDPOINT}/{object_key}"
        f"?OSSAccessKeyId={settings.ALIYUN_AK_ID}&Expires={expires_ts}&Signature={encoded_sig}"
    )


def new_object_key(prefix: str = "seg", ext: str = "png") -> str:
    return f"{prefix}/{uuid.uuid4().hex}.{ext}"
