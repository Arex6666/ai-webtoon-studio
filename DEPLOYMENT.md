# AI Webtoon Studio 部署指南

> 最后更新: 2026-01-17

---

## 项目概览

AI Webtoon Studio 是一个 AI 驱动的漫剧生产工厂，支持：

- ✅ ComfyUI 多模式图像生成
- ✅ 图层分离与管理
- ✅ 气泡排版编辑
- ✅ 长条漫导出
- ✅ Release Bundle 可追溯交付
- ✅ 模板化工作流

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 后端 | FastAPI + SQLAlchemy + Alembic |
| 异步任务 | Celery + Redis |
| 数据库 | PostgreSQL |
| 对象存储 | MinIO |
| 图像生成 | ComfyUI |

---

## 环境要求

- Node.js 18+
- Python 3.10+
- PostgreSQL 14+
- Redis 6+
- MinIO (或 S3 兼容存储)
- ComfyUI 实例 (可选，用于真实生成)

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/ai-webtoon-studio.git
cd ai-webtoon-studio
```

### 2. 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# ============ 数据库 ============
DATABASE_URL=postgresql://user:password@localhost:5432/webtoon_studio

# ============ Redis ============
REDIS_URL=redis://localhost:6379/0

# ============ MinIO ============
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=webtoon-studio
MINIO_SECURE=false

# ============ ComfyUI (可选) ============
COMFYUI_URL=http://localhost:8188

# ============ LLM (可选) ============
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx

# ============ JWT ============
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ============ CORS ============
CORS_ORIGINS=["http://localhost:3000", "http://localhost:3001"]
```

### 3. 安装依赖

**后端：**

```bash
cd apps/api
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**前端：**

```bash
cd apps/web
npm install
```

### 4. 初始化数据库

```bash
cd apps/api
alembic upgrade head
```

### 5. 启动服务

**方式 A：开发模式（分别启动）**

```bash
# 终端 1: 后端 API
cd apps/api
uvicorn app.main:app --reload --port 8000

# 终端 2: Celery Worker
cd apps/api
celery -A app.celery_app:celery_app worker --loglevel=info

# 终端 3: 前端
cd apps/web
npm run dev
```

**方式 B：使用启动脚本**

```bash
# Windows
.\scripts\start-dev.ps1

# Linux/Mac
./scripts/start-dev.sh
```

### 6. 访问应用

- 前端: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

---

## Docker 部署

### 使用 Docker Compose

```bash
docker-compose up -d
```

### docker-compose.yml 示例

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_USER: webtoon
      POSTGRES_PASSWORD: webtoon123
      POSTGRES_DB: webtoon_studio
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"

  api:
    build: ./apps/api
    environment:
      DATABASE_URL: postgresql://webtoon:webtoon123@postgres:5432/webtoon_studio
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
    depends_on:
      - postgres
      - redis
      - minio
    ports:
      - "8000:8000"

  worker:
    build: ./apps/api
    command: celery -A app.celery_app:celery_app worker --loglevel=info
    environment:
      DATABASE_URL: postgresql://webtoon:webtoon123@postgres:5432/webtoon_studio
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis
      - api

  web:
    build: ./apps/web
    environment:
      NEXT_PUBLIC_API_URL: http://api:8000
    depends_on:
      - api
    ports:
      - "3000:3000"

volumes:
  postgres_data:
  minio_data:
```

---

## 生产环境配置

### 1. 使用生产数据库

```bash
DATABASE_URL=postgresql://user:password@your-db-host:5432/webtoon_prod
```

### 2. 配置 HTTPS

使用 Nginx 或 Caddy 作为反向代理：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
    }
}
```

### 3. 配置 ComfyUI

确保 ComfyUI 实例已安装以下节点：

- ComfyUI-Manager
- ComfyUI-Impact-Pack (SAM)
- ComfyUI-Controlnet-Aux
- comfyui-tooling-nodes

```bash
COMFYUI_URL=http://your-comfyui-host:8188
```

---

## API 端点一览

### 核心 API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/projects` | GET/POST | 项目管理 |
| `/api/v1/chapters` | GET/POST | 章节管理 |
| `/api/v1/panels` | GET/POST | 面板管理 |
| `/api/v1/jobs` | POST | 任务创建 |

### 高级生成

| 端点 | 功能 |
|------|------|
| `/api/v1/generate/ipadapter` | 角色一致性 |
| `/api/v1/generate/controlnet` | ControlNet 控制 |
| `/api/v1/generate/inpaint` | 局部重绘 |
| `/api/v1/generate/layer-separation` | 图层分离 |

### 导出

| 端点 | 功能 |
|------|------|
| `/api/v1/jobs/export` | 章节导出 |
| `/api/v1/chapters/{id}/release` | 发布管理 |

---

## 故障排查

### 数据库连接失败

```bash
# 检查 PostgreSQL 状态
pg_isready -h localhost -p 5432

# 测试连接
psql -h localhost -U user -d webtoon_studio
```

### Celery Worker 无响应

```bash
# 检查 Redis 连接
redis-cli ping

# 查看 Celery 日志
celery -A app.celery_app:celery_app inspect active
```

### ComfyUI 连接失败

```bash
# 测试 ComfyUI 健康
curl http://your-comfyui:8188/system_stats
```

---

## 更多资源

- [前端设计文档](./前端设计.md)
- [API 文档](http://localhost:8000/docs)
- [ComfyUI 官方文档](https://github.com/comfyanonymous/ComfyUI)
