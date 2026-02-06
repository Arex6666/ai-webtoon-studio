"""
DependencyGraph 单元测试
"""
import pytest
import sys
import os

# Add the app directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.graph.dependency_graph import (
    DependencyGraph,
    ChangeType,
    RenderTarget,
    InvalidationRule,
    InvalidatedPanel,
    RenderPlan,
)


class TestInvalidationRules:
    """测试失效规则"""

    def setup_method(self):
        self.dg = DependencyGraph()
        self.test_storyboard = {
            "title": "测试故事",
            "style": "日漫风格",
            "characters": [
                {"name": "小明", "appearance": "黑发少年"},
                {"name": "小红", "appearance": "红衣少女"},
            ],
            "scenes": [
                {"name": "教室", "description": "高中教室"},
                {"name": "操场", "description": "学校操场"},
            ],
            "panels": [
                {"panel_number": 1, "scene": "教室", "characters": ["小明"]},
                {"panel_number": 2, "scene": "教室", "characters": ["小明", "小红"]},
                {"panel_number": 3, "scene": "操场", "characters": ["小红"]},
                {"panel_number": 4, "scene": "教室", "characters": ["小明"]},
            ],
        }

    def test_dialogue_change_only_affects_typeset(self):
        """测试对白修改仅影响排版"""
        paths = ["/panels/1/dialogue"]
        
        invalidated = self.dg.get_invalidated_panels(self.test_storyboard, paths)
        
        assert len(invalidated) == 1
        assert invalidated[0].panel_id == "panel_1"
        assert invalidated[0].render_target == RenderTarget.TYPESET_ONLY

    def test_camera_change_requires_full_render(self):
        """测试镜头修改需完整渲染"""
        paths = ["/panels/0/camera"]
        
        invalidated = self.dg.get_invalidated_panels(self.test_storyboard, paths)
        
        assert len(invalidated) == 1
        assert invalidated[0].panel_id == "panel_0"
        assert invalidated[0].render_target == RenderTarget.FULL_RENDER

    def test_description_change_requires_full_render(self):
        """测试描述修改需完整渲染"""
        paths = ["/panels/2/description"]
        
        invalidated = self.dg.get_invalidated_panels(self.test_storyboard, paths)
        
        assert len(invalidated) == 1
        assert invalidated[0].panel_id == "panel_2"
        assert invalidated[0].render_target == RenderTarget.FULL_RENDER

    def test_character_appearance_affects_all_panels_with_character(self):
        """测试角色外观修改影响所有包含该角色的分镜"""
        # 修改小明的外观（索引0）
        paths = ["/characters/0/appearance"]
        
        invalidated = self.dg.get_invalidated_panels(self.test_storyboard, paths)
        
        # 小明出现在panel 0, 1, 3
        panel_ids = [p.panel_id for p in invalidated]
        assert "panel_0" in panel_ids
        assert "panel_1" in panel_ids
        assert "panel_3" in panel_ids
        assert "panel_2" not in panel_ids  # 小明不在panel 2

    def test_scene_change_affects_all_panels_using_scene(self):
        """测试场景修改影响所有使用该场景的分镜"""
        # 修改教室场景（索引0）
        paths = ["/scenes/0"]
        
        invalidated = self.dg.get_invalidated_panels(self.test_storyboard, paths)
        
        # 教室在panel 0, 1, 3
        panel_ids = [p.panel_id for p in invalidated]
        assert "panel_0" in panel_ids
        assert "panel_1" in panel_ids
        assert "panel_3" in panel_ids

    def test_style_change_affects_all_panels(self):
        """测试风格修改影响所有分镜"""
        paths = ["/style"]
        
        invalidated = self.dg.get_invalidated_panels(self.test_storyboard, paths)
        
        # 所有4个分镜都受影响
        assert len(invalidated) == 4


class TestRenderPlan:
    """测试渲染计划"""

    def setup_method(self):
        self.dg = DependencyGraph()
        self.test_storyboard = {
            "panels": [
                {"panel_number": 1, "scene": "教室", "characters": ["小明"]},
                {"panel_number": 2, "scene": "教室", "characters": ["小红"]},
            ],
            "characters": [
                {"name": "小明"},
                {"name": "小红"},
            ],
            "scenes": [
                {"name": "教室"},
            ],
        }

    def test_build_render_plan_categorizes_correctly(self):
        """测试渲染计划正确分类"""
        paths = [
            "/panels/0/dialogue",  # typeset only
            "/panels/1/camera",    # full render
        ]
        
        plan = self.dg.build_render_plan(self.test_storyboard, paths)
        
        assert "panel_0" in plan.typeset_only_panels
        assert "panel_1" in plan.full_render_panels

    def test_full_render_priority_over_typeset(self):
        """测试完整渲染优先于排版"""
        paths = [
            "/panels/0/dialogue",     # typeset only
            "/panels/0/description",  # full render
        ]
        
        plan = self.dg.build_render_plan(self.test_storyboard, paths)
        
        # panel_0应该在full_render中，不在typeset中
        assert "panel_0" in plan.full_render_panels
        assert "panel_0" not in plan.typeset_only_panels

    def test_render_plan_summary(self):
        """测试渲染计划摘要"""
        paths = ["/panels/0/camera", "/panels/1/dialogue"]
        
        plan = self.dg.build_render_plan(self.test_storyboard, paths)
        
        assert "完整渲染" in plan.summary or "重排版" in plan.summary


class TestPatchImpactAnalysis:
    """测试Patch影响分析"""

    def setup_method(self):
        self.dg = DependencyGraph()
        self.test_storyboard = {
            "title": "测试",
            "panels": [
                {"panel_number": 1},
                {"panel_number": 2},
            ]
        }

    def test_analyze_patch_impact(self):
        """测试分析Patch影响"""
        patches = [
            {"op": "replace", "path": "/panels/0/camera", "value": "top_down"},
        ]
        
        analysis = self.dg.analyze_patch_impact(self.test_storyboard, patches)
        
        assert analysis["total_patches"] == 1
        assert analysis["affected_panels"] >= 0
        assert "render_plan" in analysis


class TestCustomRules:
    """测试自定义规则"""

    def test_add_custom_rule(self):
        """测试添加自定义规则"""
        dg = DependencyGraph()
        initial_count = len(dg.get_rules())
        
        custom_rule = InvalidationRule(
            change_type=ChangeType.PROP,
            pattern=r"/panels/(\d+)/props",
            render_target=RenderTarget.COMPOSITE,
            scope="panel",
            description="道具修改需合成层"
        )
        
        dg.add_rule(custom_rule)
        
        assert len(dg.get_rules()) == initial_count + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
