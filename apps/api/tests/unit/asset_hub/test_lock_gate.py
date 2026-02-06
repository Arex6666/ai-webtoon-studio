"""
AssetLockGate 单元测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.asset_hub.lock_gate import (
    AssetLockGate,
    LockStatus,
    BindingType,
    AssetBinding,
)


class TestBindingCreation:
    """测试绑定创建"""

    def setup_method(self):
        self.gate = AssetLockGate()

    def test_create_binding_pending(self):
        """测试创建待确认绑定"""
        binding = self.gate.create_binding(
            storyboard_id="sb_001",
            reference_name="小明",
            binding_type=BindingType.CHARACTER,
            asset_id="char_001",
            asset_name="小明",
            confidence=0.8,
        )
        
        assert binding.status == LockStatus.PENDING
        assert binding.asset_id == "char_001"

    def test_create_binding_auto_confirm(self):
        """测试高置信度自动确认"""
        binding = self.gate.create_binding(
            storyboard_id="sb_001",
            reference_name="小明",
            binding_type=BindingType.CHARACTER,
            asset_id="char_001",
            asset_name="小明",
            confidence=0.98,
        )
        
        assert binding.status == LockStatus.CONFIRMED


class TestBindingConfirmation:
    """测试绑定确认"""

    def setup_method(self):
        self.gate = AssetLockGate()
        self.binding = self.gate.create_binding(
            storyboard_id="sb_001",
            reference_name="小明",
            binding_type=BindingType.CHARACTER,
            asset_id="char_001",
            asset_name="小明",
            confidence=0.7,
        )

    def test_confirm_binding(self):
        """测试确认绑定"""
        result = self.gate.confirm_binding(self.binding.id, "user_001")
        
        assert result.success is True
        assert result.new_status == LockStatus.CONFIRMED
        
        binding = self.gate.get_binding(self.binding.id)
        assert binding.confirmed_by == "user_001"

    def test_confirm_nonexistent_fails(self):
        """测试确认不存在的绑定失败"""
        result = self.gate.confirm_binding("nonexistent")
        assert result.success is False


class TestBindingRejection:
    """测试绑定拒绝"""

    def setup_method(self):
        self.gate = AssetLockGate()
        self.binding = self.gate.create_binding(
            storyboard_id="sb_001",
            reference_name="小明",
            binding_type=BindingType.CHARACTER,
            asset_id="char_001",
            asset_name="小明",
            confidence=0.7,
        )

    def test_reject_binding(self):
        """测试拒绝绑定"""
        result = self.gate.reject_binding(self.binding.id, "匹配错误")
        
        assert result.success is True
        assert result.new_status == LockStatus.REJECTED
        
        binding = self.gate.get_binding(self.binding.id)
        assert binding.asset_id is None


class TestBindingChange:
    """测试更换绑定"""

    def setup_method(self):
        self.gate = AssetLockGate()
        self.binding = self.gate.create_binding(
            storyboard_id="sb_001",
            reference_name="小明",
            binding_type=BindingType.CHARACTER,
            asset_id="char_001",
            asset_name="小明",
            confidence=0.7,
        )

    def test_change_binding(self):
        """测试更换绑定资产"""
        result = self.gate.change_binding(
            self.binding.id,
            new_asset_id="char_002",
            new_asset_name="小明2号"
        )
        
        assert result.success is True
        
        binding = self.gate.get_binding(self.binding.id)
        assert binding.asset_id == "char_002"
        assert binding.asset_name == "小明2号"
        assert binding.confidence == 1.0


class TestLocking:
    """测试锁定功能"""

    def setup_method(self):
        self.gate = AssetLockGate()
        self.binding = self.gate.create_binding(
            storyboard_id="sb_001",
            reference_name="小明",
            binding_type=BindingType.CHARACTER,
            asset_id="char_001",
            asset_name="小明",
            confidence=0.98,  # 自动确认
        )

    def test_lock_confirmed_binding(self):
        """测试锁定已确认绑定"""
        result = self.gate.lock_binding(self.binding.id)
        
        assert result.success is True
        assert result.new_status == LockStatus.LOCKED

    def test_cannot_modify_locked_binding(self):
        """测试无法修改锁定的绑定"""
        self.gate.lock_binding(self.binding.id)
        
        result = self.gate.change_binding(
            self.binding.id,
            new_asset_id="char_002",
            new_asset_name="新资产"
        )
        
        assert result.success is False
        assert "锁定" in result.message

    def test_unlock_binding(self):
        """测试解锁绑定"""
        self.gate.lock_binding(self.binding.id)
        result = self.gate.unlock_binding(self.binding.id)
        
        assert result.success is True
        assert result.new_status == LockStatus.CONFIRMED


class TestStoryboardBindings:
    """测试分镜绑定管理"""

    def setup_method(self):
        self.gate = AssetLockGate()
        self.storyboard_id = "sb_001"
        
        # 创建多个绑定
        self.gate.create_binding(
            self.storyboard_id, "小明", BindingType.CHARACTER,
            asset_id="char_001", asset_name="小明", confidence=0.98
        )
        self.gate.create_binding(
            self.storyboard_id, "小红", BindingType.CHARACTER,
            asset_id="char_002", asset_name="小红", confidence=0.7
        )
        self.gate.create_binding(
            self.storyboard_id, "教室", BindingType.SCENE,
            confidence=0.5
        )

    def test_get_all_bindings(self):
        """测试获取所有绑定"""
        bindings = self.gate.get_storyboard_bindings(self.storyboard_id)
        assert len(bindings) == 3

    def test_get_pending_bindings(self):
        """测试获取待确认绑定"""
        pending = self.gate.get_pending_bindings(self.storyboard_id)
        assert len(pending) == 2

    def test_binding_summary(self):
        """测试绑定状态汇总"""
        summary = self.gate.get_binding_summary(self.storyboard_id)
        
        assert summary["total"] == 3
        assert summary["confirmed"] == 1
        assert summary["pending"] == 2


class TestBatchOperations:
    """测试批量操作"""

    def setup_method(self):
        self.gate = AssetLockGate()
        self.storyboard_id = "sb_001"
        
        self.bindings = []
        for i in range(3):
            b = self.gate.create_binding(
                self.storyboard_id, f"角色{i}", BindingType.CHARACTER,
                asset_id=f"char_{i}", asset_name=f"角色{i}", confidence=0.7
            )
            self.bindings.append(b)

    def test_batch_confirm(self):
        """测试批量确认"""
        binding_ids = [b.id for b in self.bindings]
        results = self.gate.batch_confirm(binding_ids)
        
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_batch_lock(self):
        """测试批量锁定"""
        # 先确认所有
        for b in self.bindings:
            self.gate.confirm_binding(b.id)
        
        results = self.gate.batch_lock(self.storyboard_id)
        
        assert len(results) == 3
        assert all(r.new_status == LockStatus.LOCKED for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
