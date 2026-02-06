"""
AssetGenerator 单元测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.asset_hub.asset_generator import (
    AssetGenerator,
    AssetDraft,
    GenerationStatus,
    GenerationRequest,
)


class TestDraftManagement:
    """测试草稿管理"""

    def setup_method(self):
        self.generator = AssetGenerator()

    def test_get_nonexistent_draft(self):
        """测试获取不存在的草稿"""
        draft = self.generator.get_draft("nonexistent")
        assert draft is None

    def test_list_drafts_empty(self):
        """测试列出空草稿列表"""
        drafts = self.generator.list_drafts()
        assert drafts == []


class TestDraftConfirmation:
    """测试草稿确认"""

    def setup_method(self):
        self.generator = AssetGenerator()
        # 手动创建草稿用于测试
        self.generator._drafts["test_001"] = AssetDraft(
            id="test_001",
            name="测试角色",
            asset_type="character",
            description="测试描述",
            visual_prompt="测试提示词",
            status=GenerationStatus.READY,
        )

    def test_confirm_draft(self):
        """测试确认草稿"""
        draft = self.generator.confirm_draft("test_001")
        
        assert draft is not None
        assert draft.status == GenerationStatus.CONFIRMED

    def test_confirm_nonexistent_returns_none(self):
        """测试确认不存在的草稿返回None"""
        result = self.generator.confirm_draft("nonexistent")
        assert result is None


class TestDraftRejection:
    """测试草稿拒绝"""

    def setup_method(self):
        self.generator = AssetGenerator()
        self.generator._drafts["test_001"] = AssetDraft(
            id="test_001",
            name="测试角色",
            asset_type="character",
            status=GenerationStatus.READY,
        )

    def test_reject_draft(self):
        """测试拒绝草稿"""
        draft = self.generator.reject_draft("test_001")
        
        assert draft is not None
        assert draft.status == GenerationStatus.REJECTED


class TestDraftUpdate:
    """测试草稿更新"""

    def setup_method(self):
        self.generator = AssetGenerator()
        self.generator._drafts["test_001"] = AssetDraft(
            id="test_001",
            name="原名称",
            asset_type="character",
            description="原描述",
            status=GenerationStatus.READY,
        )

    def test_update_draft(self):
        """测试更新草稿"""
        draft = self.generator.update_draft(
            "test_001",
            {"name": "新名称", "description": "新描述"}
        )
        
        assert draft is not None
        assert draft.name == "新名称"
        assert draft.description == "新描述"

    def test_cannot_update_confirmed_draft(self):
        """测试无法更新已确认草稿"""
        self.generator.confirm_draft("test_001")
        
        draft = self.generator.update_draft(
            "test_001",
            {"name": "试图修改"}
        )
        
        assert draft is None


class TestVisualPrompt:
    """测试视觉提示词"""

    def setup_method(self):
        self.generator = AssetGenerator()
        self.generator._drafts["test_001"] = AssetDraft(
            id="test_001",
            name="测试角色",
            asset_type="character",
            visual_prompt="黑发少年，穿着校服",
            status=GenerationStatus.READY,
        )

    def test_get_visual_prompt(self):
        """测试获取视觉提示词"""
        prompt = self.generator.get_visual_prompt("test_001")
        
        assert prompt is not None
        assert "黑发少年" in prompt


class TestDraftFiltering:
    """测试草稿过滤"""

    def setup_method(self):
        self.generator = AssetGenerator()
        # 创建不同类型和状态的草稿
        self.generator._drafts["char_001"] = AssetDraft(
            id="char_001", name="角色1", asset_type="character",
            status=GenerationStatus.READY
        )
        self.generator._drafts["char_002"] = AssetDraft(
            id="char_002", name="角色2", asset_type="character",
            status=GenerationStatus.CONFIRMED
        )
        self.generator._drafts["scene_001"] = AssetDraft(
            id="scene_001", name="场景1", asset_type="scene",
            status=GenerationStatus.READY
        )

    def test_filter_by_type(self):
        """测试按类型过滤"""
        drafts = self.generator.list_drafts(asset_type="character")
        assert len(drafts) == 2

    def test_filter_by_status(self):
        """测试按状态过滤"""
        drafts = self.generator.list_drafts(status=GenerationStatus.READY)
        assert len(drafts) == 2


class TestDraftClearing:
    """测试草稿清理"""

    def setup_method(self):
        self.generator = AssetGenerator()
        for i in range(3):
            self.generator._drafts[f"draft_{i}"] = AssetDraft(
                id=f"draft_{i}", name=f"草稿{i}", asset_type="character",
                status=GenerationStatus.REJECTED if i == 0 else GenerationStatus.READY
            )

    def test_clear_by_status(self):
        """测试按状态清理"""
        count = self.generator.clear_drafts(GenerationStatus.REJECTED)
        
        assert count == 1
        assert len(self.generator.list_drafts()) == 2

    def test_clear_all(self):
        """测试清理所有"""
        count = self.generator.clear_drafts()
        
        assert count == 3
        assert len(self.generator.list_drafts()) == 0


class TestGenerationRequest:
    """测试生成请求模型"""

    def test_create_request(self):
        """测试创建生成请求"""
        request = GenerationRequest(
            name="小明",
            asset_type="character",
            context="一个四格漫画的主角",
            style_hint="日漫风格"
        )
        
        assert request.name == "小明"
        assert request.asset_type == "character"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
