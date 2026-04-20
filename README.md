# AI Webtoon Studio

AI 漫剧（Webtoon/Motion Comic）开发工作台 - 商业级 AI 漫剧创作工具

**核心理念：** Canva 的易用性 + Midjourney 的生成力 + CapCut 的剪辑逻辑

> 🎉 **最新更新 (2026-01-31)**: Agent 前端框架 M1 完成，包含首页灵感输入、策划工作台、制作工作台三大工作面

---

## 🚀 快速开始

### 环境要求

- **Docker & Docker Compose** - PostgreSQL、Redis、MinIO
- **Node.js 18+** - 前端开发
- **Python 3.11+** - 后端开发

### 一键启动

```powershell
# 1. 启动基础设施
cd docker
docker compose up -d postgres redis minio

# 2. 启动后端 (API & Worker)
cd apps/api
pip install -r requirements.txt
# 终端 1: 启动 API 服务
python -m uvicorn app.main:app --reload --port 8000
# 终端 2: 启动 Celery Worker (必须，用于执行 AI 分镜/视频等后台任务)
celery -A app.celery_app:celery_app worker --loglevel=info --pool=solo

# 3. 启动前端 (port: 3001)
cd apps/web
npm install
npm run dev
```

### 访问地址

| 服务 | URL | 说明 |
|------|-----|------|
| 🏠 **首页** | http://localhost:3001 | 灵感输入 |
| 📋 **策划工作台** | http://localhost:3001/agent/demo | Agent 对话驱动 |
| 📹 **制作工作台** | http://localhost:3001/agent/demo/produce | 时间线编辑 |
| 🎬 **Studio** | http://localhost:3001/projects | 传统编辑模式 |
| 📚 **API 文档** | http://localhost:8000/docs | Swagger UI |

---

## 🎬 P0 Production MVP 配置

Production MVP 需要额外配置 ComfyUI 和 InsightFace 才能使用真实渲染和人脸一致性功能。

### 📦 快速配置

```powershell
# 1. 安装 InsightFace (后端)
cd apps/api
pip install insightface onnxruntime

# 2. 配置 ComfyUI URL
echo COMFYUI_URL=http://127.0.0.1:8188 >> .env

# 3. 验证配置
python validate_setup.py
```

### 🔧 详细配置指南

查看完整的 [ComfyUI + InsightFace 配置指南](../../SETUP_GUIDE.md) 了解：
- ComfyUI 安装和模型下载
- InsightFace 配置
- 端到端测试流程
- 常见问题排查

### ✅ 快速测试

```powershell
# 测试 ComfyUI 连接
python apps/api/test_comfyui_connection.py

# 测试 FaceID 提取
python apps/api/test_faceid_extraction.py

# 完整验证
python apps/api/validate_setup.py
```

---

## 📁 项目结构

```
ai-webtoon-studio/
├── apps/
│   ├── web/                          # Next.js 14 前端
│   │   └── src/
│   │       ├── app/                  # App Router
│   │       │   ├── page.tsx          # 首页 (灵感输入)
│   │       │   ├── agent/            # Agent 路由
│   │       │   └── projects/         # 项目列表
│   │       │
│   │       └── components/
│   │           ├── home/             # 首页组件 (3 files)
│   │           │   ├── InspirationInput.tsx
│   │           │   ├── TemplateChips.tsx
│   │           │   └── InspirationFeed.tsx
│   │           │
│   │           ├── agent/            # 策划工作台 (6 files)
│   │           │   ├── EpisodeTree.tsx
│   │           │   ├── AgentChat.tsx
│   │           │   ├── PlanningPanel.tsx
│   │           │   ├── AssetSlotPanel.tsx
│   │           │   ├── AssetLockGate.tsx
│   │           │   └── AssetPicker.tsx
│   │           │
│   │           ├── produce/          # 制作工作台 (4 files)
│   │           │   ├── MaterialPanel.tsx
│   │           │   ├── PreviewCanvas.tsx
│   │           │   ├── FilmStrip.tsx
│   │           │   └── Timeline.tsx
│   │           │
│   │           └── studio/           # 传统编辑器 (~40 files)
│   │
│   └── api/                          # FastAPI 后端
│       └── app/
│           ├── api/routes/           # API 路由 (37 files)
│           ├── models/               # SQLAlchemy 模型 (64 files)
│           ├── schemas/              # Pydantic Schema (34 files)
│           ├── services/             # 业务服务 (~180 files)
│           └── workers/              # Celery 任务 (13 files)
│
├── design-system/                    # 设计系统
│   └── ai-webtoon-studio/
│       └── MASTER.md                 # UI/UX 规范
└── docker/
    └── docker-compose.yml
```

---

## 🎬 核心功能

### 1. 首页灵感输入
- **InspirationInput**: 大型创意输入框，支持多文件上传、@引用
- **TemplateChips**: 预设 6 大题材模板 (都市/悬疑/爽文/古风/科幻/搞笑)
- **InspirationFeed**: 灵感广场作品展示与复刻

### 2. Agent 策划工作台
- **EpisodeTree**: 剧集/阶段状态管理
- **AgentChat**: 智能体对话，支持 Action Card 交互
- **AssetSlotPanel**: 角色/场景/物品/风格 4类资产绑定
- **AssetLockGate**: 资产生成门禁系统，包含复用推荐
- **AssetPicker**: 资产选择器，支持搜索与筛选

### 3. 制作工作台
- **PreviewCanvas**: 多画幅 (9:16/16:9/4:5/1:1) 预览，支持安全区
- **Timeline**: 多轨 (视频/配音/音乐) 非线性编辑
- **FilmStrip**: 可视化分镜条，集成 QA 状态
- **MaterialPanel**: 层级化素材管理 (分镜/图层/特效/音频)

### 4. 智能管线
- **Prompt Contract**: 结构化 Prompt 契约系统
- **Auto Repair Loop**: 自动验证与修复机制
- **FaceID Embedding**: 角色一致性保证

---

## 📊 功能完成度

| 模块 | 状态 | 包含功能 |
|------|------|----------|
| **Frontend Framework** | ✅ 100% | Next.js 14, Tailwind, Framer Motion, Zustand |
| **Agent Workspace** | ✅ 100% | Chat, Tree, Planning, Asset Controls |
| **Production Workspace**| ✅ 100% | Timeline, Canvas, FilmStrip, Layers |
| **Homepage** | ✅ 100% | Inspiration Input, Feed, Templates |
| **Backend API** | ✅ 90% | Project/Chapter/Asset CRUD, GenAI Pipeline |
| **GenAI Pipeline** | ✅ 85% | Script Analysis, Storyboard Gen, Repair Loop |
| **ComfyUI Integration**| 🚧 50% | Mock Pipeline Complete, Real Integration Pending |

---

## 🔧 常见配置

创建 `apps/api/.env`:

```env
# LLM Provider
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/webtoon_studio

# Storage
MINIO_ENDPOINT=localhost:9000
MINIO_BUCKET=webtoon-assets
```

---

## 📄 License

MIT
