"""
StudioOrchestrator 单元测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.orchestrator.studio_orchestrator import (
    StudioOrchestrator,
    WorkflowStage,
    SessionState,
    OrchestratorResult,
)


class TestSessionManagement:
    """测试会话管理"""

    def setup_method(self):
        self.orchestrator = StudioOrchestrator(project_id="proj_001")

    def test_create_session(self):
        """测试创建会话"""
        session = self.orchestrator.create_session("session_001")
        
        assert isinstance(session, SessionState)
        assert session.session_id == "session_001"
        assert session.project_id == "proj_001"
        assert session.stage == WorkflowStage.IDEATION

    def test_get_session(self):
        """测试获取会话"""
        self.orchestrator.create_session("session_001")
        
        session = self.orchestrator.get_session("session_001")
        assert session is not None
        
        miss = self.orchestrator.get_session("nonexistent")
        assert miss is None


class TestWorkflowStatus:
    """测试工作流状态"""

    def setup_method(self):
        self.orchestrator = StudioOrchestrator(project_id="proj_001")
        self.orchestrator.create_session("session_001")

    def test_get_workflow_status(self):
        """测试获取工作流状态"""
        status = self.orchestrator.get_workflow_status("session_001")
        
        assert "session_id" in status
        assert "stage" in status
        assert status["stage"] == "ideation"

    def test_workflow_status_nonexistent(self):
        """测试获取不存在的会话状态"""
        status = self.orchestrator.get_workflow_status("nonexistent")
        assert "error" in status


class TestWorkflowStages:
    """测试工作流阶段"""

    def test_all_stages_defined(self):
        """测试所有阶段已定义"""
        stages = list(WorkflowStage)
        assert len(stages) >= 5
        
        stage_names = [s.value for s in stages]
        assert "ideation" in stage_names
        assert "storyboarding" in stage_names
        assert "rendering" in stage_names


class TestOrchestratorResult:
    """测试编排结果"""

    def test_success_result(self):
        """测试成功结果"""
        result = OrchestratorResult(
            success=True,
            stage=WorkflowStage.STORYBOARDING,
            message="操作成功",
            data={"key": "value"},
            next_actions=["action1", "action2"],
        )
        
        assert result.success is True
        assert result.stage == WorkflowStage.STORYBOARDING
        assert len(result.next_actions) == 2

    def test_failure_result(self):
        """测试失败结果"""
        result = OrchestratorResult(
            success=False,
            stage=WorkflowStage.IDEATION,
            message="操作失败",
        )
        
        assert result.success is False
        assert result.data is None


class TestModuleIntegration:
    """测试模块集成"""

    def setup_method(self):
        self.orchestrator = StudioOrchestrator(project_id="proj_001")

    def test_has_director_agent(self):
        """测试包含DirectorAgent"""
        assert self.orchestrator.director is not None

    def test_has_graph_store(self):
        """测试包含GraphStore"""
        assert self.orchestrator.graph_store is not None
        assert self.orchestrator.version_manager is not None
        assert self.orchestrator.dependency_graph is not None

    def test_has_asset_hub(self):
        """测试包含Asset Hub"""
        assert self.orchestrator.asset_matcher is not None
        assert self.orchestrator.lock_gate is not None
        assert self.orchestrator.asset_generator is not None

    def test_has_factory(self):
        """测试包含Factory"""
        assert self.orchestrator.prompt_compiler is not None
        assert self.orchestrator.render_planner is not None


class TestSessionState:
    """测试会话状态模型"""

    def test_default_values(self):
        """测试默认值"""
        state = SessionState(
            session_id="test",
            project_id="proj",
        )
        
        assert state.stage == WorkflowStage.IDEATION
        assert state.storyboard_id is None
        assert state.pending_assets == 0

    def test_with_storyboard(self):
        """测试带分镜的状态"""
        state = SessionState(
            session_id="test",
            project_id="proj",
            storyboard_id="sb_001",
            current_storyboard={"panels": []},
            stage=WorkflowStage.STORYBOARDING,
        )
        
        assert state.storyboard_id == "sb_001"
        assert state.current_storyboard is not None


class TestVersionHistory:
    """测试版本历史"""

    def setup_method(self):
        self.orchestrator = StudioOrchestrator(project_id="proj_001")

    def test_empty_history_without_session(self):
        """测试无会话时返回空历史"""
        history = self.orchestrator.get_version_history("nonexistent")
        assert history == []

    def test_empty_history_without_storyboard(self):
        """测试无分镜时返回空历史"""
        self.orchestrator.create_session("session_001")
        history = self.orchestrator.get_version_history("session_001")
        assert history == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
