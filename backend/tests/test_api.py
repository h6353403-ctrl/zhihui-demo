"""API 路由集成测试：用 TestClient + mock 外部服务，不依赖真实模型/云服务。

覆盖 8 个业务接口的请求校验、错误处理与字段返回，保证改路由逻辑时
不破坏既有契约。
"""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _png_bytes(size=(10, 10), color=(255, 0, 0, 255)):
    img = Image.new("RGBA", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------- 健康检查 ----------

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------- ① Brief 解析 ----------

def test_parse_ok_and_strips_visual_style(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {
            "brand": "花漾",
            "campaign": {"name": "秋冬", "period": "11.1-11.11"},
            "products": [],
            "selling_points": [],
            "target_audience": "",
            "tone": "",
            "must_include": [],
            "forbidden": [],
            "visual_style": {"keywords": []},
            "missing_fields": ["visual_style.keywords"],
            "confidence": 0.9,
        }

    monkeypatch.setattr("app.services.llm.chat_completion", fake_chat)
    r = client.post("/api/v1/parse", json={"brief": "测试 brief"})
    assert r.status_code == 200
    d = r.json()
    assert d["brand"] == "花漾"
    # 后处理：视觉风格字段与缺失项都被移除
    assert "visual_style" not in d
    assert d["missing_fields"] == []


def test_parse_model_error_returns_502(monkeypatch):
    async def fake_chat(*args, **kwargs):
        raise RuntimeError("缺少模型 API Key，请检查 backend/.env")

    monkeypatch.setattr("app.services.llm.chat_completion", fake_chat)
    r = client.post("/api/v1/parse", json={"brief": "x"})
    assert r.status_code == 502
    assert "解析失败" in r.json()["detail"]


# ---------- ② 选题推荐 ----------

def test_topics_ok(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {"topics": [{"angle": "角度", "title": "标题", "reason": "原因"}]}

    monkeypatch.setattr("app.services.llm.chat_completion", fake_chat)
    r = client.post(
        "/api/v1/topics", json={"parsed": {}, "type": "poster", "persona": "daily"}
    )
    assert r.status_code == 200
    assert len(r.json()["topics"]) == 1


def test_topics_empty_raises_502(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {"topics": []}

    monkeypatch.setattr("app.services.llm.chat_completion", fake_chat)
    r = client.post("/api/v1/topics", json={"parsed": {}})
    assert r.status_code == 502


# ---------- ③ 文案生成 ----------

def test_content_ok(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {"cover": {"headline": "标题", "points": ["a", "b", "c"]}, "body": "正文"}

    monkeypatch.setattr("app.services.llm.chat_completion", fake_chat)
    r = client.post(
        "/api/v1/content",
        json={"parsed": {}, "type": "poster", "persona": "daily", "topic": {}, "style": "realistic"},
    )
    assert r.status_code == 200
    assert r.json()["cover"]["headline"] == "标题"


def test_content_no_cover_raises_502(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {"body": "无封面"}

    monkeypatch.setattr("app.services.llm.chat_completion", fake_chat)
    r = client.post("/api/v1/content", json={"parsed": {}, "topic": {}})
    assert r.status_code == 502


# ---------- ④ 背景图 ----------

def test_image_ok(monkeypatch):
    async def fake_gen(*args, **kwargs):
        return "https://example.com/bg.jpg"

    monkeypatch.setattr("app.services.image.generate_image", fake_gen)
    r = client.post("/api/v1/image", json={"prompt": "秋日", "style": "realistic"})
    assert r.status_code == 200
    assert r.json()["url"] == "https://example.com/bg.jpg"


def test_image_error_returns_502(monkeypatch):
    async def fake_gen(*args, **kwargs):
        raise RuntimeError("图像生成失败")

    monkeypatch.setattr("app.services.image.generate_image", fake_gen)
    r = client.post("/api/v1/image", json={"prompt": "x", "style": "realistic"})
    assert r.status_code == 502


# ---------- ⑤ 抠图 ----------

def test_segment_ok(monkeypatch):
    monkeypatch.setattr("app.services.oss.new_object_key", lambda *a, **k: "seg/abc.png")
    async def fake_upload(*args, **kwargs):
        return "seg/abc.png"

    monkeypatch.setattr("app.services.oss.upload_to_oss", fake_upload)
    monkeypatch.setattr("app.services.oss.presigned_get_url", lambda *a, **k: "https://signed")
    async def fake_segment(*args, **kwargs):
        return "https://example.com/seg.png"

    monkeypatch.setattr("app.services.segment.segment_commodity", fake_segment)
    r = client.post(
        "/api/v1/segment", files={"file": ("p.png", _png_bytes(), "image/png")}
    )
    assert r.status_code == 200
    assert r.json()["url"] == "https://example.com/seg.png"


def test_segment_bad_image_returns_400():
    r = client.post("/api/v1/segment", files={"file": ("p.png", b"not-an-image", "image/png")})
    assert r.status_code == 400


def test_segment_oversize_returns_413(monkeypatch):
    monkeypatch.setattr("app.api.routes.MAX_UPLOAD_SIZE", 10)  # 缩小阈值便于测试
    r = client.post("/api/v1/segment", files={"file": ("p.png", _png_bytes(), "image/png")})
    assert r.status_code == 413


# ---------- ⑥ 视觉质检 ----------

def test_vqa_ok(monkeypatch):
    async def fake_vqa(*args, **kwargs):
        return {"items": [{"item": "Logo完整性", "level": "pass", "note": "ok"}]}

    monkeypatch.setattr("app.services.vqa.visual_qa", fake_vqa)
    r = client.post("/api/v1/vqa", json={"image_url": "https://x", "style": "realistic"})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


# ---------- ⑦ 三层合成 ----------

def test_composite_ok(monkeypatch):
    async def fake_composite(*args, **kwargs):
        return b"jpeg-bytes"

    monkeypatch.setattr("app.services.composite.composite_cover", fake_composite)
    monkeypatch.setattr("app.services.oss.new_object_key", lambda *a, **k: "composite/c.jpg")
    async def fake_upload(*args, **kwargs):
        return "composite/c.jpg"

    monkeypatch.setattr("app.services.oss.upload_to_oss", fake_upload)
    monkeypatch.setattr("app.services.oss.presigned_get_url", lambda *a, **k: "https://signed/c.jpg")
    r = client.post(
        "/api/v1/composite",
        json={"bg_url": "https://bg", "product_url": "", "logo_base64": "", "cover": {}},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["url"].startswith("https://signed")
    assert d["object_key"] == "composite/c.jpg"


# ---------- ⑧ 下载 ----------

def test_download_illegal_object_key():
    r = client.get("/api/v1/download/evil/path.txt")
    assert r.status_code == 400


def test_download_ok(monkeypatch):
    class FakeResponse:
        content = b"fake-jpeg"
        status_code = 200

    class FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr("app.services.oss.presigned_get_url", lambda *a, **k: "https://signed")
    monkeypatch.setattr("app.api.routes.httpx.AsyncClient", FakeAsyncClient)
    r = client.get("/api/v1/download/composite/c.jpg")
    assert r.status_code == 200
    assert r.content == b"fake-jpeg"
    assert "attachment" in r.headers.get("content-disposition", "")
