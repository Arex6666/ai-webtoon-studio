"""
Provenance Collector - 来源追溯收集器

负责收集章节内所有任务的执行历史，生成 provenance/jobs.json
"""
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import Panel, Job, RenderJob
from app.schemas.bundle_manifest import (
    ProvenanceJobsSpec, JobProvenanceRecord, JobAttemptRecord
)
from app.services.export.bundle_models import ChapterSnapshot, PanelArtifactPlan

logger = logging.getLogger(__name__)


class ProvenanceCollector:
    """任务历史收集器"""
    
    def __init__(self, db: Session):
        self.db = db
        self.jobs: Dict[str, JobProvenanceRecord] = {}
        
    def collect(
        self, 
        chapter_snapshot: ChapterSnapshot, 
        panel_plans: List[PanelArtifactPlan]
    ) -> ProvenanceJobsSpec:
        """
        收集整个章节的任务历史
        """
        logger.info(f"Collecting provenance for chapter {chapter_snapshot.chapter_id}")
        
        # 1. 收集所有相关 panel 的 job
        panel_ids = [p.panel_id for p in chapter_snapshot.panels]
        
        # 查询 RenderJob
        # TODO: 使用 RenderJob 表 (目前 Job 表混用了类型)
        jobs = self.db.query(Job).filter(
            Job.chapter_id == chapter_snapshot.chapter_id
        ).all()
        
        total_render = 0
        total_typeset = 0
        total_duration = 0
        
        for job in jobs:
            record = self._convert_job(job)
            self.jobs[job.id] = record
            
            if job.type == "render":
                total_render += 1
            elif job.type == "typeset":
                total_typeset += 1
                
            if record.duration_ms:
                total_duration += record.duration_ms
        
        return ProvenanceJobsSpec(
            spec_version="1.0.0",
            chapter_id=chapter_snapshot.chapter_id,
            exported_at=datetime.utcnow().isoformat(),
            jobs=list(self.jobs.values()),
            total_jobs=len(self.jobs),
            total_render_jobs=total_render,
            total_typeset_jobs=total_typeset,
            total_duration_ms=total_duration
        )
    
    def _convert_job(self, job: Job) -> JobProvenanceRecord:
        """转换 Job 模型为 Provenance 记录"""
        
        # 提取尝试记录
        attempts = []
        # TODO: 从 RenderAttempt 表查询 (如果已实现)
        
        # 提取参数摘要
        params = job.params_json or {}
        
        return JobProvenanceRecord(
            job_id=job.id,
            job_type=job.type,
            panel_id=job.panel_id,
            provider=job.provider or "unknown",
            created_at=job.created_at.isoformat() if job.created_at else "",
            finished_at=job.finished_at.isoformat() if job.finished_at else None,
            duration_ms=int((job.finished_at - job.started_at).total_seconds() * 1000) 
                if job.finished_at and job.started_at else None,
            seed=params.get("seed"),
            workflow_name=params.get("workflow"),
            model_name=params.get("model"),
            attempts=attempts
        )
