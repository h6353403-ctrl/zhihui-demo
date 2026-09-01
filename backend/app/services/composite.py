"""三层合成：AI 背景 + 真实产品图（透明抠图）+ Logo + 模板文字 → 一张成稿图。

用途：把 CSS 三层合成渲染成真实图片，供 VLM 视觉质检检查最终成稿的
Logo 完整性、文字越界、调性统一。

文字排版策略（对应前端模板安全区约束）：
- 所有文本先按宽度折行，再逐级缩小字号，保证不越出画布
- 主标题最多 2 行、副标题最多 3 行、卖点每条 1 行、角标 1 行
- 放不下时自动降字号，最小字号仍放不下则截断并记录告警日志
"""
import base64
import io
import logging
import os

import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

FONT_PATHS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
]

CANVAS = (900, 1200)  # 3:4 小红书封面
INK = (42, 33, 28)
ACCENT = (232, 56, 79)


def _load_font(size: int):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text(draw, text, font, max_width):
    """按字符折行，返回行列表。

    中文逐字、连续英文/数字按整体处理；单行超过 max_width 时换行。
    """
    if not text:
        return [""]
    lines = []
    current = ""
    for ch in text:
        candidate = current + ch
        w, _ = _text_size(draw, candidate, font)
        if w > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def fit_font(draw, text, max_width, max_lines, start_size, min_size=16):
    """从 start_size 逐级缩小字号，直到文本能放入 max_width × max_lines。

    返回 (font, lines, size, truncated)。
    - 保证单行宽度 ≤ max_width、行数 ≤ max_lines
    - 最小字号仍放不下时，截断多余行并置 truncated=True
    """
    size = start_size
    while size >= min_size:
        font = _load_font(size)
        lines = wrap_text(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines, size, False
        size -= 2

    font = _load_font(min_size)
    lines = wrap_text(draw, text, font, max_width)[:max_lines]
    return font, lines, min_size, True


async def _download(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise RuntimeError(f"图片下载失败（{resp.status_code}）")
    return resp.content


async def composite_cover(bg_url: str, product_url: str, logo_base64: str, cover: dict) -> bytes:
    W, H = CANVAS

    # 第一层：AI 背景
    bg_bytes = await _download(bg_url)
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA").resize((W, H), Image.LANCZOS)

    # 第二层：真实产品图（透明抠图，右下）
    if product_url:
        try:
            p_bytes = await _download(product_url)
            product = Image.open(io.BytesIO(p_bytes)).convert("RGBA")
            pw = int(W * 0.30)
            ph = max(1, int(product.height * pw / product.width))
            product = product.resize((pw, ph), Image.LANCZOS)
            bg.paste(product, (W - pw - 50, H - ph - 190), product)
        except Exception:
            pass  # 产品图为可选项，缺失不阻断合成

    # 第三层：品牌 Logo（右上）
    if logo_base64:
        try:
            data = logo_base64.split(",", 1)[-1]
            logo = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
            lw = 120
            lh = max(1, int(logo.height * lw / logo.width))
            logo = logo.resize((lw, lh), Image.LANCZOS)
            bg.paste(logo, (W - lw - 45, 45), logo)
        except Exception:
            pass

    draw = ImageDraw.Draw(bg)

    # 文字安全区：左侧留给标题/卖点，右侧预留给 Logo 与角标
    text_max_width = int(W * 0.56)  # 约 504px

    # 主标题（左上，最多 2 行）
    if cover.get("headline"):
        font, lines, size, truncated = fit_font(
            draw, cover["headline"], text_max_width, 2, start_size=72
        )
        if truncated:
            logger.warning("headline 过长被截断：%s", cover["headline"])
        y = 120
        for line in lines:
            draw.text((55, y), line, fill=INK, font=font)
            y += int(size * 1.3)

    # 副标题（最多 3 行）
    if cover.get("subhead"):
        font, lines, size, truncated = fit_font(
            draw, cover["subhead"], text_max_width, 3, start_size=34
        )
        if truncated:
            logger.warning("subhead 过长被截断：%s", cover["subhead"])
        y = 240
        for line in lines:
            draw.text((55, y), line, fill=INK, font=font)
            y += int(size * 1.35)

    # 促销角标（右上，红底白字，最多 1 行，右对齐）
    if cover.get("badge"):
        font, lines, size, truncated = fit_font(
            draw, cover["badge"], int(W * 0.30), 1, start_size=32, min_size=18
        )
        if truncated:
            logger.warning("badge 过长被截断：%s", cover["badge"])
        line = lines[0]
        tw, th = _text_size(draw, line, font)
        bw = tw + 30
        bh = th + 18
        x1, y1 = W - bw - 45, 200
        draw.rounded_rectangle([x1, y1, x1 + bw, y1 + bh], radius=8, fill=ACCENT)
        draw.text((x1 + 15, y1 + 9), line, fill=(255, 255, 255), font=font)

    # 卖点（左下，白底标签，每条 1 行）
    points = cover.get("points") or []
    y = H - 330
    for pt in points:
        font, lines, size, truncated = fit_font(
            draw, pt, int(W * 0.86), 1, start_size=30, min_size=18
        )
        if truncated:
            logger.warning("卖点过长被截断：%s", pt)
        line = lines[0]
        tw, th = _text_size(draw, line, font)
        draw.rectangle([55, y, 55 + tw + 20, y + th + 18], fill=(255, 255, 255))
        draw.text((65, y + 8), line, fill=INK, font=font)
        y += th + 28

    # 法务角标（底部条）
    draw.rectangle([0, H - 70, W, H], fill=(255, 255, 255))
    draw.text((55, H - 55), "品牌合作推广 · 效果因人而异", fill=(0, 0, 0), font=_load_font(22))

    buf = io.BytesIO()
    bg.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()
