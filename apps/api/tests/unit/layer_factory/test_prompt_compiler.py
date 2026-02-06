"""
PromptCompiler 单元测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.layer_factory.prompt_compiler import (
    PromptCompiler,
    PromptStyle,
    PromptPriority,
    CompiledPrompt,
)


class TestBasicCompilation:
    """测试基础编译"""

    def setup_method(self):
        self.compiler = PromptCompiler()

    def test_compile_simple_panel(self):
        """测试编译简单分镜"""
        panel_data = {
            "description": "主角站在教室门口",
            "camera": {"shot_type": "medium"},
        }
        
        result = self.compiler.compile(panel_data)
        
        assert isinstance(result, CompiledPrompt)
        assert result.positive != ""
        assert result.negative != ""

    def test_compile_with_characters(self):
        """测试包含角色的编译"""
        panel_data = {
            "description": "两人对话",
            "characters": ["小明", "小红"],
        }
        characters = [
            {"name": "小明", "appearance": "黑发少年"},
            {"name": "小红", "appearance": "红衣少女", "gender": "female"},
        ]
        
        result = self.compiler.compile(panel_data, characters=characters)
        
        assert "黑发少年" in result.positive or "红衣少女" in result.positive

    def test_compile_with_scene(self):
        """测试包含场景的编译"""
        panel_data = {
            "scene": "教室",
            "description": "上课中",
        }
        scene = {"name": "教室", "description": "宽敞明亮的高中教室"}
        
        result = self.compiler.compile(panel_data, scene=scene)
        
        assert "教室" in result.positive or "高中" in result.positive


class TestStylePresets:
    """测试风格预设"""

    def setup_method(self):
        self.compiler = PromptCompiler()
        self.panel_data = {"description": "测试场景"}

    def test_korean_webtoon_style(self):
        """测试韩漫风格"""
        result = self.compiler.compile(
            self.panel_data,
            style=PromptStyle.KOREAN_WEBTOON
        )
        
        assert "webtoon" in result.positive.lower() or "manhwa" in result.positive.lower()

    def test_japanese_manga_style(self):
        """测试日漫风格"""
        result = self.compiler.compile(
            self.panel_data,
            style=PromptStyle.JAPANESE_MANGA
        )
        
        assert "manga" in result.positive.lower()

    def test_anime_style(self):
        """测试动画风格"""
        result = self.compiler.compile(
            self.panel_data,
            style=PromptStyle.ANIME
        )
        
        assert "anime" in result.positive.lower()


class TestCameraTokens:
    """测试镜头令牌"""

    def setup_method(self):
        self.compiler = PromptCompiler()

    def test_close_up_shot(self):
        """测试特写镜头"""
        panel_data = {
            "description": "角色表情",
            "camera": {"shot_type": "close_up"},
        }
        
        result = self.compiler.compile(panel_data)
        
        assert "close-up" in result.positive.lower() or "portrait" in result.positive.lower()

    def test_wide_shot(self):
        """测试远景镜头"""
        panel_data = {
            "description": "全景",
            "camera": {"shot_type": "wide"},
        }
        
        result = self.compiler.compile(panel_data)
        
        assert "wide" in result.positive.lower()

    def test_high_angle(self):
        """测试高角度"""
        panel_data = {
            "description": "俯视",
            "camera": {"shot_type": "medium", "angle": "high_angle"},
        }
        
        result = self.compiler.compile(panel_data)
        
        assert "high angle" in result.positive.lower() or "bird" in result.positive.lower()


class TestSceneTokens:
    """测试场景令牌"""

    def setup_method(self):
        self.compiler = PromptCompiler()

    def test_time_of_day(self):
        """测试时间设置"""
        panel_data = {
            "description": "夜晚场景",
            "time_of_day": "night",
        }
        
        result = self.compiler.compile(panel_data)
        
        assert "night" in result.positive.lower()

    def test_weather(self):
        """测试天气设置"""
        panel_data = {
            "description": "雨天",
            "weather": "rain",
        }
        
        result = self.compiler.compile(panel_data)
        
        assert "rain" in result.positive.lower()


class TestNegativePrompt:
    """测试负向提示词"""

    def setup_method(self):
        self.compiler = PromptCompiler()

    def test_negative_contains_quality_terms(self):
        """测试负向包含质量词"""
        panel_data = {"description": "测试"}
        
        result = self.compiler.compile(panel_data)
        
        assert "low quality" in result.negative.lower() or "blurry" in result.negative.lower()

    def test_negative_contains_anatomy_terms(self):
        """测试负向包含解剖学词"""
        panel_data = {"description": "测试"}
        
        result = self.compiler.compile(panel_data)
        
        assert "bad anatomy" in result.negative.lower() or "bad hands" in result.negative.lower()


class TestBatchCompilation:
    """测试批量编译"""

    def setup_method(self):
        self.compiler = PromptCompiler()

    def test_compile_batch(self):
        """测试批量编译"""
        panels = [
            {"description": "场景1"},
            {"description": "场景2"},
            {"description": "场景3"},
        ]
        
        results = self.compiler.compile_batch(panels)
        
        assert len(results) == 3
        assert all(isinstance(r, CompiledPrompt) for r in results)

    def test_batch_with_storyboard_data(self):
        """测试使用分镜数据的批量编译"""
        panels = [
            {"description": "对话", "characters": ["小明"]},
        ]
        storyboard = {
            "characters": [{"name": "小明", "appearance": "黑发少年"}],
            "style": "korean_webtoon",
        }
        
        results = self.compiler.compile_batch(panels, storyboard)
        
        assert len(results) == 1
        assert "黑发少年" in results[0].positive


class TestTokenPriority:
    """测试令牌优先级"""

    def setup_method(self):
        self.compiler = PromptCompiler()

    def test_action_has_high_priority(self):
        """测试动作描述有高优先级"""
        panel_data = {
            "description": "激烈的战斗场景",
            "weather": "rain",  # 低优先级
        }
        
        result = self.compiler.compile(panel_data)
        
        # 动作描述应该在提示词前面
        action_pos = result.positive.find("战斗")
        rain_pos = result.positive.find("rain")
        
        if action_pos >= 0 and rain_pos >= 0:
            assert action_pos < rain_pos


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
