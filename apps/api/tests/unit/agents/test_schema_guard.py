"""
SchemaGuard 单元测试
"""
import pytest
import sys
import os

# Add the app directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.agents.schema_guard import SchemaGuard, SchemaType, ValidationResult


class TestSchemaGuardValidation:
    """测试SchemaGuard的验证功能"""

    def setup_method(self):
        """每个测试方法前初始化"""
        self.guard = SchemaGuard(auto_repair=False)

    # === Panel Schema Tests ===

    def test_validate_valid_panel(self):
        """测试有效的Panel数据通过验证"""
        data = {
            "panel_number": 1,
            "description": "一只橘猫站在厨房里，眼睛盯着桌上的鱼",
            "dialogue": [
                {"speaker": "旁白", "text": "在一个阳光明媚的午后..."}
            ],
            "characters": ["橘猫"],
            "scene": "厨房",
            "camera": {"angle": "eye_level", "shot_type": "medium"},
        }
        
        result = self.guard.validate(data, SchemaType.PANEL)
        
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_panel_missing_required_field(self):
        """测试缺少必需字段的Panel数据被拒绝"""
        data = {
            "panel_number": 1,
            # missing "description"
        }
        
        result = self.guard.validate(data, SchemaType.PANEL)
        
        assert result.is_valid is False
        assert any("description" in err for err in result.errors)

    def test_validate_panel_wrong_type(self):
        """测试字段类型错误被检测"""
        data = {
            "panel_number": "one",  # should be int
            "description": "测试描述",
        }
        
        result = self.guard.validate(data, SchemaType.PANEL)
        
        assert result.is_valid is False
        assert any("panel_number" in err and "wrong type" in err for err in result.errors)

    def test_validate_panel_nested_dialogue_missing_speaker(self):
        """测试嵌套对话结构缺少字段"""
        data = {
            "panel_number": 1,
            "description": "测试场景",
            "dialogue": [
                {"text": "独白内容"}  # missing "speaker"
            ],
        }
        
        result = self.guard.validate(data, SchemaType.PANEL)
        
        assert result.is_valid is False
        assert any("speaker" in err for err in result.errors)

    def test_validate_panel_unknown_field_warning(self):
        """测试未知字段产生警告"""
        data = {
            "panel_number": 1,
            "description": "测试描述",
            "unknown_field": "some value",
        }
        
        result = self.guard.validate(data, SchemaType.PANEL)
        
        assert result.is_valid is True  # 非严格模式下仍然通过
        assert any("unknown_field" in warn for warn in result.warnings)

    def test_validate_panel_strict_mode_rejects_unknown_field(self):
        """测试严格模式下未知字段导致失败"""
        data = {
            "panel_number": 1,
            "description": "测试描述",
            "unknown_field": "some value",
        }
        
        result = self.guard.validate(data, SchemaType.PANEL, strict=True)
        
        assert result.is_valid is False

    # === Storyboard Schema Tests ===

    def test_validate_valid_storyboard(self):
        """测试有效的Storyboard数据通过验证"""
        data = {
            "panels": [
                {"panel_number": 1, "description": "开场"},
                {"panel_number": 2, "description": "发展"},
            ],
            "title": "猫咪偷鱼记",
            "characters": ["橘猫", "主人"],
            "scenes": ["厨房", "客厅"],
        }
        
        result = self.guard.validate(data, SchemaType.STORYBOARD)
        
        assert result.is_valid is True

    def test_validate_storyboard_missing_panels(self):
        """测试缺少panels字段的Storyboard被拒绝"""
        data = {
            "title": "测试标题",
        }
        
        result = self.guard.validate(data, SchemaType.STORYBOARD)
        
        assert result.is_valid is False
        assert any("panels" in err for err in result.errors)

    # === Character Schema Tests ===

    def test_validate_valid_character(self):
        """测试有效的Character数据通过验证"""
        data = {
            "name": "橘猫咪咪",
            "description": "一只胖胖的橘猫",
            "appearance": "橘色毛发，绿色眼睛",
            "personality": "贪吃，慵懒",
        }
        
        result = self.guard.validate(data, SchemaType.CHARACTER)
        
        assert result.is_valid is True

    def test_validate_character_missing_name(self):
        """测试缺少name字段的Character被拒绝"""
        data = {
            "description": "一只神秘的猫",
        }
        
        result = self.guard.validate(data, SchemaType.CHARACTER)
        
        assert result.is_valid is False
        assert any("name" in err for err in result.errors)

    # === Scene Schema Tests ===

    def test_validate_valid_scene(self):
        """测试有效的Scene数据通过验证"""
        data = {
            "name": "厨房",
            "description": "现代风格的厨房，有大理石台面",
            "time_of_day": "afternoon",
        }
        
        result = self.guard.validate(data, SchemaType.SCENE)
        
        assert result.is_valid is True

    # === RenderPlan Schema Tests ===

    def test_validate_valid_render_plan(self):
        """测试有效的RenderPlan数据通过验证"""
        data = {
            "panel_id": "panel-001",
            "workflow": "txt2img_standard",
            "parameters": {
                "steps": 30,
                "cfg_scale": 7.5,
            },
            "priority": 5,
        }
        
        result = self.guard.validate(data, SchemaType.RENDER_PLAN)
        
        assert result.is_valid is True


class TestSchemaGuardDefaults:
    """测试SchemaGuard的默认值功能"""

    def test_add_defaults_to_panel(self):
        """测试为Panel添加默认值"""
        data = {
            "panel_number": 1,
            "description": "测试",
        }
        
        result = SchemaGuard.add_defaults(data, SchemaType.PANEL)
        
        assert "dialogue" in result
        assert result["dialogue"] == []
        assert "camera" in result
        assert result["camera"]["angle"] == "eye_level"

    def test_add_defaults_preserves_existing_values(self):
        """测试添加默认值时不覆盖已有值"""
        data = {
            "panel_number": 1,
            "description": "测试",
            "dialogue": [{"speaker": "A", "text": "Hi"}],
        }
        
        result = SchemaGuard.add_defaults(data, SchemaType.PANEL)
        
        assert len(result["dialogue"]) == 1
        assert result["dialogue"][0]["text"] == "Hi"


class TestSchemaGuardGetSchema:
    """测试获取Schema定义"""

    def setup_method(self):
        self.guard = SchemaGuard()

    def test_get_panel_schema(self):
        """测试获取Panel Schema"""
        schema = self.guard.get_schema(SchemaType.PANEL)
        
        assert "required" in schema
        assert "panel_number" in schema["required"]
        assert "description" in schema["required"]

    def test_get_unknown_schema_returns_empty(self):
        """测试获取未知Schema类型返回空dict"""
        schema = self.guard.get_schema("unknown_type")
        
        assert schema == {}


# === Async Tests for Auto-Repair ===

@pytest.fixture
def mock_llm_response(monkeypatch):
    """Mock LLM响应用于测试auto-repair"""
    async def mock_chat_completion(self, messages, response_format="text"):
        # 返回修复后的JSON
        return '{"panel_number": 1, "description": "已修复的描述"}'
    
    monkeypatch.setattr(
        "app.services.agents.schema_guard.StandardLLMService._chat_completion",
        mock_chat_completion
    )


@pytest.mark.asyncio
async def test_validate_and_repair_valid_data():
    """测试有效数据不触发修复"""
    guard = SchemaGuard(auto_repair=True)
    data = {
        "panel_number": 1,
        "description": "有效描述",
    }
    
    result = await guard.validate_and_repair(data, SchemaType.PANEL)
    
    assert result.is_valid is True
    assert result.repaired_data is None  # 没有修复


@pytest.mark.asyncio
async def test_validate_and_repair_disabled():
    """测试禁用auto-repair"""
    guard = SchemaGuard(auto_repair=False)
    data = {
        "panel_number": 1,
        # missing description
    }
    
    result = await guard.validate_and_repair(data, SchemaType.PANEL)
    
    assert result.is_valid is False
    assert result.repaired_data is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
