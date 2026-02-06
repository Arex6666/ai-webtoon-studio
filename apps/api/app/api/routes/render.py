"""
渲染路由 - 图层生成
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

from app.core.database import get_db
from app.core.storage import storage_client
from app.models.panel import Panel
from app.models.render_job import RenderJob, JobType, JobStatus
from app.models.asset import Asset
from app.schemas.panel_spec import PanelSpec
from app.schemas.layer_pack_meta import LayerPackMeta, LayerFiles, QAResult, GenerationParams
from app.services.layer_factory import get_comfyui_client, PayloadBuilder

router = APIRouter()
logger = logging.getLogger(__name__)


class RenderRequest(BaseModel):
    panel_id: str
    force_regenerate: bool = False


class RenderResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    current_step: Optional[str]
    result: Optional[Dict[str, Any]]
    error: Optional[str]


# Routes
@router.post("/panel", response_model=RenderResponse)
async def render_panel(
    request: RenderRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    渲染分镜 - 生成图层包
    异步执行，返回任务 ID
    """
    panel = db.query(Panel).filter(Panel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    # 检查是否已有渲染结果
    if panel.render_status == "rendered" and not request.force_regenerate:
        return RenderResponse(
            job_id="",
            status="already_rendered",
            message="Panel already rendered. Set force_regenerate=true to regenerate."
        )
    
    # 创建渲染任务
    job = RenderJob(
        panel_id=panel.id,
        job_type=JobType.LAYER_GENERATION.value,
        status=JobStatus.PENDING.value,
        input_params={"panel_spec": panel.spec_json}
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # 更新分镜状态
    panel.render_status = "rendering"
    db.commit()
    
    # 启动后台任务
    background_tasks.add_task(
        execute_render_job,
        job_id=job.id,
        panel_id=panel.id
    )
    
    return RenderResponse(
        job_id=job.id,
        status="queued",
        message="Render job queued"
    )


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """获取渲染任务状态"""
    job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        result=job.output_data,
        error=job.error_message
    )


@router.post("/job/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """取消渲染任务"""
    job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
        raise HTTPException(status_code=400, detail="Job already finished")
    
    job.status = JobStatus.CANCELLED.value
    db.commit()
    
    # 尝试取消 ComfyUI 任务
    client = get_comfyui_client()
    await client.cancel_job(job_id)
    
    return {"message": "Job cancelled", "job_id": job_id}


@router.get("/panel/{panel_id}/layers")
async def get_panel_layers(
    panel_id: str,
    db: Session = Depends(get_db)
):
    """获取分镜的图层包信息"""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    # 获取最新完成的渲染任务
    job = db.query(RenderJob).filter(
        RenderJob.panel_id == panel_id,
        RenderJob.status == JobStatus.COMPLETED.value
    ).order_by(RenderJob.completed_at.desc()).first()
    
    if not job or not job.output_data:
        return {
            "panel_id": panel_id,
            "status": "not_rendered",
            "layers": []
        }
    
    return {
        "panel_id": panel_id,
        "status": "rendered",
        "layer_pack": job.output_data
    }


# Background Task
async def execute_render_job(job_id: str, panel_id: str):
    """
    执行渲染任务（后台）
    """
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        
        if not job or not panel:
            return
        
        # 更新状态
        job.status = JobStatus.PROCESSING.value
        job.current_step = "Initializing"
        job.progress = 5
        db.commit()
        
        # 获取 ComfyUI 客户端
        client = get_comfyui_client()
        payload_builder = PayloadBuilder()
        
        # 解析 PanelSpec
        panel_spec = PanelSpec(**panel.spec_json) if panel.spec_json else PanelSpec(panel_id=panel_id)
        
        # 获取关联资产
        character_data = None
        scene_data = None
        
        for char in panel_spec.characters:
            asset = db.query(Asset).filter(Asset.id == char.character_id).first()
            if asset:
                character_data = asset.data_json
                break
        
        if panel_spec.scene.scene_id:
            asset = db.query(Asset).filter(Asset.id == panel_spec.scene.scene_id).first()
            if asset:
                scene_data = asset.data_json
        
        # 构建工作流
        job.current_step = "Building workflow"
        job.progress = 10
        db.commit()
        
        workflow = payload_builder.build_character_workflow(
            panel_spec=panel_spec,
            character_data=character_data,
            scene_data=scene_data
        )
        
        # 提交到 ComfyUI
        job.current_step = "Submitting to render engine"
        job.progress = 20
        db.commit()
        
        comfy_job_id = await client.submit_workflow(workflow)
        
        # 轮询状态
        job.current_step = "Rendering"
        db.commit()
        
        import asyncio
        max_attempts = 120  # 最多等待 2 分钟
        
        for i in range(max_attempts):
            status = await client.poll_status(comfy_job_id)
            
            if status.get("status") == "completed":
                job.progress = 80
                db.commit()
                break
            elif status.get("status") == "failed":
                raise Exception(status.get("error", "Render failed"))
            elif status.get("status") == "cancelled":
                job.status = JobStatus.CANCELLED.value
                db.commit()
                return
            
            job.progress = min(20 + (i / max_attempts) * 60, 75)
            db.commit()
            
            await asyncio.sleep(1)
        
        # 获取输出
        job.current_step = "Fetching outputs"
        job.progress = 85
        db.commit()
        
        # 使用 MockComfyUI 的分层输出方法
        if hasattr(client, 'fetch_layer_outputs'):
            layer_outputs = await client.fetch_layer_outputs(comfy_job_id)
        else:
            # 回退到普通方法
            outputs = await client.fetch_outputs(comfy_job_id)
            layer_outputs = {"full": outputs[0]} if outputs else {}
        
        # 上传到存储
        job.current_step = "Uploading to storage"
        job.progress = 90
        db.commit()
        
        pack_id = str(uuid.uuid4())
        folder = f"panels/{panel_id}/{pack_id}"
        
        layers_data = []
        first_layer_path = None
        
        for layer_type, data in layer_outputs.items():
            filename = f"{layer_type}.png"
            path = storage_client.upload_file(
                data=data,
                filename=filename,
                content_type="image/png",
                folder=folder
            )
            
            if first_layer_path is None and layer_type == "full":
                first_layer_path = path
            
            layers_data.append({
                "type": layer_type if layer_type in ["full", "char", "bg", "fg", "mask"] else "full",
                "filename": filename,
                "storage_path": path,
                "width": 1024,
                "height": 1024
            })
        
        if first_layer_path is None and layers_data:
            first_layer_path = layers_data[0]["storage_path"]
        
        # 构建 LayerPackMeta（使用纯字典避免序列化问题）
        layer_pack_data = {
            "pack_id": pack_id,
            "panel_id": panel_id,
            "layers": layers_data,
            "canvas_width": 1024,
            "canvas_height": 1024,
            "status": "completed",
            "qa_score": {"overall": 0.9, "issues": []},
            "created_at": datetime.utcnow().isoformat()
        }
        
        # 更新任务和分镜
        job.status = JobStatus.COMPLETED.value
        job.progress = 100
        job.current_step = "Complete"
        job.output_data = layer_pack_data
        job.result_url = storage_client.get_url(first_layer_path) if first_layer_path else None
        
        panel.render_status = "rendered"
        panel.active_layer_pack_id = pack_id
        panel.qa_score = 0.9
        
        job.completed_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"Render job completed: {job_id}")
        
    except Exception as e:
        logger.error(f"Render job failed: {job_id} - {e}")
        if job:
            job.status = JobStatus.FAILED.value
            job.error_message = str(e)
            db.commit()
        if panel:
            panel.render_status = "failed"
            db.commit()
    finally:
        db.close()
