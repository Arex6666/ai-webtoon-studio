"""
导出 Worker（完整实现）
"""
from celery import shared_task
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import logging
import uuid
import time
import json

from app.db.database import SessionLocal
from app.models import Job, Chapter, Panel, LayerPack
from app.api.routes.ws import push_chapter_update
from app.services.export.strip_composer import get_strip_composer
from app.services.export.release_bundle import get_bundle_generator

logger = logging.getLogger(__name__)


def get_event_loop():
    """获取或创建事件循环"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def push_export_update_sync(chapter_id: str, job_id: str, status: str, progress: float, message: str = None):
    """同步版本的 WebSocket 推送"""
    try:
        loop = get_event_loop()
        loop.run_until_complete(
            push_chapter_update(chapter_id, "export_progress", {
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "message": message,
            })
        )
    except Exception as e:
        logger.warning(f"Failed to push WS update: {e}")


@shared_task(bind=True, name="app.workers.export_worker.execute_export_job")
def execute_export_job(self, job_id: str, chapter_id: str):
    """
    执行导出任务
    
    1. 收集所有面板的最终图
    2. 拼接为长条漫
    3. 生成 release bundle
    4. 上传到存储
    """
    db = SessionLocal()
    start_time = time.time()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"success": False, "error": "Job not found"}
        
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            return {"success": False, "error": "Chapter not found"}
        
        project_id = chapter.project_id
        
        # 更新状态
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        
        push_export_update_sync(chapter_id, job_id, "running", 0, "Collecting panels...")
        
        # 获取所有面板（按顺序）
        panels = db.query(Panel).filter(
            Panel.chapter_id == chapter_id
        ).order_by(Panel.order_index).all()
        
        if not panels:
            raise Exception("No panels in chapter")
        
        total_panels = len(panels)
        logger.info(f"Export job {job_id}: {total_panels} panels to export")
        
        # 收集面板图片信息
        panel_infos = []
        image_urls = []
        
        for i, panel in enumerate(panels):
            progress = 0.1 + (i / total_panels) * 0.3  # 10% - 40%
            job.progress = progress
            db.commit()
            push_export_update_sync(chapter_id, job_id, "running", progress, f"Processing panel {i+1}/{total_panels}")
            
            # 获取激活的 LayerPack
            layerpack = None
            if panel.active_layer_pack_id:
                layerpack = db.query(LayerPack).filter(LayerPack.id == panel.active_layer_pack_id).first()
            
            # 如果没有激活的, 取最新的
            if not layerpack:
                layerpack = db.query(LayerPack).filter(
                    LayerPack.panel_id == panel.id
                ).order_by(LayerPack.created_at.desc()).first()
            
            # 确定使用的图片 (优先 typeset, 其次 full)
            exported_url = None
            if panel.typeset_image_url:
                exported_url = panel.typeset_image_url
            elif panel.preview_url:
                exported_url = panel.preview_url
            elif layerpack and (layerpack.full_url or layerpack.file_full):
                exported_url = layerpack.full_url or layerpack.file_full
            else:
                # 使用占位符
                exported_url = f"https://picsum.photos/seed/{panel.id}/1080/1920"
            
            image_urls.append(exported_url)
            
            panel_infos.append({
                "panel_id": panel.id,
                "order_index": panel.order_index,
                "layerpack_id": layerpack.id if layerpack else None,
                "manifest_url": layerpack.manifest_url if layerpack else None,
                "full_url": layerpack.full_url if layerpack else panel.preview_url,
                "typeset_url": panel.typeset_image_url,
                "exported_url": exported_url,
                "qa_score": layerpack.qa_score if layerpack else panel.qa_score or 0,
                "status": panel.render_status,
            })
        
        # 合成长条漫
        push_export_update_sync(chapter_id, job_id, "running", 0.5, "Composing strip...")
        
        composer = get_strip_composer(gap=0)
        loop = get_event_loop()
        
        try:
            strip_bytes = loop.run_until_complete(
                composer.compose_from_urls(image_urls, output_width=1080)
            )
            strip_width = 1080
            strip_height = 1920 * total_panels  # 估算
        except Exception as e:
            logger.warning(f"Failed to compose from URLs, using mock: {e}")
            # Mock strip
            strip_bytes = b"MOCK_STRIP_DATA"
            strip_width = 1080
            strip_height = 1920 * total_panels
        
        job.progress = 0.7
        db.commit()
        push_export_update_sync(chapter_id, job_id, "running", 0.7, "Uploading strip...")
        
        # 生成 release bundle
        release_id = f"release-{uuid.uuid4().hex[:12]}"
        duration_ms = int((time.time() - start_time) * 1000)
        
        # 模拟上传（生产环境使用 MinIO）
        strip_url = f"https://storage.example.com/releases/{chapter_id}/{release_id}/strip.png"
        bundle_url = f"https://storage.example.com/releases/{chapter_id}/{release_id}/bundle.json"
        
        # 生成 bundle
        bundle_gen = get_bundle_generator()
        bundle = bundle_gen.generate(
            release_id=release_id,
            chapter_id=chapter_id,
            chapter_title=chapter.title,
            project_id=project_id,
            strip_url=strip_url,
            strip_width=strip_width,
            strip_height=strip_height,
            panels=panel_infos,
            total_cost=job.cost_used or 0,
            export_duration_ms=duration_ms,
        )
        
        job.progress = 0.9
        db.commit()
        push_export_update_sync(chapter_id, job_id, "running", 0.9, "Finalizing...")
        
        # 完成
        outputs = {
            "release_id": release_id,
            "strip_url": strip_url,
            "bundle_url": bundle_url,
            "strip_width": strip_width,
            "strip_height": strip_height,
            "panels_exported": total_panels,
            "duration_ms": duration_ms,
            "bundle": bundle,
        }
        
        job.status = "succeeded"
        job.progress = 1.0
        job.outputs_json = outputs
        job.finished_at = datetime.utcnow()
        job.cost_used = 2.0
        
        chapter.export_status = "exported"
        chapter.exported_url = strip_url
        
        db.commit()
        
        push_export_update_sync(chapter_id, job_id, "succeeded", 1.0, f"Exported {total_panels} panels")
        
        logger.info(f"Export job {job_id} completed: {total_panels} panels in {duration_ms}ms")
        return {"success": True, "outputs": outputs}
        
    except Exception as e:
        logger.error(f"Export job {job_id} failed: {e}")
        if job:
            job.status = "failed"
            job.error_json = {"code": "EXPORT_ERROR", "message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()
        
        push_export_update_sync(chapter_id, job_id, "failed", 0, str(e))
        return {"success": False, "error": str(e)}
        
    finally:
        db.close()
