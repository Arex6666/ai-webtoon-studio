"""
Episode Video Generation API
分集视频生成 - 使用豆包视频大模型
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
import uuid
import logging

from app.db.database import get_db
from app.models import Job
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class PanelVideoMeta(BaseModel):
    """每张图片对应的分镜元数据，用于编译高质量 motion prompt"""
    camera_move: Optional[str] = None      # "static", "pan", "dolly_in", etc.
    shot_type: Optional[str] = None        # "CU", "WS", "MS", etc.
    actions: Optional[str] = None          # 角色动作描述
    mood: Optional[str] = None             # 情绪氛围
    weather: Optional[str] = None          # 天气
    time_of_day: Optional[str] = None      # 时间段
    composition_notes: Optional[List[str]] = None  # 构图要点
    visual_prompt: Optional[str] = None    # LLM 生成的视觉描述
    lens_hint: Optional[str] = None        # 镜头焦距提示
    duration_sec: Optional[float] = None   # 面板时长（优先级高于全局）


class EpisodeVideoRequest(BaseModel):
    """分集视频生成请求"""
    project_id: str
    image_urls: List[str] = []           # 场景图片 URL 列表
    motion_prompt: str = "缓慢推进，镜头微微摇动，营造氛围感"  # 运动提示词
    duration_sec: float = 5.0            # 默认每段视频时长（当 duration_per_image 未指定时使用）
    duration_per_image: Optional[List[float]] = None  # 每张图片的独立时长（与 image_urls 对应）
    panel_metadata: Optional[List[PanelVideoMeta]] = None  # 分镜结构化数据（与 image_urls 对应）
    provider: str = "doubao"             # 默认使用豆包


class VideoJobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None


class EpisodeVideoResponse(BaseModel):
    """分集视频生成响应"""
    message: str
    jobs: List[dict]   # [{job_id, image_url, status}]
    total: int


# ============ Routes ============

@router.post("/episode/{episode_num}/generate-video", response_model=EpisodeVideoResponse)
async def generate_episode_video(
    episode_num: int,
    request: EpisodeVideoRequest,
    db: Session = Depends(get_db),
):
    """
    为分集中的场景图片生成视频

    接收图片 URL 列表, 为每张图片创建一个视频生成任务 (使用豆包视频模型)
    """
    if not request.image_urls:
        raise HTTPException(status_code=400, detail="至少需要提供一张图片 URL")

    # 检查 Doubao API Key 是否配置
    api_key = getattr(settings, 'DOUBAO_VIDEO_API_KEY', None) or settings.DOUBAO_API_KEY
    if not api_key and request.provider == "doubao":
        raise HTTPException(
            status_code=400,
            detail="未配置 DOUBAO_API_KEY 或 DOUBAO_VIDEO_API_KEY，无法使用豆包视频服务"
        )

    # 确保 doubao provider 已注册
    from app.services.video.doubao_video_provider import DoubaoVideoProvider
    from app.services.video.video_provider_base import register_provider, get_video_provider
    if get_video_provider("doubao") is None and api_key:
        register_provider("doubao", DoubaoVideoProvider())

    jobs_created = []

    for idx, image_url in enumerate(request.image_urls):
        job_id = str(uuid.uuid4())

        # Use per-image duration if provided, otherwise fall back to global duration_sec
        img_duration = (
            request.duration_per_image[idx]
            if request.duration_per_image and idx < len(request.duration_per_image)
            else request.duration_sec
        )

        # 提取当前面板的结构化元数据（如果有）
        panel_meta_dict = None
        if request.panel_metadata and idx < len(request.panel_metadata):
            pm = request.panel_metadata[idx]
            panel_meta_dict = pm.model_dump(exclude_none=True)
            # 面板自带时长优先
            if pm.duration_sec is not None:
                img_duration = pm.duration_sec

        # 创建 Job 记录
        inputs = {
            "episode_number": episode_num,
            "image_url": image_url,
            "image_index": idx,
            "motion_prompt": request.motion_prompt,
            "duration_sec": img_duration,
            "provider": request.provider,
        }
        if panel_meta_dict:
            inputs["panel_metadata"] = panel_meta_dict

        job = Job(
            id=job_id,
            type="episode_video",
            provider=request.provider,
            project_id=request.project_id,
            status="queued",
            progress=0.0,
            attempt=1,
            max_attempts=3,
            cost_estimated=0.5,
            cost_used=0.0,
            inputs_json=inputs,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # 触发异步视频生成
        from app.workers.episode_video_worker import generate_episode_video_task
        generate_episode_video_task.delay(job_id, image_url, request.motion_prompt, img_duration, request.provider)

        jobs_created.append({
            "job_id": job_id,
            "image_url": image_url,
            "status": "queued",
        })

        logger.info(f"[EpisodeVideo] Created job {job_id} for episode {episode_num}, image #{idx}")

    return EpisodeVideoResponse(
        message=f"已创建 {len(jobs_created)} 个视频生成任务 (使用{request.provider})",
        jobs=jobs_created,
        total=len(jobs_created),
    )


@router.get("/episode/video-jobs/{job_id}", response_model=VideoJobStatusResponse)
async def get_video_job_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    """获取视频生成任务状态"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    outputs = job.outputs_json or {}
    inputs = job.inputs_json or {}

    return VideoJobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        image_url=inputs.get("image_url"),
        video_url=outputs.get("video_url"),
        error=(job.error_json or {}).get("message") if job.error_json else None,
    )


@router.get("/episode/video-jobs", response_model=List[VideoJobStatusResponse])
async def list_episode_video_jobs(
    project_id: str,
    episode_num: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """列出项目的视频生成任务"""
    query = db.query(Job).filter(
        Job.project_id == project_id,
        Job.type == "episode_video",
    )

    # Filter BEFORE truncation. ``episode_number`` lives inside the JSON
    # ``inputs_json`` column; JSON access syntax differs between SQLite
    # (dev) and Postgres (prod), so we pull a generous batch ordered
    # newest-first, filter in Python, then slice to the response cap.
    candidate_jobs = query.order_by(Job.created_at.desc()).limit(500).all()
    if episode_num is not None:
        candidate_jobs = [
            j for j in candidate_jobs
            if (j.inputs_json or {}).get("episode_number") == episode_num
        ]
    jobs = candidate_jobs[:50]

    results = []
    for job in jobs:
        outputs = job.outputs_json or {}
        inputs = job.inputs_json or {}

        results.append(VideoJobStatusResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            image_url=inputs.get("image_url"),
            video_url=outputs.get("video_url"),
            error=(job.error_json or {}).get("message") if job.error_json else None,
        ))

    return results


# ============ Phase D: Compose endpoints ============


class ComposeJobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    video_url: Optional[str] = None
    clip_count: Optional[int] = None
    duration_sec: Optional[float] = None
    error: Optional[str] = None


@router.get("/episode/compose-jobs/{job_id}", response_model=ComposeJobStatusResponse)
async def get_compose_job_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Phase D: status of an episode_video_compose job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Compose job not found")
    outputs = job.outputs_json or {}
    return ComposeJobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        video_url=outputs.get("video_url"),
        clip_count=outputs.get("clip_count"),
        duration_sec=outputs.get("duration_sec"),
        error=(job.error_json or {}).get("message") if job.error_json else None,
    )


class ComposeRetryRequest(BaseModel):
    project_id: str


class ComposeRetryResponse(BaseModel):
    job_id: str
    status: str


@router.post("/episode/{episode_num}/compose-video/retry", response_model=ComposeRetryResponse)
async def retry_episode_compose(
    episode_num: int,
    request: ComposeRetryRequest,
    db: Session = Depends(get_db),
):
    """Phase D: manually enqueue a fresh compose for an episode.

    Used when compose itself failed but every per-panel clip is still 'succeeded'.
    Bypasses the dedup check (returns a new job_id even if a prior succeeded
    compose row exists), but still enforces the all-clips-succeeded rule.
    """
    candidates = db.query(Job).filter(
        Job.type == "episode_video",
        Job.project_id == request.project_id,
    ).all()
    siblings = [
        j for j in candidates
        if (j.inputs_json or {}).get("episode_number") == episode_num
    ]
    if not siblings:
        raise HTTPException(status_code=404, detail="No per-panel clips for episode")
    if any(j.status != "succeeded" for j in siblings):
        raise HTTPException(
            status_code=409,
            detail="Cannot compose: one or more sibling clips are not 'succeeded'",
        )

    compose_job_id = str(uuid.uuid4())
    job = Job(
        id=compose_job_id,
        type="episode_video_compose",
        provider="ffmpeg",
        project_id=request.project_id,
        status="queued",
        inputs_json={
            "episode_number": episode_num,
            "expected_clip_count": len(siblings),
        },
    )
    db.add(job)
    db.commit()

    from app.workers.episode_compose_worker import execute_episode_compose
    execute_episode_compose.delay(compose_job_id)

    logger.info(
        "[EpisodeCompose] retry enqueued %s for project=%s ep=%s clips=%d",
        compose_job_id, request.project_id, episode_num, len(siblings),
    )
    return ComposeRetryResponse(job_id=compose_job_id, status="queued")
