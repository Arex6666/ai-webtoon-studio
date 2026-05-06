"""
AI Webtoon Studio - FastAPI 主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import init_db
from app.api.routes.auth import hash_password
from app.models.user import User

# 初始化 Celery 应用绑定，确保共享任务使用正确的 Broker
from app.celery_app import celery_app

# 重要：在导入路由之前先导入所有模型，确保 SQLAlchemy 关系正确注册
from app import models  # noqa: F401 - 确保所有模型在路由导入前加载
# Trigger reload

from app.api.routes import projects, chapters, panels, assets, render, typeset, compose, auth, identity, scene_anchor, brain, qa, ws, studios, exports, shot_versions, jobs, timeline, bindings, analytics, release, layerpacks, generate, templates, drafts, batch_render, script_pipeline, automation, asset_autobuild, props, conversations, faceid, export_strip, agent, providers, episode_video, media, qa_fix, versions, voices, music

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
from app.core.logging import configure_trace_logger
configure_trace_logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("Starting AI Webtoon Studio API...")
    init_db()
    logger.info("Database initialized")
    yield
    # 关闭时
    logger.info("Shutting down...")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    description="AI 漫剧（Webtoon/Motion Comic）开发工作台 API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 配置
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]
if isinstance(settings.CORS_ORIGINS, list):
    origins.extend(settings.CORS_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
from fastapi import Request
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    error_traceback = traceback.format_exc()
    logger.error(f"Unhandled exception: {exc}\n{error_traceback}")

    # 生产环境避免把内部异常细节暴露给客户端
    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": type(exc).__name__,
                "traceback": error_traceback,
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "type": type(exc).__name__,
            "traceback": None,
        },
    )

# 注册路由
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["项目"])
app.include_router(chapters.router, prefix="/api/v1/chapters", tags=["章节"])
app.include_router(panels.router, prefix="/api/v1/panels", tags=["分镜"])
app.include_router(assets.router, prefix="/api/v1/assets", tags=["资产"])
app.include_router(render.router, prefix="/api/v1/render", tags=["渲染"])
app.include_router(typeset.router, prefix="/api/v1/typeset", tags=["嵌字"])
app.include_router(compose.router, prefix="/api/v1/compose", tags=["合成导出"])
app.include_router(identity.router, prefix="/api/v1/identity", tags=["角色一致性"])
app.include_router(scene_anchor.router, prefix="/api/v1/scene-anchor", tags=["场景一致性"])
app.include_router(brain.router, prefix="/api/v1/brain", tags=["AI Brain"])
app.include_router(qa.router, prefix="/api/v1/qa", tags=["质量检测"])
app.include_router(ws.router, prefix="/api/v1/ws", tags=["WebSocket"])
app.include_router(studios.router, prefix="/api/v1/studios", tags=["工作室"])
app.include_router(exports.router, prefix="/api/v1/exports", tags=["导出"])
app.include_router(shot_versions.router, prefix="/api/v1/shot-versions", tags=["镜头版本"])

# Task Package 10: 后端对接
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["统一任务"])
app.include_router(timeline.router, prefix="/api/v1/chapters", tags=["时间轴"])
app.include_router(bindings.router, prefix="/api/v1/chapters", tags=["资产绑定"])
app.include_router(analytics.router, prefix="/api/v1/chapters", tags=["统计分析"])
app.include_router(release.router, prefix="/api/v1/chapters", tags=["发布交付"])

# Task Package A05: LayerPack
app.include_router(layerpacks.router, prefix="/api/v1/panels", tags=["图层包"])

# Advanced Generation (IP-Adapter, ControlNet, Inpaint, Layer Separation)
app.include_router(generate.router, prefix="/api/v1/generate", tags=["高级生成"])

# Task A10: Templates
app.include_router(templates.router, prefix="/api/v1/templates", tags=["模板"])

# S3-02: Storyboard Drafts
app.include_router(drafts.router, prefix="/api/v1/drafts", tags=["分镜草稿"])

# S3-07: Batch Render
app.include_router(batch_render.router, prefix="/api/v1", tags=["批量渲染"])

# Health Check
from app.api.routes import health
app.include_router(health.router, prefix="/api/v1/health", tags=["System"])

# P0: Script Pipeline (3-phase LLM: Parse → Plan → Bind)
app.include_router(script_pipeline.router, prefix="/api/v1", tags=["剧本流水线"])

# P1: Full Automation (Character Chain + Scene Chain + Binding)
app.include_router(automation.router, prefix="/api/v1/automation", tags=["全自动化"])

# P0-CH: Asset AutoBuild (Canonical Characters/Scenes)
app.include_router(asset_autobuild.router, prefix="/api/v1", tags=["资产自动生成"])

# S5-04: Prop Assets System
app.include_router(props.router, prefix="/api/v1", tags=["物品资产"])

# Conversational Agent System
app.include_router(conversations.router, prefix="/api/v1", tags=["对话智能体"])

# Agent API (chat-driven pre-production)
app.include_router(agent.router, prefix="/api/v1/agent", tags=["Agent"])

# Phase 5: Studio Orchestrator
from app.api.routes import orchestrator
app.include_router(orchestrator.router, prefix="/api/v1", tags=["统一编排"])

# P0: FaceID Embedding System
app.include_router(faceid.router, prefix="/api/v1", tags=["FaceID"])

# P0: Strip PNG Export
app.include_router(export_strip.router, prefix="/api/v1", tags=["导出"])

# P0: Provider Status API
app.include_router(providers.router, tags=["Providers"])

# Episode Video Generation (豆包视频大模型)
app.include_router(episode_video.router, prefix="/api/v1/agent", tags=["视频生成"])

# Media URL (presigned URL generation)
app.include_router(media.router, prefix="/api/v1", tags=["媒体"])

# E5: NeedsFix Workflow with Guided Repair
app.include_router(qa_fix.router, prefix="/api/v1/qa-fix", tags=["质量修复"])

# E3: Persistent Version Tree
app.include_router(versions.router, prefix="/api/v1/versions", tags=["版本管理"])

# Voice Agent (AI 配音智能体)
app.include_router(voices.router, prefix="/api/v1/voices", tags=["配音"])

# Music Asset Management
app.include_router(music.router, prefix="/api/v1/music", tags=["音乐"])


@app.get("/")
async def root():
    """API 根路径"""
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
