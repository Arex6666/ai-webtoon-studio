"""
Bundle Worker - 章节打包任务执行者

集成 BundleBuilder 和 Celery 任务
"""
import logging
from celery import shared_task
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import SessionLocal
from app.models import Job, Export, Chapter
from app.api.routes.ws import push_chapter_update
from app.services.export.bundle_builder import get_bundle_builder
from app.services.export.bundle_models import BundleBuildContext
from app.services.export.bundle_errors import BundleBuildError

logger = logging.getLogger(__name__)


def sync_push_update(chapter_id: str, event_type: str, payload: dict):
    """同步推送 WS 消息"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(push_chapter_update(chapter_id, event_type, payload))


@shared_task(bind=True, name="app.workers.bundle_worker.export_bundle_task")
def export_bundle_task(self, job_id: str, chapter_id: str, export_id: str):
    """
    执行 Bundle 导出任务
    """
    logger.info(f"Starting bundle export task: job={job_id} chapter={chapter_id}")
    
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        export = db.query(Export).filter(Export.id == export_id).first()
        
        if not job or not export:
            logger.error(f"Job or Export not found: {job_id}, {export_id}")
            return
            
        # 更新状态：Running
        job.start()
        export.state = "running"
        db.commit()
        
        # 定义进度回调
        def progress_callback(job_id, stage, progress, message=None, panel_index=None):
            # 更新 Job
            job.progress = progress
            db.add(job)  # Ensure session tracks it
            db.commit()
            
            # 推送 WS
            payload = {
                "job_id": job_id,
                "export_id": export_id,
                "status": "running",
                "stage": stage,
                "progress": progress,
                "message": message,
                "panel_index": panel_index
            }
            sync_push_update(chapter_id, "export_progress", payload)
            logger.info(f"[BundleJob] {stage}: {progress:.2%} - {message}")

        # 创建构建上下文
        context = BundleBuildContext(
            export_id=export_id,
            job_id=job_id,
            chapter_id=chapter_id,
            progress_callback=progress_callback
        )
        
        # 执行构建
        builder = get_bundle_builder(db, context)
        result = await_in_sync(builder.build())
        
        if result.success:
            # 更新 Job 成功
            outputs = {
                "bundle_url": result.bundle_url,
                "manifest_url": result.manifest_url,
                "total_bytes": result.total_bytes,
                "panel_count": result.panel_count,
                "qa_summary": result.qa_summary
            }
            job.succeed(outputs)
            
            # 更新 Export 成功
            export.state = "succeeded"
            export.output_uri = result.bundle_url
            export.settings_json = {
                **(export.settings_json or {}), 
                "manifest_url": result.manifest_url,
                "total_bytes": result.total_bytes,
                "qa_summary": result.qa_summary
            }
            db.commit()
            
            # 推送成功消息
            sync_push_update(chapter_id, "export_status", {
                "job_id": job_id,
                "export_id": export_id,
                "status": "succeeded",
                "bundle_url": result.bundle_url,
                "manifest_url": result.manifest_url
            })
            
        else:
            # 失败处理
            error_data = {
                "code": result.error_code,
                "message": result.error_message,
                "panel_index": result.error_panel_index
            }
            job.fail(error_data)
            
            export.state = "failed"
            db.commit()
            
            sync_push_update(chapter_id, "export_status", {
                "job_id": job_id,
                "export_id": export_id,
                "status": "failed",
                "error": error_data
            })
            
    except Exception as e:
        logger.exception(f"Bundle export task unexpected failed: {e}")
        if job:
            job.fail({"code": "INTERNAL_ERROR", "message": str(e)})
        if export:
            export.state = "failed"
        db.commit()
        
        sync_push_update(chapter_id, "export_status", {
            "job_id": job_id,
            "export_id": export_id,
            "status": "failed",
            "error": {"code": "INTERNAL_ERROR", "message": str(e)}
        })
        
    finally:
        db.close()


def await_in_sync(awaitable):
    """在同步函数中等待异步结果"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(awaitable)
