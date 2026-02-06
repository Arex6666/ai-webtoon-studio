"""
GraphStore 单元测试
"""
import pytest
import sys
import os

# Add the app directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.graph.graph_store import GraphStore, ApplyResult


class TestStateManagement:
    """测试状态管理"""

    def setup_method(self):
        self.store = GraphStore()
        self.test_id = "test_sb_001"
        self.test_data = {
            "title": "测试故事",
            "panels": [
                {"panel_number": 1, "description": "第一格"},
            ]
        }

    def test_save_and_get_state(self):
        """测试保存和获取状态"""
        self.store.save_state(self.test_id, self.test_data, "初始版本")
        
        state = self.store.get_current_state(self.test_id)
        
        assert state is not None
        assert state["title"] == "测试故事"

    def test_get_nonexistent_state_returns_none(self):
        """测试获取不存在的状态返回None"""
        state = self.store.get_current_state("nonexistent")
        assert state is None

    def test_state_is_deep_copy(self):
        """测试返回的状态是深拷贝"""
        self.store.save_state(self.test_id, self.test_data, "test")
        
        state1 = self.store.get_current_state(self.test_id)
        state1["title"] = "修改后"
        
        state2 = self.store.get_current_state(self.test_id)
        
        # 修改state1不应影响存储
        assert state2["title"] == "测试故事"


class TestPatchApplication:
    """测试Patch应用"""

    def setup_method(self):
        self.store = GraphStore()
        self.test_id = "test_sb_002"
        self.test_data = {
            "title": "原标题",
            "panels": [
                {"panel_number": 1, "description": "原描述"},
            ]
        }
        self.store.save_state(self.test_id, self.test_data, "初始")

    def test_apply_patches_success(self):
        """测试成功应用Patch"""
        patches = [
            {"op": "replace", "path": "/title", "value": "新标题"},
        ]
        
        result = self.store.apply_patches(self.test_id, patches, "修改标题")
        
        assert result.success is True
        assert result.new_state["title"] == "新标题"
        assert result.patch_record_id is not None

    def test_apply_patches_creates_snapshots(self):
        """测试应用Patch创建快照"""
        patches = [
            {"op": "replace", "path": "/title", "value": "新标题"},
        ]
        
        result = self.store.apply_patches(self.test_id, patches)
        
        assert result.before_snapshot_id is not None
        assert result.after_snapshot_id is not None

    def test_apply_patches_generates_render_plan(self):
        """测试应用Patch生成渲染计划"""
        patches = [
            {"op": "replace", "path": "/panels/0/description", "value": "新描述"},
        ]
        
        result = self.store.apply_patches(self.test_id, patches)
        
        assert result.render_plan is not None

    def test_apply_patches_nonexistent_storyboard_fails(self):
        """测试对不存在的分镜应用Patch失败"""
        patches = [{"op": "add", "path": "/test", "value": 1}]
        
        result = self.store.apply_patches("nonexistent", patches)
        
        assert result.success is False
        assert "not found" in result.error.lower()


class TestRollback:
    """测试回滚"""

    def setup_method(self):
        self.store = GraphStore()
        self.test_id = "test_sb_003"

    def test_rollback_success(self):
        """测试成功回滚"""
        # 保存初始版本
        snapshot1 = self.store.save_state(
            self.test_id, {"version": 1}, "v1"
        )
        
        # 保存第二版本
        self.store.save_state(
            self.test_id, {"version": 2}, "v2"
        )
        
        # 回滚到v1
        result = self.store.rollback(self.test_id, snapshot1.id)
        
        assert result.success is True
        assert result.new_state["version"] == 1

    def test_rollback_nonexistent_snapshot_fails(self):
        """测试回滚到不存在的快照失败"""
        result = self.store.rollback(self.test_id, "nonexistent")
        
        assert result.success is False


class TestHistoryRetrieval:
    """测试历史获取"""

    def setup_method(self):
        self.store = GraphStore()
        self.test_id = "test_sb_004"

    def test_get_snapshot_list(self):
        """测试获取快照列表"""
        for i in range(3):
            self.store.save_state(
                self.test_id, {"version": i}, f"v{i}"
            )
        
        snapshots = self.store.get_snapshot_list(self.test_id)
        
        assert len(snapshots) == 3

    def test_get_patch_history(self):
        """测试获取Patch历史"""
        self.store.save_state(self.test_id, {"title": "初始"}, "init")
        
        for i in range(2):
            self.store.apply_patches(
                self.test_id,
                [{"op": "replace", "path": "/title", "value": f"版本{i}"}],
                f"更新{i}"
            )
        
        history = self.store.get_patch_history(self.test_id)
        
        assert len(history) == 2


class TestImpactAnalysis:
    """测试影响分析"""

    def setup_method(self):
        self.store = GraphStore()
        self.test_id = "test_sb_005"
        self.test_data = {
            "panels": [{"panel_number": 1}]
        }
        self.store.save_state(self.test_id, self.test_data, "init")

    def test_analyze_impact(self):
        """测试影响分析"""
        patches = [
            {"op": "replace", "path": "/panels/0/camera", "value": "top_down"}
        ]
        
        analysis = self.store.analyze_impact(self.test_id, patches)
        
        assert "total_patches" in analysis
        assert "render_plan" in analysis


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
