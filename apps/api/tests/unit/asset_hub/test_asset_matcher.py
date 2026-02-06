"""
AssetMatcher 单元测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.asset_hub.asset_matcher import (
    AssetMatcher,
    AssetType,
    MatchRequest,
    MatchResult,
    MatchConfidence,
)


class TestAssetRegistration:
    """测试资产注册"""

    def setup_method(self):
        self.matcher = AssetMatcher()

    def test_register_character(self):
        """测试注册角色"""
        self.matcher.register_asset(
            asset_id="char_001",
            name="小明",
            asset_type=AssetType.CHARACTER,
            tags=["主角", "男性"],
        )
        
        assets = self.matcher.get_registered_assets(AssetType.CHARACTER)
        assert len(assets) == 1
        assert assets[0]["name"] == "小明"

    def test_register_scene(self):
        """测试注册场景"""
        self.matcher.register_asset(
            asset_id="scene_001",
            name="教室",
            asset_type=AssetType.SCENE,
        )
        
        assets = self.matcher.get_registered_assets(AssetType.SCENE)
        assert len(assets) == 1


class TestExactMatching:
    """测试精确匹配"""

    def setup_method(self):
        self.matcher = AssetMatcher()
        self.matcher.register_asset("char_001", "小明", AssetType.CHARACTER)
        self.matcher.register_asset("char_002", "小红", AssetType.CHARACTER)
        self.matcher.register_asset("scene_001", "教室", AssetType.SCENE)

    def test_exact_name_match(self):
        """测试精确名称匹配"""
        request = MatchRequest(query="小明", asset_type=AssetType.CHARACTER)
        result = self.matcher.match(request)
        
        assert result.best_match is not None
        assert result.best_match.asset_id == "char_001"
        assert result.best_match.score == 1.0
        assert result.best_match.confidence == MatchConfidence.HIGH

    def test_case_insensitive_match(self):
        """测试大小写不敏感匹配"""
        self.matcher.register_asset("char_003", "John", AssetType.CHARACTER)
        
        request = MatchRequest(query="john", asset_type=AssetType.CHARACTER)
        result = self.matcher.match(request)
        
        assert result.best_match is not None
        assert result.best_match.score == 1.0


class TestFuzzyMatching:
    """测试模糊匹配"""

    def setup_method(self):
        self.matcher = AssetMatcher()
        self.matcher.register_asset("char_001", "小明同学", AssetType.CHARACTER)
        self.matcher.register_asset("scene_001", "高中教室", AssetType.SCENE)

    def test_contains_match(self):
        """测试包含关系匹配"""
        request = MatchRequest(query="小明", asset_type=AssetType.CHARACTER)
        result = self.matcher.match(request)
        
        assert result.best_match is not None
        assert result.best_match.score > 0.7

    def test_similar_name_match(self):
        """测试相似名称匹配"""
        request = MatchRequest(query="教室", asset_type=AssetType.SCENE)
        result = self.matcher.match(request)
        
        assert result.best_match is not None
        assert result.best_match.score > 0.5


class TestAliasMatching:
    """测试别名匹配"""

    def setup_method(self):
        self.matcher = AssetMatcher()
        self.matcher.register_asset(
            asset_id="char_001",
            name="张明",
            asset_type=AssetType.CHARACTER,
            aliases=["小明", "明明", "阿明"],
        )

    def test_alias_exact_match(self):
        """测试别名精确匹配"""
        request = MatchRequest(query="小明", asset_type=AssetType.CHARACTER)
        result = self.matcher.match(request)
        
        assert result.best_match is not None
        assert result.best_match.asset_id == "char_001"
        assert result.best_match.score >= 0.9


class TestTagMatching:
    """测试标签匹配"""

    def setup_method(self):
        self.matcher = AssetMatcher()
        self.matcher.register_asset(
            asset_id="char_001",
            name="神秘人",
            asset_type=AssetType.CHARACTER,
            tags=["反派", "神秘", "黑衣人"],
        )

    def test_tag_match(self):
        """测试标签匹配"""
        request = MatchRequest(query="黑衣人", asset_type=AssetType.CHARACTER)
        result = self.matcher.match(request)
        
        assert result.best_match is not None
        assert "标签" in result.best_match.match_reason


class TestNoMatch:
    """测试无匹配情况"""

    def setup_method(self):
        self.matcher = AssetMatcher()
        self.matcher.register_asset("char_001", "小明", AssetType.CHARACTER)

    def test_no_match_returns_empty_candidates(self):
        """测试无匹配时返回空候选"""
        request = MatchRequest(query="完全不存在的角色", asset_type=AssetType.CHARACTER)
        result = self.matcher.match(request)
        
        assert result.best_match is None or result.best_match.score < 0.4
        assert result.needs_generation is True

    def test_wrong_type_no_match(self):
        """测试类型不匹配"""
        request = MatchRequest(query="小明", asset_type=AssetType.SCENE)
        result = self.matcher.match(request)
        
        assert result.best_match is None


class TestBatchMatching:
    """测试批量匹配"""

    def setup_method(self):
        self.matcher = AssetMatcher()
        self.matcher.register_asset("char_001", "小明", AssetType.CHARACTER)
        self.matcher.register_asset("char_002", "小红", AssetType.CHARACTER)
        self.matcher.register_asset("scene_001", "教室", AssetType.SCENE)

    def test_batch_match(self):
        """测试批量匹配"""
        queries = [
            {"query": "小明", "type": "character"},
            {"query": "小红", "type": "character"},
            {"query": "教室", "type": "scene"},
        ]
        
        results = self.matcher.batch_match(queries)
        
        assert len(results) == 3
        assert results["小明"].best_match is not None
        assert results["小红"].best_match is not None


class TestStoryboardExtraction:
    """测试分镜资产提取"""

    def setup_method(self):
        self.matcher = AssetMatcher()
        self.matcher.register_asset("char_001", "小明", AssetType.CHARACTER)
        self.matcher.register_asset("scene_001", "教室", AssetType.SCENE)

    def test_extract_and_match(self):
        """测试从分镜提取并匹配"""
        storyboard = {
            "characters": [{"name": "小明"}, {"name": "未知角色"}],
            "scenes": [{"name": "教室"}],
            "panels": [
                {"characters": ["小明"], "scene": "教室"},
            ]
        }
        
        result = self.matcher.extract_and_match(storyboard)
        
        assert "summary" in result
        assert result["summary"]["total"] >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
