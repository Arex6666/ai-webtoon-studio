"""
统一任务路由 - Jobs API (使用 Celery)
支持 image_job, anchor_job, video_job, export_job
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
import uuid
import logging

from app.schemas.job_schemas import JobCreateRequest, JobStatusResponse as UnifiedJobResponse
from app.celery_app import celery_app

from app.db.database import get_db
from app.models import Job, Panel, Chapter, Clip, Timeline

# Celery Workers
from app.workers.image_worker import execute_image_job
from app.workers.anchor_worker import execute_anchor_job
from app.workers.video_worker import execute_video_job
from app.workers.export_worker import execute_export_job

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class JobType(str, Enum):
    IMAGE = "image_job"
    ANCHOR = "anchor_job"
    VIDEO = "video_job"
    EXPORT = "export_job"


class ImageJobRequest(BaseModel):
    panel_id: str
    provider: Optional[str] = "comfyui"
    inputs: Optional[Dict[str, Any]] = None


class AnchorJobRequest(BaseModel):
    panel_id: str
    kind: str  # depth, pose, seg, lineart, canny, scribble
    source_image_url: str


class VideoJobRequest(BaseModel):
    clip_id: str
    start_frame_url: str
    end_frame_url: Optional[str] = None
    motion_prompt: str
    duration_sec: float = 3.0
    fps: int = 8
    provider: Optional[str] = "mock"


class ExportJobRequest(BaseModel):
    chapter_id: str
    export_spec: Optional[Dict[str, Any]] = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    type: str
    status: str
    progress: float
    provider: Optional[str]
    attempt: int
    max_attempts: int
    started_at: Optional[str]
    finished_at: Optional[str]
    cost: Dict[str, float]
    result: Optional[Dict[str, Any]]
    error: Optional[Dict[str, Any]]


class JobListResponse(BaseModel):
    items: List[JobStatusResponse]
    total: int


# ============ Helper Functions ============

def create_job_record(
    db: Session,
    job_type: str,
    provider: str,
    inputs: Dict[str, Any],
    panel_id: Optional[str] = None,
    clip_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Job:
    """创建 Job 记录"""
    job = Job(
        id=str(uuid.uuid4()),
        type=job_type,
        provider=provider,
        project_id=project_id,
        chapter_id=chapter_id,
        panel_id=panel_id,
        clip_id=clip_id,
        inputs_json=inputs,
        status="queued",
        progress=0.0,
        attempt=1,
        max_attempts=3,
        cost_estimated=5.0,
        cost_used=0.0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def job_to_response(job: Job) -> JobStatusResponse:
    """转换 Job 到响应格式"""
    return JobStatusResponse(
        job_id=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress,
        provider=job.provider,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        cost={"estimated": job.cost_estimated, "used": job.cost_used},
        result=job.outputs_json,
        error=job.error_json,
    )


# ============ Routes ============

@router.post("/", response_model=UnifiedJobResponse)
async def create_unified_job(
    req: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Unified job creation — single entry point for all job types."""
    target_field_map = {
        "image": "panel_id",
        "video": "clip_id",
        "storyboard": "chapter_id",
        "export": "chapter_id",
    }
    target_field = target_field_map.get(req.type)
    if not target_field:
        raise HTTPException(status_code=400, detail=f"Unknown job type: {req.type}")

    job = create_job_record(
        db=db,
        job_type=req.type,
        provider=req.provider,
        inputs=req.params,
        **{target_field: req.target_id},
    )

    TASK_MAP = {
        "image": ("app.workers.image_worker.execute_image_job", "image", [job.id, req.target_id]),
        "video": ("app.workers.video_worker.execute_video_job", "video", [job.id, req.target_id]),
        "export": ("app.workers.export_worker.execute_export_job", "export", [job.id, req.target_id]),
    }
    if req.type in TASK_MAP:
        task_name, queue, args = TASK_MAP[req.type]
        celery_app.send_task(task_name, args=args, queue=queue)
    elif req.type == "storyboard":
        from app.api.routes.chapters import run_storyboard_task
        background_tasks.add_task(
            run_storyboard_task,
            job_id=job.id,
            chapter_id=req.target_id,
            script=req.params.get("script", ""),
            provider=req.provider,
        )

    return UnifiedJobResponse(
        job_id=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress or 0.0,
        created_at=job.created_at.isoformat() if job.created_at else None,
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
    )


@router.post("/image", response_model=JobResponse)
async def create_image_job(
    request: ImageJobRequest,
    db: Session = Depends(get_db)
):
    """创建图像生成任务"""
    # 验证 panel 存在
    panel = db.query(Panel).filter(Panel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    # 创建 Job 记录
    job = create_job_record(
        db=db,
        job_type=JobType.IMAGE.value,
        provider=request.provider or "comfyui",
        inputs=request.inputs or {},
        panel_id=request.panel_id,
        chapter_id=panel.chapter_id,
    )
    
    # 异步执行
    execute_image_job.delay(job.id, request.panel_id)
    
    logger.info(f"Image job created: {job.id} for panel {request.panel_id}")
    
    return JobResponse(
        job_id=job.id,
        status="queued",
        message="Image job queued"
    )


@router.post("/anchor", response_model=JobResponse)
async def create_anchor_job(
    request: AnchorJobRequest,
    db: Session = Depends(get_db)
):
    """创建控制图生成任务"""
    panel = db.query(Panel).filter(Panel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    job = create_job_record(
        db=db,
        job_type=JobType.ANCHOR.value,
        provider="comfyui",
        inputs={
            "kind": request.kind,
            "source_image_url": request.source_image_url,
        },
        panel_id=request.panel_id,
        chapter_id=panel.chapter_id,
    )
    
    execute_anchor_job.delay(job.id, request.panel_id, request.kind)
    
    return JobResponse(
        job_id=job.id,
        status="queued",
        message=f"Anchor job ({request.kind}) queued"
    )


@router.post("/video", response_model=JobResponse)
async def create_video_job(
    request: VideoJobRequest,
    db: Session = Depends(get_db)
):
    """创建视频生成任务"""
    clip = db.query(Clip).filter(Clip.id == request.clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    
    timeline = db.query(Timeline).filter(Timeline.id == clip.timeline_id).first()
    chapter_id = timeline.chapter_id if timeline else None
    
    job = create_job_record(
        db=db,
        job_type=JobType.VIDEO.value,
        provider=request.provider or "mock",
        inputs={
            "start_frame_url": request.start_frame_url,
            "end_frame_url": request.end_frame_url,
            "motion_prompt": request.motion_prompt,
            "duration_sec": request.duration_sec,
            "fps": request.fps,
        },
        clip_id=request.clip_id,
        chapter_id=chapter_id,
    )
    
    execute_video_job.delay(job.id, request.clip_id)
    
    return JobResponse(
        job_id=job.id,
        status="queued",
        message="Video job queued"
    )


@router.post("/export", response_model=JobResponse)
async def create_export_job(
    request: ExportJobRequest,
    db: Session = Depends(get_db)
):
    """创建导出任务"""
    chapter = db.query(Chapter).filter(Chapter.id == request.chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    job = create_job_record(
        db=db,
        job_type=JobType.EXPORT.value,
        provider="local",
        inputs=request.export_spec or {},
        chapter_id=request.chapter_id,
        project_id=chapter.project_id,
    )
    
    execute_export_job.delay(job.id, request.chapter_id)
    
    return JobResponse(
        job_id=job.id,
        status="queued",
        message="Export job queued"
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """获取任务状态"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_to_response(job)


@router.get("/chapter/{chapter_id}", response_model=JobListResponse)
async def list_chapter_jobs(
    chapter_id: str,
    type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """列出章节相关的任务"""
    query = db.query(Job).filter(Job.chapter_id == chapter_id)
    
    if type:
        query = query.filter(Job.type == type)
    
    jobs = query.order_by(Job.created_at.desc()).limit(100).all()
    
    return JobListResponse(
        items=[job_to_response(j) for j in jobs],
        total=len(jobs)
    )


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """取消任务"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status in ["succeeded", "failed"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed job")
    
    job.status = "canceled"
    job.finished_at = datetime.utcnow()
    db.commit()
    
    # TODO: 实际取消 Celery 任务
    
    return {"message": "Job canceled", "job_id": job_id}
