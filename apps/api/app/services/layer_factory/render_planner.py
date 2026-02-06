"""
RenderPlanner - 渲染计划生成器
整合DependencyGraph，生成优化的渲染执行计划
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum

from app.services.graph.dependency_graph import DependencyGraph, RenderTarget, RenderPlan

logger = logging.getLogger(__name__)


class RenderPriority(str, Enum):
    """渲染优先级"""
    URGENT = "urgent"       # 立即执行
    HIGH = "high"           # 优先队列
    NORMAL = "normal"       # 正常队列
    LOW = "low"             # 低优先级


class RenderJobStatus(str, Enum):
    """渲染任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RenderJob(BaseModel):
    """渲染任务"""
    id: str = Field(..., description="任务ID")
    panel_id: str = Field(..., description="分镜ID")
    render_target: RenderTarget = Field(..., description="渲染目标类型")
    priority: RenderPriority = Field(default=RenderPriority.NORMAL)
    status: RenderJobStatus = Field(default=RenderJobStatus.PENDING)
    dependencies: List[str] = Field(default_factory=list, description="依赖的任务ID")
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)
    error: Optional[str] = Field(None)
    result_url: Optional[str] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    """执行计划"""
    id: str = Field(..., description="计划ID")
    storyboard_id: str = Field(..., description="分镜ID")
    jobs: List[RenderJob] = Field(default_factory=list, description="任务列表")
    total_jobs: int = Field(0)
    estimated_duration_seconds: int = Field(0)
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = Field("pending")


class RenderPlanner:
    """
    渲染计划生成器
    
    功能:
    1. 分析分镜变更生成最小渲染集
    2. 构建任务依赖图
    3. 优化执行顺序
    4. 估算渲染时间
    """

    # 估计渲染时间（秒）
    RENDER_TIME_ESTIMATES = {
        RenderTarget.FULL_RENDER: 30,
        RenderTarget.TYPESET_ONLY: 5,
        RenderTarget.COMPOSITE: 10,
        RenderTarget.NONE: 0,
    }

    def __init__(self):
        self.dependency_graph = DependencyGraph()
        self._plan_counter = 0
        self._job_counter = 0

    def create_full_render_plan(
        self,
        storyboard: Dict[str, Any],
        storyboard_id: str,
        priority: RenderPriority = RenderPriority.NORMAL,
    ) -> ExecutionPlan:
        """
        创建完整渲染计划（所有分镜）
        
        Args:
            storyboard: 分镜数据
            storyboard_id: 分镜ID
            priority: 渲染优先级
            
        Returns:
            执行计划
        """
        panels = storyboard.get("panels", [])
        jobs = []
        
        for i, panel in enumerate(panels):
            job = self._create_job(
                panel_id=panel.get("panel_id", f"panel_{i}"),
                render_target=RenderTarget.FULL_RENDER,
                priority=priority,
                panel_data=panel,
            )
            jobs.append(job)
        
        return self._build_plan(storyboard_id, jobs)

    def create_incremental_plan(
        self,
        storyboard: Dict[str, Any],
        storyboard_id: str,
        patches: List[Dict[str, Any]],
        priority: RenderPriority = RenderPriority.NORMAL,
    ) -> ExecutionPlan:
        """
        创建增量渲染计划（仅变更部分）
        
        Args:
            storyboard: 分镜数据
            storyboard_id: 分镜ID
            patches: 变更的Patch列表
            priority: 渲染优先级
            
        Returns:
            执行计划
        """
        # 使用DependencyGraph分析影响
        patch_paths = [p.get("path", "") for p in patches]
        render_plan = self.dependency_graph.build_render_plan(storyboard, patch_paths)
        
        jobs = []
        panels = storyboard.get("panels", [])
        
        # 添加完整渲染任务
        for panel_id in render_plan.full_render_panels:
            idx = self._extract_panel_index(panel_id)
            panel_data = panels[idx] if idx < len(panels) else {}
            job = self._create_job(
                panel_id=panel_id,
                render_target=RenderTarget.FULL_RENDER,
                priority=priority,
                panel_data=panel_data,
            )
            jobs.append(job)
        
        # 添加排版任务
        for panel_id in render_plan.typeset_only_panels:
            idx = self._extract_panel_index(panel_id)
            panel_data = panels[idx] if idx < len(panels) else {}
            job = self._create_job(
                panel_id=panel_id,
                render_target=RenderTarget.TYPESET_ONLY,
                priority=priority,
                panel_data=panel_data,
            )
            jobs.append(job)
        
        # 添加合成任务
        for panel_id in render_plan.composite_panels:
            idx = self._extract_panel_index(panel_id)
            panel_data = panels[idx] if idx < len(panels) else {}
            job = self._create_job(
                panel_id=panel_id,
                render_target=RenderTarget.COMPOSITE,
                priority=priority,
                panel_data=panel_data,
            )
            jobs.append(job)
        
        return self._build_plan(storyboard_id, jobs)

    def create_selective_plan(
        self,
        storyboard: Dict[str, Any],
        storyboard_id: str,
        panel_ids: List[str],
        render_target: RenderTarget = RenderTarget.FULL_RENDER,
        priority: RenderPriority = RenderPriority.NORMAL,
    ) -> ExecutionPlan:
        """
        创建选择性渲染计划（指定分镜）
        
        Args:
            storyboard: 分镜数据
            storyboard_id: 分镜ID
            panel_ids: 要渲染的分镜ID列表
            render_target: 渲染目标类型
            priority: 渲染优先级
            
        Returns:
            执行计划
        """
        panels = storyboard.get("panels", [])
        jobs = []
        
        for panel_id in panel_ids:
            idx = self._extract_panel_index(panel_id)
            panel_data = panels[idx] if idx < len(panels) else {}
            job = self._create_job(
                panel_id=panel_id,
                render_target=render_target,
                priority=priority,
                panel_data=panel_data,
            )
            jobs.append(job)
        
        return self._build_plan(storyboard_id, jobs)

    def optimize_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        优化执行计划
        
        优化策略:
        1. 按渲染类型分组（可并行）
        2. 优先执行快速任务
        3. 考虑资源限制
        """
        # 按优先级和渲染类型排序
        priority_order = {
            RenderPriority.URGENT: 0,
            RenderPriority.HIGH: 1,
            RenderPriority.NORMAL: 2,
            RenderPriority.LOW: 3,
        }
        
        render_order = {
            RenderTarget.TYPESET_ONLY: 0,  # 快速任务先执行
            RenderTarget.COMPOSITE: 1,
            RenderTarget.FULL_RENDER: 2,
        }
        
        plan.jobs.sort(key=lambda j: (
            priority_order.get(j.priority, 2),
            render_order.get(j.render_target, 2),
        ))
        
        return plan

    def estimate_duration(self, plan: ExecutionPlan) -> int:
        """估算执行时间（秒）"""
        total = 0
        for job in plan.jobs:
            total += self.RENDER_TIME_ESTIMATES.get(job.render_target, 30)
        return total

    def get_parallel_batches(
        self,
        plan: ExecutionPlan,
        max_concurrent: int = 4,
    ) -> List[List[RenderJob]]:
        """
        获取可并行执行的任务批次
        
        Args:
            plan: 执行计划
            max_concurrent: 最大并发数
            
        Returns:
            任务批次列表
        """
        batches = []
        remaining_jobs = list(plan.jobs)
        
        while remaining_jobs:
            batch = []
            for job in remaining_jobs[:max_concurrent]:
                # 检查依赖是否已完成
                can_run = True
                for dep_id in job.dependencies:
                    if any(j.id == dep_id for j in remaining_jobs):
                        can_run = False
                        break
                
                if can_run:
                    batch.append(job)
            
            if not batch:
                # 无法继续，可能有循环依赖
                batch = remaining_jobs[:max_concurrent]
            
            batches.append(batch)
            for job in batch:
                remaining_jobs.remove(job)
        
        return batches

    def _create_job(
        self,
        panel_id: str,
        render_target: RenderTarget,
        priority: RenderPriority,
        panel_data: Optional[Dict[str, Any]] = None,
    ) -> RenderJob:
        """创建渲染任务"""
        self._job_counter += 1
        job_id = f"job_{self._job_counter:06d}"
        
        return RenderJob(
            id=job_id,
            panel_id=panel_id,
            render_target=render_target,
            priority=priority,
            metadata={"panel_data": panel_data} if panel_data else {},
        )

    def _build_plan(
        self,
        storyboard_id: str,
        jobs: List[RenderJob],
    ) -> ExecutionPlan:
        """构建执行计划"""
        self._plan_counter += 1
        plan_id = f"plan_{storyboard_id[:8]}_{self._plan_counter:04d}"
        
        plan = ExecutionPlan(
            id=plan_id,
            storyboard_id=storyboard_id,
            jobs=jobs,
            total_jobs=len(jobs),
        )
        
        plan.estimated_duration_seconds = self.estimate_duration(plan)
        return self.optimize_plan(plan)

    def _extract_panel_index(self, panel_id: str) -> int:
        """从panel_id提取索引"""
        try:
            if panel_id.startswith("panel_"):
                return int(panel_id.split("_")[1])
            return int(panel_id)
        except (ValueError, IndexError):
            return 0

    def get_plan_summary(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """获取计划摘要"""
        by_target = {}
        for job in plan.jobs:
            target = job.render_target.value
            by_target[target] = by_target.get(target, 0) + 1
        
        return {
            "id": plan.id,
            "total_jobs": plan.total_jobs,
            "by_render_target": by_target,
            "estimated_duration_seconds": plan.estimated_duration_seconds,
            "estimated_duration_human": self._format_duration(plan.estimated_duration_seconds),
        }

    def _format_duration(self, seconds: int) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            return f"{seconds // 60}分{seconds % 60}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}小时{minutes}分"
