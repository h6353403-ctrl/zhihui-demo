import base64
import hashlib
import hmac

from app.services import segment
from app.services import oss


# ---------- 阿里云 RPC 签名 ----------

def test_percent_encode():
    assert segment._percent_encode("abc") == "abc"
    assert segment._percent_encode("a b") == "a%20b"
    assert segment._percent_encode("a+b") == "a%2Bb"
    # 保留字符不编码
    assert segment._percent_encode("-_.~") == "-_.~"


def test_rpc_signature_deterministic():
    params = {
        "Format": "JSON",
        "Version": "2019-12-30",
        "AccessKeyId": "ak",
        "Action": "SegmentCommodity",
        "ImageURL": "https://example.com/a.png",
    }
    s1 = segment._rpc_signature("secret", "POST", params)
    s2 = segment._rpc_signature("secret", "POST", params)
    assert s1 == s2
    # HMAC-SHA1 -> base64 固定 28 字符，且可解码
    assert len(s1) == 28
    base64.b64decode(s1)


def test_rpc_signature_matches_reference():
    """用独立写法验证签名值：sorted + quote + sha1 + b64。"""
    secret = "test-secret"
    params = {"b": "2", "a": "1", "Action": "Do"}
    got = segment._rpc_signature(secret, "POST", params)

    def ref_encode(s):
        from urllib.parse import quote

        return quote(str(s), safe="-_.~")

    canonical = "&".join(
        f"{ref_encode(k)}={ref_encode(v)}" for k, v in sorted(params.items())
    )
    string_to_sign = f"POST&%2F&{ref_encode(canonical)}"
    expected = base64.b64encode(
        hmac.new((secret + "&").encode(), string_to_sign.encode(), hashlib.sha1).digest()
    ).decode()
    assert got == expected


# ---------- OSS 签名 ----------

def test_oss_signature_deterministic():
    s1 = oss._oss_signature("secret", "PUT", "image/png", "Mon, 01 Jan 2024 00:00:00 GMT", "/bucket/key.png")
    s2 = oss._oss_signature("secret", "PUT", "image/png", "Mon, 01 Jan 2024 00:00:00 GMT", "/bucket/key.png")
    assert s1 == s2
    base64.b64decode(s1)


def test_oss_signature_matches_reference():
    secret = "test-secret"
    method, content_type, date, resource = "PUT", "image/png", "Mon, 01 Jan 2024 00:00:00 GMT", "/bucket/k.png"
    string_to_sign = f"{method}\n\n{content_type}\n{date}\n{resource}"
    expected = base64.b64encode(
        hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()
    ).decode()
    assert oss._oss_signature(secret, method, content_type, date, resource) == expected


def test_new_object_key():
    key = oss.new_object_key("seg", "png")
    assert key.startswith("seg/")
    assert key.endswith(".png")
    assert len(key) == len("seg/") + 32 + len(".png")


def test_presigned_get_url_encodes_signature(monkeypatch):
    monkeypatch.setattr(oss.settings, "ALIYUN_AK_ID", "akid")
    monkeypatch.setattr(oss.settings, "ALIYUN_AK_SECRET", "sk")
    monkeypatch.setattr(oss.settings, "OSS_BUCKET", "mybucket")
    monkeypatch.setattr(oss.settings, "OSS_ENDPOINT", "oss-cn-shanghai.aliyuncs.com")

    url = oss.presigned_get_url("composite/x.jpg", expires=600)
    assert url.startswith("https://mybucket.oss-cn-shanghai.aliyuncs.com/composite/x.jpg?")
    assert "OSSAccessKeyId=akid" in url
    assert "Expires=" in url
    # Signature 参数里的 base64 特殊字符必须被 URL 编码
    sig_part = [p for p in url.split("&") if p.startswith("Signature=")][0]
    assert "+" not in sig_part and "/" not in sig_part and "=" not in sig_part[len("Signature="):]
