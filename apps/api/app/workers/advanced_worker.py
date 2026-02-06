"""
高级生成 Worker
"""
from celery import shared_task
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import logging
import uuid
import time

from app.db.database import SessionLocal
from app.models import Job, Panel, LayerPack
from app.api.routes.ws import push_job_update
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_event_loop():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def push_update_sync(chapter_id: str, job_id: str, panel_id: str, status: str, progress: float, step: str = None):
    try:
        loop = get_event_loop()
        loop.run_until_complete(
            push_job_update(chapter_id, job_id, panel_id, status, progress, step)
        )
    except Exception as e:
        logger.warning(f"WS push failed: {e}")


@shared_task(bind=True, name="app.workers.advanced_worker.execute_ipadapter_job")
def execute_ipadapter_job(self, job_id: str, panel_id: str):
    """IP-Adapter 角色一致性生成"""
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not job or not panel:
            return {"success": False, "error": "Not found"}
        
        chapter_id = panel.chapter_id
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        push_update_sync(chapter_id, job_id, panel_id, "running", 0, "loading_ipadapter")
        
        inputs = job.inputs_json or {}
        
        if settings.COMFYUI_URL:
            from app.services.layer_factory.advanced_adapter import get_advanced_adapter
            adapter = get_advanced_adapter()
            loop = get_event_loop()
            
            result = loop.run_until_complete(
                adapter.generate_with_reference(
                    positive_prompt=inputs.get("positive_prompt", ""),
                    reference_image_url=inputs.get("reference_image_url", ""),
                    ipadapter_weight=inputs.get("ipadapter_weight", 0.8),
                    seed=inputs.get("seed"),
                    steps=inputs.get("steps", 20),
                    progress_callback=lambda p: push_update_sync(chapter_id, job_id, panel_id, "running", p, "generating")
                )
            )
            outputs = {"outputs": result}
        else:
            # Mock
            for p in [0.2, 0.4, 0.6, 0.8, 1.0]:
                time.sleep(0.5)
                push_update_sync(chapter_id, job_id, panel_id, "running", p, "generating")
            
            outputs = {
                "layerpack_id": f"lp-{int(time.time())}-{uuid.uuid4().hex[:6]}",
                "full_url": f"https://picsum.photos/seed/{panel_id}-ipa/1080/1920",
            }
        
        job.status = "succeeded"
        job.progress = 1.0
        job.outputs_json = outputs
        job.finished_at = datetime.utcnow()
        db.commit()
        
        push_update_sync(chapter_id, job_id, panel_id, "succeeded", 1.0, "completed")
        return {"success": True, "outputs": outputs}
        
    except Exception as e:
        logger.error(f"IPAdapter job {job_id} failed: {e}")
        if job:
            job.status = "failed"
            job.error_json = {"message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task(bind=True, name="app.workers.advanced_worker.execute_controlnet_job")
def execute_controlnet_job(self, job_id: str, panel_id: str):
    """ControlNet 控制生成"""
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not job or not panel:
            return {"success": False, "error": "Not found"}
        
        chapter_id = panel.chapter_id
        inputs = job.inputs_json or {}
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        push_update_sync(chapter_id, job_id, panel_id, "running", 0, "loading_controlnet")
        
        if settings.COMFYUI_URL:
            from app.services.layer_factory.advanced_adapter import get_advanced_adapter
            adapter = get_advanced_adapter()
            loop = get_event_loop()
            
            result = loop.run_until_complete(
                adapter.generate_with_control(
                    positive_prompt=inputs.get("positive_prompt", ""),
                    control_image_url=inputs.get("control_image_url", ""),
                    control_type=inputs.get("control_type", "depth"),
                    control_strength=inputs.get("control_strength", 0.8),
                    negative_prompt=inputs.get("negative_prompt", ""),
                    seed=inputs.get("seed"),
                    steps=inputs.get("steps", 20),
                    progress_callback=lambda p: push_update_sync(chapter_id, job_id, panel_id, "running", p, "generating")
                )
            )
            outputs = {"outputs": result}
        else:
            for p in [0.2, 0.4, 0.6, 0.8, 1.0]:
                time.sleep(0.5)
                push_update_sync(chapter_id, job_id, panel_id, "running", p, "generating")
            outputs = {
                "layerpack_id": f"lp-{int(time.time())}-{uuid.uuid4().hex[:6]}",
                "full_url": f"https://picsum.photos/seed/{panel_id}-cn/1080/1920",
            }
        
        job.status = "succeeded"
        job.progress = 1.0
        job.outputs_json = outputs
        job.finished_at = datetime.utcnow()
        db.commit()
        
        push_update_sync(chapter_id, job_id, panel_id, "succeeded", 1.0, "completed")
        return {"success": True, "outputs": outputs}
        
    except Exception as e:
        logger.error(f"ControlNet job {job_id} failed: {e}")
        if job:
            job.status = "failed"
            job.error_json = {"message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task(bind=True, name="app.workers.advanced_worker.execute_inpaint_job")
def execute_inpaint_job(self, job_id: str, panel_id: str):
    """局部重绘"""
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not job or not panel:
            return {"success": False, "error": "Not found"}
        
        chapter_id = panel.chapter_id
        inputs = job.inputs_json or {}
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        push_update_sync(chapter_id, job_id, panel_id, "running", 0, "inpainting")
        
        if settings.COMFYUI_URL:
            from app.services.layer_factory.advanced_adapter import get_advanced_adapter
            adapter = get_advanced_adapter()
            loop = get_event_loop()
            
            result = loop.run_until_complete(
                adapter.inpaint(
                    source_image_url=inputs.get("source_image_url", ""),
                    mask_image_url=inputs.get("mask_image_url", ""),
                    positive_prompt=inputs.get("positive_prompt", ""),
                    denoise=inputs.get("denoise", 0.8),
                    grow_mask=inputs.get("grow_mask", 8),
                    seed=inputs.get("seed"),
                    steps=inputs.get("steps", 20),
                    progress_callback=lambda p: push_update_sync(chapter_id, job_id, panel_id, "running", p, "inpainting")
                )
            )
            outputs = {"outputs": result}
        else:
            for p in [0.2, 0.4, 0.6, 0.8, 1.0]:
                time.sleep(0.5)
                push_update_sync(chapter_id, job_id, panel_id, "running", p, "inpainting")
            outputs = {
                "full_url": f"https://picsum.photos/seed/{panel_id}-inp/1080/1920",
            }
        
        job.status = "succeeded"
        job.progress = 1.0
        job.outputs_json = outputs
        job.finished_at = datetime.utcnow()
        db.commit()
        
        push_update_sync(chapter_id, job_id, panel_id, "succeeded", 1.0, "completed")
        return {"success": True, "outputs": outputs}
        
    except Exception as e:
        logger.error(f"Inpaint job {job_id} failed: {e}")
        if job:
            job.status = "failed"
            job.error_json = {"message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task(bind=True, name="app.workers.advanced_worker.execute_layer_separation_job")
def execute_layer_separation_job(self, job_id: str, panel_id: str):
    """图层分离"""
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not job or not panel:
            return {"success": False, "error": "Not found"}
        
        chapter_id = panel.chapter_id
        inputs = job.inputs_json or {}
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        push_update_sync(chapter_id, job_id, panel_id, "running", 0, "separating_layers")
        
        if settings.COMFYUI_URL:
            from app.services.layer_factory.advanced_adapter import get_advanced_adapter
            adapter = get_advanced_adapter()
            loop = get_event_loop()
            
            result = loop.run_until_complete(
                adapter.separate_layers(
                    source_image_url=inputs.get("source_image_url", ""),
                    point_coords=inputs.get("point_coords"),
                    progress_callback=lambda p: push_update_sync(chapter_id, job_id, panel_id, "running", p, "separating")
                )
            )
            outputs = {"outputs": result}
        else:
            for p in [0.3, 0.6, 1.0]:
                time.sleep(0.5)
                push_update_sync(chapter_id, job_id, panel_id, "running", p, "separating")
            outputs = {
                "mask_url": f"https://picsum.photos/seed/{panel_id}-mask/1080/1920",
                "char_url": f"https://picsum.photos/seed/{panel_id}-char/1080/1920",
                "bg_url": f"https://picsum.photos/seed/{panel_id}-bg/1080/1920",
            }
        
        job.status = "succeeded"
        job.progress = 1.0
        job.outputs_json = outputs
        job.finished_at = datetime.utcnow()
        db.commit()
        
        push_update_sync(chapter_id, job_id, panel_id, "succeeded", 1.0, "completed")
        return {"success": True, "outputs": outputs}
        
    except Exception as e:
        logger.error(f"Layer separation job {job_id} failed: {e}")
        if job:
            job.status = "failed"
            job.error_json = {"message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task(bind=True, name="app.workers.advanced_worker.execute_estimate_job")
def execute_estimate_job(self, job_id: str, panel_id: str, estimate_type: str):
    """控制图估计（深度图/姿态图）"""
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not job or not panel:
            return {"success": False, "error": "Not found"}
        
        chapter_id = panel.chapter_id
        inputs = job.inputs_json or {}
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        push_update_sync(chapter_id, job_id, panel_id, "running", 0, f"estimating_{estimate_type}")
        
        if settings.COMFYUI_URL:
            from app.services.layer_factory.advanced_adapter import get_advanced_adapter
            adapter = get_advanced_adapter()
            loop = get_event_loop()
            
            if estimate_type == "depth":
                result = loop.run_until_complete(
                    adapter.estimate_depth(inputs.get("source_image_url", ""))
                )
            else:
                result = loop.run_until_complete(
                    adapter.estimate_pose(inputs.get("source_image_url", ""))
                )
            outputs = {"outputs": result}
        else:
            time.sleep(1)
            outputs = {
                f"{estimate_type}_url": f"https://picsum.photos/seed/{panel_id}-{estimate_type}/1080/1920",
            }
        
        job.status = "succeeded"
        job.progress = 1.0
        job.outputs_json = outputs
        job.finished_at = datetime.utcnow()
        db.commit()
        
        push_update_sync(chapter_id, job_id, panel_id, "succeeded", 1.0, "completed")
        return {"success": True, "outputs": outputs}
        
    except Exception as e:
        logger.error(f"Estimate job {job_id} failed: {e}")
        if job:
            job.status = "failed"
            job.error_json = {"message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
