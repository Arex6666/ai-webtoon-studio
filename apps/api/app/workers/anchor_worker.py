"""
Anchor 生成 Worker (控制图)
"""
from celery import shared_task
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import logging
import uuid
import time

from app.db.database import SessionLocal
from app.models import Job, Panel
from app.api.routes.ws import push_job_update

logger = logging.getLogger(__name__)


def push_update_sync(chapter_id: str, job_id: str, panel_id: str, status: str, progress: float, current_step: str = None):
    """同步版本的 WebSocket 推送"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            push_job_update(chapter_id, job_id, panel_id, status, progress, current_step)
        )
        loop.close()
    except Exception as e:
        logger.warning(f"Failed to push WS update: {e}")


@shared_task(bind=True, name="app.workers.anchor_worker.execute_anchor_job")
def execute_anchor_job(self, job_id: str, panel_id: str, kind: str):
    """
    执行 Anchor 生成任务
    
    kind: depth, pose, seg, lineart, canny, scribble
    """
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"success": False, "error": "Job not found"}
        
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not panel:
            return {"success": False, "error": "Panel not found"}
        
        chapter_id = panel.chapter_id
        
        # 更新状态
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        
        push_update_sync(chapter_id, job_id, panel_id, "running", 0, f"generating_{kind}")
        
        # 模拟生成
        time.sleep(2)
        job.progress = 0.5
        db.commit()
        push_update_sync(chapter_id, job_id, panel_id, "running", 0.5, "processing")
        
        time.sleep(2)
        
        # 生成结果
        anchor_id = f"anchor-{uuid.uuid4().hex[:8]}"
        outputs = {
            "anchor_id": anchor_id,
            "kind": kind,
            "control_image_url": f"https://picsum.photos/seed/{panel_id}-{kind}/1080/1920",
        }
        
        job.status = "succeeded"
        job.progress = 1.0
        job.outputs_json = outputs
        job.finished_at = datetime.utcnow()
        job.cost_used = 1.0
        db.commit()
        
        push_update_sync(chapter_id, job_id, panel_id, "succeeded", 1.0, "completed")
        
        logger.info(f"Anchor job {job_id} ({kind}) completed")
        return {"success": True, "outputs": outputs}
        
    except Exception as e:
        logger.error(f"Anchor job {job_id} failed: {e}")
        if job:
            job.status = "failed"
            job.error_json = {"code": "EXECUTION_ERROR", "message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()
        return {"success": False, "error": str(e)}
        
    finally:
        db.close()
