"""配置：所有凭证一律从环境变量（.env）读取，禁止硬编码。"""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env 的绝对路径，保证从任意工作目录启动都能读到
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def _get(key, default=""):
    return os.getenv(key, default)


class Settings:
    # ---------- DeepSeek（Brief 结构化解析） ----------
    DEEPSEEK_API_KEY = _get("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = _get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = _get("DEEPSEEK_MODEL", "deepseek-chat")

    # ---------- GLM-5.2（选题推荐 + 文案生成） ----------
    GLM_API_KEY = _get("GLM_API_KEY")
    GLM_BASE_URL = _get("GLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    GLM_MODEL = _get("GLM_MODEL", "glm-5-2-260617")

    # ---------- SeedDream 5.0（封面背景图） ----------
    SEEDREAM_API_KEY = _get("SEEDREAM_API_KEY")
    SEEDREAM_BASE_URL = _get("SEEDREAM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    SEEDREAM_MODEL = _get("SEEDREAM_MODEL", "doubao-seedream-5-0-260128")
    SEEDREAM_SIZE = _get("SEEDREAM_SIZE", "1728x2304")

    # ---------- 阿里云（商品抠图 + OSS） ----------
    ALIYUN_AK_ID = _get("ALIYUN_AK_ID")
    ALIYUN_AK_SECRET = _get("ALIYUN_AK_SECRET")
    OSS_BUCKET = _get("OSS_BUCKET")
    OSS_REGION = _get("OSS_REGION", "cn-shanghai")
    OSS_ENDPOINT = _get("OSS_ENDPOINT", "oss-cn-shanghai.aliyuncs.com")
    SEGMENT_ENDPOINT = _get("SEGMENT_ENDPOINT", "https://imageseg.cn-shanghai.aliyuncs.com/")

    # ---------- Qwen-VL（视觉质检，DashScope 国际版） ----------
    QWEN_API_KEY = _get("QWEN_API_KEY")
    QWEN_BASE_URL = _get("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    QWEN_MODEL = _get("QWEN_MODEL", "qwen-vl-max")


settings = Settings()
