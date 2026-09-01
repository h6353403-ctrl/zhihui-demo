"""API 路由：前端通过受控 API 调用后端，绝不接触任何凭证。"""
import io
import json

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel

from ..core.config import settings
from ..services import composite as composite_service
from ..services import image as image_service
from ..services import llm
from ..services import oss, segment, vqa

router = APIRouter(prefix="/api/v1")

PERSONAS = {
    "vivid": {"name": "元气种草型", "hint": "短句、感叹多、emoji 密集、第二人称"},
    "rational": {"name": "理性测评型", "hint": "长句、数据导向、少 emoji、第一人称"},
    "daily": {"name": "生活碎碎念型", "hint": "口语化、场景开头、语气词多"},
}
TYPES = {
    "poster": "活动大字报",
    "review": "产品测评",
    "recommend": "好物推荐",
}
STYLES = {
    "realistic": {"name": "写实", "en": "Realistic", "prompt": "写实摄影风格，真实照片质感，自然光影，高细节"},
    "illustration": {"name": "插画", "en": "Illustration", "prompt": "手绘插画风格，温暖笔触，艺术感"},
    "3d": {"name": "3D 卡通", "en": "3D Render", "prompt": "3D渲染风格，立体卡通盲盒质感，C4D柔和灯光"},
    "cyberpunk": {"name": "赛博朋克", "en": "Cyberpunk", "prompt": "赛博朋克风格，霓虹灯光，蓝紫配色，科技感"},
    "guofeng": {"name": "国风", "en": "Guofeng", "prompt": "国风水墨风格，水墨晕染，国潮元素，留白意境"},
    "minimal": {"name": "极简", "en": "Minimal", "prompt": "极简风格，干净留白，大面积纯色，高级感构图"},
}


class ParseRequest(BaseModel):
    brief: str


class TopicsRequest(BaseModel):
    parsed: dict
    type: str = "poster"
    persona: str = "daily"


class ContentRequest(BaseModel):
    parsed: dict
    type: str = "poster"
    persona: str = "daily"
    topic: dict
    style: str = "realistic"


class ImageRequest(BaseModel):
    prompt: str
    style: str = "realistic"


class VqaRequest(BaseModel):
    image_url: str
    style: str = "realistic"


class CompositeRequest(BaseModel):
    bg_url: str
    product_url: str = ""
    logo_base64: str = ""
    cover: dict = {}


@router.post("/parse")
async def parse_brief(req: ParseRequest):
    """① Brief 结构化解析（DeepSeek）"""
    prompt = f"""你是品牌 Brief 结构化解析引擎。把下面的 Brief 解析成 JSON。
规则：只提取原文明确写出的信息，绝不推断或补充。原文没写的字段，把字段名加进 missing_fields 数组。
注意：视觉风格由用户在界面另行选择，不解析 visual_style 字段。
只输出 JSON，不要任何解释、前言或 markdown 代码块。

JSON 结构：
{{"brand":"","campaign":{{"name":"","period":""}},"products":[{{"name":"","specs":"","price":"","original_price":""}}],"selling_points":[{{"text":"","priority":"must 或 optional"}}],"target_audience":"","tone":"","must_include":[],"forbidden":[],"missing_fields":[],"confidence":0.9}}

Brief 原文：
{req.brief}"""
    try:
        result = await llm.chat_completion(
            settings.DEEPSEEK_BASE_URL, settings.DEEPSEEK_API_KEY, settings.DEEPSEEK_MODEL, prompt
        )
        # 视觉风格由前端选择器决定，不解析也不返回该字段
        result.pop("visual_style", None)
        if isinstance(result.get("missing_fields"), list):
            result["missing_fields"] = [
                f for f in result["missing_fields"]
                if "visual_style" not in str(f).lower()
            ]
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"解析失败：{e}")


@router.post("/topics")
async def recommend_topics(req: TopicsRequest):
    """② 选题推荐（GLM）"""
    t = TYPES.get(req.type, "活动大字报")
    p = PERSONAS.get(req.persona, PERSONAS["daily"])
    prompt = f"""你是小红书选题推荐引擎。基于下面的结构化 Brief，为一位达人推荐 3 个互不重复的选题。
内容类型：{t}
达人语言风格：{p['name']}（{p['hint']}）
要求：3 个选题角度必须明显不同，避免同质化。title 不超过 20 字。
只输出 JSON，不要解释：
{{"topics":[{{"angle":"选题角度，8字内","title":"笔记标题","reason":"为什么适配这位达人，30字内"}}]}}

Brief：{json.dumps(req.parsed, ensure_ascii=False)}"""
    try:
        result = await llm.chat_completion(
            settings.GLM_BASE_URL, settings.GLM_API_KEY, settings.GLM_MODEL, prompt
        )
        topics = result.get("topics") or []
        if not topics:
            raise HTTPException(status_code=502, detail="模型未返回选题")
        return {"topics": topics}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"选题生成失败：{e}")


@router.post("/content")
async def generate_content(req: ContentRequest):
    """③ 文案与封面排版（GLM）"""
    t = TYPES.get(req.type, "活动大字报")
    p = PERSONAS.get(req.persona, PERSONAS["daily"])
    st = STYLES.get(req.style, STYLES["realistic"])
    prompt = f"""你是小红书图文生成引擎。基于 Brief 和选定选题，生成封面排版数据和正文。
内容类型：{t}
达人语言风格：{p['name']}（{p['hint']}）
视觉风格：{st['name']}（{st['prompt']}），封面背景提示词 bg_prompt 必须符合该风格
选定选题：{json.dumps(req.topic, ensure_ascii=False)}

硬约束（模板引擎限制，必须遵守）：
- headline 主标题最多 10 个字
- subhead 副标题最多 16 个字
- points 恰好 3 条，每条最多 9 个字
- badge 促销角标最多 8 个字
- body 正文 150-220 字，符合达人语言风格
- 必须覆盖 Brief 中所有 priority 为 must 的卖点
- 严禁出现 Brief forbidden 列表中的任何词或近义表述

只输出 JSON，不要解释：
{{"cover":{{"headline":"","subhead":"","points":["","",""],"badge":"","bg_prompt":"背景图生成提示词，描述场景氛围材质光影，不描述任何商品外观"}},"body":"","tags":[],"self_check":[{{"level":"pass 或 review 或 block","item":"检查项","note":"说明"}}]}}

Brief：{json.dumps(req.parsed, ensure_ascii=False)}"""
    try:
        result = await llm.chat_completion(
            settings.GLM_BASE_URL, settings.GLM_API_KEY, settings.GLM_MODEL, prompt, max_tokens=3000
        )
        if not result.get("cover"):
            raise HTTPException(status_code=502, detail="模型未返回有效的图文数据")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"图文生成失败：{e}")


@router.post("/image")
async def gen_image(req: ImageRequest):
    """④ 封面背景图（SeedDream）"""
    try:
        st = STYLES.get(req.style, STYLES["realistic"])
        final_prompt = f"{st['prompt']}，{req.prompt}"
        url = await image_service.generate_image(
            settings.SEEDREAM_BASE_URL,
            settings.SEEDREAM_API_KEY,
            settings.SEEDREAM_MODEL,
            final_prompt,
            settings.SEEDREAM_SIZE,
        )
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"背景图生成失败：{e}")


MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/segment")
async def segment_image(file: UploadFile = File(...)):
    """⑤ 产品图抠图：上传 → 上海 OSS → SegmentCommodity → 透明背景图"""
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="文件为空")
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="文件过大，最大支持 10MB")
        # 视觉智能要求 < 2000x2000，统一缩放到最长边 ≤ 1900 并转 PNG（保留透明通道）
        try:
            img = Image.open(io.BytesIO(content))
            img = img.convert("RGBA")
        except Exception:
            raise HTTPException(status_code=400, detail="无法识别的图片文件，请上传 JPG/PNG 等常见格式")
        img.thumbnail((1900, 1900))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        content = buf.getvalue()

        object_key = oss.new_object_key("seg", "png")
        object_key = await oss.upload_to_oss(content, object_key, "image/png")
        signed_url = oss.presigned_get_url(object_key)
        result_url = await segment.segment_commodity(signed_url)
        return {"url": result_url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"抠图失败：{e}")


@router.post("/vqa")
async def visual_qa_endpoint(req: VqaRequest):
    """⑥ 视觉质检（Qwen-VL）：Logo 完整性 / 文字越界 / 调性统一"""
    try:
        st = STYLES.get(req.style, STYLES["realistic"])
        result = await vqa.visual_qa(
            settings.QWEN_BASE_URL,
            settings.QWEN_API_KEY,
            settings.QWEN_MODEL,
            req.image_url,
            st["name"],
            st["prompt"],
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"视觉质检失败：{e}")


@router.post("/composite")
async def composite_cover(req: CompositeRequest):
    """⑦ 三层合成：背景 + 产品抠图 + Logo + 文字 → 最终成稿图"""
    try:
        img_bytes = await composite_service.composite_cover(
            req.bg_url, req.product_url, req.logo_base64, req.cover
        )
        object_key = oss.new_object_key("composite", "jpg")
        await oss.upload_to_oss(img_bytes, object_key, "image/jpeg")
        signed_url = oss.presigned_get_url(object_key)
        return {"url": signed_url, "object_key": object_key}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"合成失败：{e}")


@router.get("/download/{object_key:path}")
async def download_object(object_key: str):
    """下载 OSS 对象（仅限本项目生成的前缀），供前端导出成稿图。"""
    if not object_key.startswith(("composite/", "seg/")):
        raise HTTPException(status_code=400, detail="非法的对象路径")
    try:
        signed = oss.presigned_get_url(object_key)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(signed)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"对象下载失败（{resp.status_code}）")
        content_type = "image/jpeg" if object_key.endswith(".jpg") else "image/png"
        filename = object_key.rsplit("/", 1)[-1]
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"下载失败：{e}")
