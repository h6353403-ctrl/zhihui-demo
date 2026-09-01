# 智绘 · 工作流验证 Demo

品牌 Brief 驱动的达人图文生产平台 MVP。跑通「Brief 解析 → 选题 → 文案 → 图像三层合成 → 质检合规」完整链路。

## 功能亮点

- **Brief 结构化解析**：只提取原文明确写出的信息、绝不推断，缺失字段回填确认，避免一个猜错的卖点污染下游全部笔记
- **选题推荐**：3 个差异化选题，同活动下做相似度去重
- **文案与封面排版**：达人语言风格定制，模板安全区字数硬约束（主标题 ≤10 字等）
- **图像三层合成**：AI 生成背景 + 真实产品图抠图（不重绘）+ 品牌 Logo + 确定性模板文字
- **质检与合规**：客户端硬规则拦截（确定性）+ 模型软评分 + VLM 视觉质检（概率性）三层防线
- **安全设计**：所有凭证集中在后端 `.env`，前端零硬编码，私有 OSS + 预签名 URL

## 技术栈

- **前端**：React 19 + Vite，纯 UI + 受控 API 调用
- **后端**：FastAPI，统一封装所有模型与云服务调用
- **AI 模型**：DeepSeek（Brief 解析）、GLM（选题/文案）、SeedDream（背景图）、Qwen-VL（视觉质检）
- **云服务**：阿里云视觉智能（商品抠图）、阿里云 OSS（私有 bucket + 预签名 URL）

## 目录结构

```
├── src/                   # 前端源码
│   ├── main.jsx           # 入口
│   └── zhihui-demo.jsx    # 工作流 Demo 组件
├── backend/
│   ├── app/
│   │   ├── api/routes.py      # 9 个接口
│   │   ├── core/config.py     # 从 .env 读配置
│   │   └── services/          # llm / image / vqa / segment / oss / composite / jsonutil
│   ├── tests/                 # 单元 + 集成测试
│   ├── .env.example           # 变量模板（可提交）
│   └── requirements.txt
├── index.html
├── vite.config.js         # /api 代理到后端
├── LICENSE
└── package.json
```

## 快速开始

### 后端（端口 8000）

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # 复制模板，填入你的真实凭证
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 前端（端口 5173）

```bash
npm install
npm run dev                 # 打开 http://localhost:5173
```

## 环境变量（backend/.env）

复制 `backend/.env.example` 为 `backend/.env` 后填写。所有变量说明见模板文件，关键项：

| 变量 | 用途 |
|---|---|
| `DEEPSEEK_API_KEY` | Brief 解析 |
| `GLM_API_KEY` | 选题 + 文案 |
| `SEEDREAM_API_KEY` | 背景图生成 |
| `ALIYUN_AK_ID` / `ALIYUN_AK_SECRET` | 阿里云签名（抠图 + OSS） |
| `OSS_BUCKET` | OSS 存储桶（上海） |
| `QWEN_API_KEY` | 视觉质检 |

> 真实凭证只在 `backend/.env`（已 gitignore），绝不入库、不入前端。

## API 接口

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/health` | 健康检查 |
| POST | `/api/v1/parse` | ① Brief 结构化解析 |
| POST | `/api/v1/topics` | ② 选题推荐 |
| POST | `/api/v1/content` | ③ 文案 + 封面排版 |
| POST | `/api/v1/image` | ④ 背景图生成 |
| POST | `/api/v1/segment` | ⑤ 产品图抠图 |
| POST | `/api/v1/vqa` | ⑥ 视觉质检 |
| POST | `/api/v1/composite` | ⑦ 三层合成成稿 |
| GET | `/api/v1/download/{object_key}` | 导出成稿图 |

### 视觉风格（style 取值）

`realistic` 写实 / `illustration` 插画 / `3d` 3D卡通 / `cyberpunk` 赛博朋克 / `guofeng` 国风 / `minimal` 极简

## 测试

```bash
cd backend
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ -v
```

覆盖：API 路由集成（TestClient + mock 外部服务）、JSON 解析容错、阿里云 RPC 与 OSS 签名、合成图文字折行与自适应。

## License

[MIT](./LICENSE) © 2025-2026 吴萌萌
