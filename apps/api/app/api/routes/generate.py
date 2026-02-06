"""
高级生成 API 路由
支持：角色一致性、ControlNet、Inpaint、图层分离
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

from app.db.database import get_db
from app.models import Job, Panel

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class IPAdapterRequest(BaseModel):
    """IP-Adapter 角色一致性请求"""
    panel_id: str
    reference_image_url: str
    positive_prompt: str
    ipadapter_weight: float = 0.8
    seed: Optional[int] = None
    steps: int = 20


class ControlNetRequest(BaseModel):
    """ControlNet 控制生成请求"""
    panel_id: str
    control_image_url: str
    control_type: str = "depth"  # depth, pose, canny, lineart, scribble
    control_strength: float = 0.8
    positive_prompt: str
    negative_prompt: str = ""
    seed: Optional[int] = None
    steps: int = 20


class InpaintRequest(BaseModel):
    """局部重绘请求"""
    panel_id: str
    source_image_url: str
    mask_image_url: str
    positive_prompt: str
    denoise: float = 0.8
    grow_mask: int = 8
    seed: Optional[int] = None
    steps: int = 20


class LayerSeparationRequest(BaseModel):
    """图层分离请求"""
    panel_id: str
    source_image_url: str
    point_coords: Optional[List[List[int]]] = None  # [[x, y], ...]


class ControlEstimateRequest(BaseModel):
    """控制图估计请求"""
    panel_id: str
    source_image_url: str
    estimate_type: str = "depth"  # depth, pose


class GenerationResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ============ Routes ============

@router.post("/ipadapter", response_model=GenerationResponse)
async def generate_with_ipadapter(
    request: IPAdapterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    IP-Adapter 角色一致性生成
    
    使用参考人物图片保持角色外观一致
    """
    panel = db.query(Panel).filter(Panel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    job = Job(
        id=str(uuid.uuid4()),
        type="image_job",
        provider="comfyui_ipadapter",
        panel_id=request.panel_id,
        chapter_id=panel.chapter_id,
        inputs_json={
            "reference_image_url": request.reference_image_url,
            "positive_prompt": request.positive_prompt,
            "ipadapter_weight": request.ipadapter_weight,
            "seed": request.seed,
            "steps": request.steps,
        },
        status="queued",
    )
    db.add(job)
    db.commit()
    
    # 异步执行
    from app.workers.advanced_worker import execute_ipadapter_job
    execute_ipadapter_job.delay(job.id, request.panel_id)
    
    return GenerationResponse(
        job_id=job.id,
        status="queued",
        message="IP-Adapter generation queued"
    )


@router.post("/controlnet", response_model=GenerationResponse)
async def generate_with_controlnet(
    request: ControlNetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    ControlNet 控制生成
    
    使用深度图/姿态图/边缘图控制生成
    """
    panel = db.query(Panel).filter(Panel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    job = Job(
        id=str(uuid.uuid4()),
        type="image_job",
        provider=f"comfyui_controlnet_{request.control_type}",
        panel_id=request.panel_id,
        chapter_id=panel.chapter_id,
        inputs_json={
            "control_image_url": request.control_image_url,
            "control_type": request.control_type,
            "control_strength": request.control_strength,
            "positive_prompt": request.positive_prompt,
            "negative_prompt": request.negative_prompt,
            "seed": request.seed,
            "steps": request.steps,
        },
        status="queued",
    )
    db.add(job)
    db.commit()
    
    from app.workers.advanced_worker import execute_controlnet_job
    execute_controlnet_job.delay(job.id, request.panel_id)
    
    return GenerationResponse(
        job_id=job.id,
        status="queued",
        message=f"ControlNet ({request.control_type}) generation queued"
    )


@router.post("/inpaint", response_model=GenerationResponse)
async def generate_inpaint(
    request: InpaintRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    局部重绘
    
    使用遮罩指定重绘区域
    """
    panel = db.query(Panel).filter(Panel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    job = Job(
        id=str(uuid.uuid4()),
        type="image_job",
        provider="comfyui_inpaint",
        panel_id=request.panel_id,
        chapter_id=panel.chapter_id,
        inputs_json={
            "source_image_url": request.source_image_url,
            "mask_image_url": request.mask_image_url,
            "positive_prompt": request.positive_prompt,
            "denoise": request.denoise,
            "grow_mask": request.grow_mask,
            "seed": request.seed,
            "steps": request.steps,
        },
        status="queued",
    )
    db.add(job)
    db.commit()
    
    from app.workers.advanced_worker import execute_inpaint_job
    execute_inpaint_job.delay(job.id, request.panel_id)
    
    return GenerationResponse(
        job_id=job.id,
        status="queued",
        message="Inpaint generation queued"
    )


@router.post("/layer-separation", response_model=GenerationResponse)
async def separate_layers(
    request: LayerSeparationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    图层分离
    
    分离角色和背景为两个图层
    """
    panel = db.query(Panel).filter(Panel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    job = Job(
        id=str(uuid.uuid4()),
        type="anchor_job",
        provider="comfyui_sam",
        panel_id=request.panel_id,
        chapter_id=panel.chapter_id,
        inputs_json={
            "source_image_url": request.source_image_url,
            "point_coords": request.point_coords,
        },
        status="queued",
    )
    db.add(job)
    db.commit()
    
    from app.workers.advanced_worker import execute_layer_separation_job
    execute_layer_separation_job.delay(job.id, request.panel_id)
    
    return GenerationResponse(
        job_id=job.id,
        status="queued",
        message="Layer separation queued"
    )


@router.post("/estimate-control", response_model=GenerationResponse)
async def estimate_control_image(
    request: ControlEstimateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    估计控制图
    
    从原图生成深度图/姿态图
    """
    panel = db.query(Panel).filter(Panel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    job = Job(
        id=str(uuid.uuid4()),
        type="anchor_job",
        provider=f"comfyui_{request.estimate_type}",
        panel_id=request.panel_id,
        chapter_id=panel.chapter_id,
        inputs_json={
            "source_image_url": request.source_image_url,
            "estimate_type": request.estimate_type,
        },
        status="queued",
    )
    db.add(job)
    db.commit()
    
    from app.workers.advanced_worker import execute_estimate_job
    execute_estimate_job.delay(job.id, request.panel_id, request.estimate_type)
    
    return GenerationResponse(
        job_id=job.id,
        status="queued",
        message=f"{request.estimate_type.capitalize()} estimation queued"
    )
