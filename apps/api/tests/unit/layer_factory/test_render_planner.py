"""
RenderPlanner 单元测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.layer_factory.render_planner import (
    RenderPlanner,
    RenderPriority,
    RenderJobStatus,
    RenderJob,
    ExecutionPlan,
)
from app.services.graph.dependency_graph import RenderTarget


class TestFullRenderPlan:
    """测试完整渲染计划"""

    def setup_method(self):
        self.planner = RenderPlanner()
        self.storyboard = {
            "panels": [
                {"panel_id": "panel_0", "description": "第一格"},
                {"panel_id": "panel_1", "description": "第二格"},
                {"panel_id": "panel_2", "description": "第三格"},
            ]
        }

    def test_create_full_plan(self):
        """测试创建完整渲染计划"""
        plan = self.planner.create_full_render_plan(
            self.storyboard,
            "sb_001"
        )
        
        assert isinstance(plan, ExecutionPlan)
        assert plan.total_jobs == 3
        assert all(j.render_target == RenderTarget.FULL_RENDER for j in plan.jobs)

    def test_full_plan_with_priority(self):
        """测试带优先级的完整计划"""
        plan = self.planner.create_full_render_plan(
            self.storyboard,
            "sb_001",
            priority=RenderPriority.URGENT
        )
        
        assert all(j.priority == RenderPriority.URGENT for j in plan.jobs)


class TestIncrementalPlan:
    """测试增量渲染计划"""

    def setup_method(self):
        self.planner = RenderPlanner()
        self.storyboard = {
            "panels": [
                {"panel_id": "panel_0", "description": "第一格"},
                {"panel_id": "panel_1", "description": "第二格"},
                {"panel_id": "panel_2", "description": "第三格"},
            ]
        }

    def test_dialogue_change_creates_typeset_job(self):
        """测试对白修改创建排版任务"""
        patches = [
            {"op": "replace", "path": "/panels/1/dialogue", "value": "新对白"},
        ]
        
        plan = self.planner.create_incremental_plan(
            self.storyboard,
            "sb_001",
            patches
        )
        
        # 应该有排版任务
        typeset_jobs = [j for j in plan.jobs if j.render_target == RenderTarget.TYPESET_ONLY]
        assert len(typeset_jobs) >= 1

    def test_camera_change_creates_full_render_job(self):
        """测试镜头修改创建完整渲染任务"""
        patches = [
            {"op": "replace", "path": "/panels/0/camera", "value": "close_up"},
        ]
        
        plan = self.planner.create_incremental_plan(
            self.storyboard,
            "sb_001",
            patches
        )
        
        # 应该有完整渲染任务
        full_jobs = [j for j in plan.jobs if j.render_target == RenderTarget.FULL_RENDER]
        assert len(full_jobs) >= 1


class TestSelectivePlan:
    """测试选择性渲染计划"""

    def setup_method(self):
        self.planner = RenderPlanner()
        self.storyboard = {
            "panels": [
                {"panel_id": "panel_0"},
                {"panel_id": "panel_1"},
                {"panel_id": "panel_2"},
            ]
        }

    def test_selective_render(self):
        """测试选择指定分镜渲染"""
        plan = self.planner.create_selective_plan(
            self.storyboard,
            "sb_001",
            panel_ids=["panel_0", "panel_2"]
        )
        
        assert plan.total_jobs == 2
        panel_ids = [j.panel_id for j in plan.jobs]
        assert "panel_0" in panel_ids
        assert "panel_2" in panel_ids
        assert "panel_1" not in panel_ids

    def test_selective_with_typeset_target(self):
        """测试选择排版目标"""
        plan = self.planner.create_selective_plan(
            self.storyboard,
            "sb_001",
            panel_ids=["panel_0"],
            render_target=RenderTarget.TYPESET_ONLY
        )
        
        assert plan.jobs[0].render_target == RenderTarget.TYPESET_ONLY


class TestDurationEstimation:
    """测试时长估算"""

    def setup_method(self):
        self.planner = RenderPlanner()

    def test_estimate_full_render_duration(self):
        """测试完整渲染时长估算"""
        storyboard = {
            "panels": [{"panel_id": f"panel_{i}"} for i in range(3)]
        }
        
        plan = self.planner.create_full_render_plan(storyboard, "sb_001")
        
        # 3个完整渲染任务，每个30秒
        assert plan.estimated_duration_seconds >= 90

    def test_typeset_faster_than_full(self):
        """测试排版比完整渲染快"""
        storyboard = {"panels": [{"panel_id": "panel_0"}]}
        
        full_plan = self.planner.create_selective_plan(
            storyboard, "sb_001",
            panel_ids=["panel_0"],
            render_target=RenderTarget.FULL_RENDER
        )
        
        typeset_plan = self.planner.create_selective_plan(
            storyboard, "sb_001",
            panel_ids=["panel_0"],
            render_target=RenderTarget.TYPESET_ONLY
        )
        
        assert typeset_plan.estimated_duration_seconds < full_plan.estimated_duration_seconds


class TestPlanOptimization:
    """测试计划优化"""

    def setup_method(self):
        self.planner = RenderPlanner()

    def test_optimize_sorts_by_priority(self):
        """测试优化按优先级排序"""
        storyboard = {"panels": [{"panel_id": f"panel_{i}"} for i in range(3)]}
        
        # 创建不同优先级的任务
        plan1 = self.planner.create_selective_plan(
            storyboard, "sb_001",
            panel_ids=["panel_0"],
            priority=RenderPriority.LOW
        )
        
        plan2 = self.planner.create_selective_plan(
            storyboard, "sb_001",
            panel_ids=["panel_1"],
            priority=RenderPriority.URGENT
        )
        
        # 合并后优化
        combined = ExecutionPlan(
            id="combined",
            storyboard_id="sb_001",
            jobs=plan1.jobs + plan2.jobs,
            total_jobs=2
        )
        optimized = self.planner.optimize_plan(combined)
        
        # URGENT应在前面
        assert optimized.jobs[0].priority == RenderPriority.URGENT


class TestParallelBatches:
    """测试并行批次"""

    def setup_method(self):
        self.planner = RenderPlanner()

    def test_get_parallel_batches(self):
        """测试获取并行批次"""
        storyboard = {"panels": [{"panel_id": f"panel_{i}"} for i in range(6)]}
        plan = self.planner.create_full_render_plan(storyboard, "sb_001")
        
        batches = self.planner.get_parallel_batches(plan, max_concurrent=2)
        
        # 6个任务，每批2个，应该有3批
        assert len(batches) == 3
        assert all(len(b) <= 2 for b in batches)


class TestPlanSummary:
    """测试计划摘要"""

    def setup_method(self):
        self.planner = RenderPlanner()

    def test_get_plan_summary(self):
        """测试获取计划摘要"""
        storyboard = {"panels": [{"panel_id": f"panel_{i}"} for i in range(3)]}
        plan = self.planner.create_full_render_plan(storyboard, "sb_001")
        
        summary = self.planner.get_plan_summary(plan)
        
        assert "id" in summary
        assert "total_jobs" in summary
        assert summary["total_jobs"] == 3
        assert "by_render_target" in summary
        assert "estimated_duration_human" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
