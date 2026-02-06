"""
VersionManager 单元测试
"""
import pytest
import sys
import os

# Add the app directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.graph.version_manager import (
    VersionManager,
    Snapshot,
    SnapshotType,
    PatchRecord,
    DiffResult,
)


class TestSnapshotCreation:
    """测试快照创建"""

    def setup_method(self):
        self.vm = VersionManager()
        self.test_storyboard_id = "test_sb_001"
        self.test_data = {
            "title": "测试故事",
            "panels": [
                {"panel_number": 1, "description": "第一格"},
                {"panel_number": 2, "description": "第二格"},
            ]
        }

    def test_create_snapshot(self):
        """测试创建快照"""
        snapshot = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data=self.test_data,
            reason="初始版本",
        )
        
        assert snapshot.id is not None
        assert snapshot.storyboard_id == self.test_storyboard_id
        assert snapshot.data == self.test_data
        assert snapshot.reason == "初始版本"

    def test_duplicate_snapshot_returns_existing(self):
        """测试相同内容的快照返回现有快照"""
        snapshot1 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data=self.test_data,
            reason="版本1",
        )
        
        snapshot2 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data=self.test_data,
            reason="版本2",
        )
        
        # 相同内容应返回相同快照
        assert snapshot1.id == snapshot2.id

    def test_different_data_creates_new_snapshot(self):
        """测试不同内容创建新快照"""
        snapshot1 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data=self.test_data,
            reason="版本1",
        )
        
        modified_data = self.test_data.copy()
        modified_data["title"] = "修改后的标题"
        
        snapshot2 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data=modified_data,
            reason="版本2",
        )
        
        assert snapshot1.id != snapshot2.id


class TestSnapshotRetrieval:
    """测试快照获取"""

    def setup_method(self):
        self.vm = VersionManager()
        self.test_storyboard_id = "test_sb_002"

    def test_get_snapshot_by_id(self):
        """测试按ID获取快照"""
        data = {"title": "测试"}
        snapshot = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data=data,
            reason="test",
        )
        
        retrieved = self.vm.get_snapshot(snapshot.id)
        
        assert retrieved is not None
        assert retrieved.id == snapshot.id
        assert retrieved.data == data

    def test_get_nonexistent_snapshot_returns_none(self):
        """测试获取不存在的快照返回None"""
        result = self.vm.get_snapshot("nonexistent_id")
        assert result is None

    def test_get_latest_snapshot(self):
        """测试获取最新快照"""
        # 创建多个快照
        for i in range(3):
            self.vm.create_snapshot(
                storyboard_id=self.test_storyboard_id,
                data={"version": i},
                reason=f"版本{i}",
            )
        
        latest = self.vm.get_latest_snapshot(self.test_storyboard_id)
        
        assert latest is not None
        assert latest.data["version"] == 2

    def test_list_snapshots(self):
        """测试列出快照"""
        for i in range(5):
            self.vm.create_snapshot(
                storyboard_id=self.test_storyboard_id,
                data={"version": i},
                reason=f"版本{i}",
            )
        
        snapshots = self.vm.list_snapshots(self.test_storyboard_id)
        
        assert len(snapshots) == 5


class TestRollback:
    """测试回滚"""

    def setup_method(self):
        self.vm = VersionManager()
        self.test_storyboard_id = "test_sb_003"

    def test_rollback_to_previous_version(self):
        """测试回滚到之前版本"""
        # 创建初始版本
        v1 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data={"title": "版本1"},
            reason="初始",
        )
        
        # 创建第二个版本
        self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data={"title": "版本2"},
            reason="更新",
        )
        
        # 回滚到版本1
        rolled_back = self.vm.rollback_to(self.test_storyboard_id, v1.id)
        
        assert rolled_back is not None
        assert rolled_back["title"] == "版本1"

    def test_rollback_nonexistent_snapshot_returns_none(self):
        """测试回滚到不存在的快照返回None"""
        result = self.vm.rollback_to(self.test_storyboard_id, "nonexistent")
        assert result is None


class TestPatchRecording:
    """测试Patch记录"""

    def setup_method(self):
        self.vm = VersionManager()
        self.test_storyboard_id = "test_sb_004"

    def test_record_patch(self):
        """测试记录Patch"""
        patches = [
            {"op": "replace", "path": "/title", "value": "新标题"},
        ]
        
        record = self.vm.record_patch(
            storyboard_id=self.test_storyboard_id,
            patches=patches,
            summary="修改标题",
        )
        
        assert record.id is not None
        assert record.storyboard_id == self.test_storyboard_id
        assert record.patches == patches
        assert record.summary == "修改标题"

    def test_get_patch_history(self):
        """测试获取Patch历史"""
        for i in range(3):
            self.vm.record_patch(
                storyboard_id=self.test_storyboard_id,
                patches=[{"op": "add", "path": f"/field{i}", "value": i}],
                summary=f"修改{i}",
            )
        
        history = self.vm.get_patch_history(self.test_storyboard_id)
        
        assert len(history) == 3


class TestDiffComputation:
    """测试差异计算"""

    def setup_method(self):
        self.vm = VersionManager()
        self.test_storyboard_id = "test_sb_005"

    def test_compute_diff_changed_field(self):
        """测试计算字段变更差异"""
        snap1 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data={"title": "原标题"},
            reason="v1",
        )
        
        snap2 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data={"title": "新标题"},
            reason="v2",
        )
        
        diff = self.vm.get_diff(snap1.id, snap2.id)
        
        assert diff is not None
        assert len(diff.differences) == 1
        assert diff.differences[0].path == "/title"
        assert diff.differences[0].type == "changed"

    def test_compute_diff_added_field(self):
        """测试计算新增字段差异"""
        snap1 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data={"title": "标题"},
            reason="v1",
        )
        
        snap2 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data={"title": "标题", "description": "新描述"},
            reason="v2",
        )
        
        diff = self.vm.get_diff(snap1.id, snap2.id)
        
        assert diff is not None
        assert len(diff.differences) == 1
        assert diff.differences[0].type == "added"

    def test_compute_diff_removed_field(self):
        """测试计算删除字段差异"""
        snap1 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data={"title": "标题", "description": "描述"},
            reason="v1",
        )
        
        snap2 = self.vm.create_snapshot(
            storyboard_id=self.test_storyboard_id,
            data={"title": "标题"},
            reason="v2",
        )
        
        diff = self.vm.get_diff(snap1.id, snap2.id)
        
        assert diff is not None
        assert len(diff.differences) == 1
        assert diff.differences[0].type == "removed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
