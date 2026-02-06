"""
PatchGenerator 单元测试
"""
import pytest
import sys
import os

# Add the app directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.agents.patch_generator import (
    PatchGenerator, 
    Patch, 
    PatchOperation, 
    PatchTarget,
    PatchResult,
)


class TestPatchOperations:
    """测试Patch应用操作"""

    def setup_method(self):
        """每个测试方法前初始化"""
        self.generator = PatchGenerator()

    # === ADD操作测试 ===

    def test_patch_add_new_field(self):
        """测试ADD操作添加新字段"""
        target = {"name": "测试"}
        patch = Patch(
            op=PatchOperation.ADD,
            path="/description",
            value="新描述",
            reason="添加描述"
        )
        
        result = self.generator.apply_patches(target, [patch])
        
        assert result["description"] == "新描述"
        assert result["name"] == "测试"  # 原有字段不变

    def test_patch_add_nested_field(self):
        """测试ADD操作添加嵌套字段"""
        target = {"panel": {"camera": {}}}
        patch = Patch(
            op=PatchOperation.ADD,
            path="/panel/camera/angle",
            value="top_down",
            reason="添加镜头角度"
        )
        
        result = self.generator.apply_patches(target, [patch])
        
        assert result["panel"]["camera"]["angle"] == "top_down"

    def test_patch_add_array_element(self):
        """测试ADD操作添加数组元素"""
        target = {"characters": ["角色A", "角色B"]}
        patch = Patch(
            op=PatchOperation.ADD,
            path="/characters/-",
            value="角色C",
            reason="添加新角色"
        )
        
        result = self.generator.apply_patches(target, [patch])
        
        assert len(result["characters"]) == 3
        assert result["characters"][2] == "角色C"

    def test_patch_add_array_element_at_index(self):
        """测试ADD操作在指定位置插入数组元素"""
        target = {"items": ["a", "c"]}
        patch = Patch(
            op=PatchOperation.ADD,
            path="/items/1",
            value="b",
            reason="在中间插入"
        )
        
        result = self.generator.apply_patches(target, [patch])
        
        assert result["items"] == ["a", "b", "c"]

    # === REMOVE操作测试 ===

    def test_patch_remove_field(self):
        """测试REMOVE操作删除字段"""
        target = {"name": "测试", "description": "要删除的"}
        patch = Patch(
            op=PatchOperation.REMOVE,
            path="/description",
            reason="删除描述"
        )
        
        result = self.generator.apply_patches(target, [patch])
        
        assert "description" not in result
        assert result["name"] == "测试"

    def test_patch_remove_array_element(self):
        """测试REMOVE操作删除数组元素"""
        target = {"items": ["a", "b", "c"]}
        patch = Patch(
            op=PatchOperation.REMOVE,
            path="/items/1",
            reason="删除中间元素"
        )
        
        result = self.generator.apply_patches(target, [patch])
        
        assert result["items"] == ["a", "c"]

    # === REPLACE操作测试 ===

    def test_patch_replace_field(self):
        """测试REPLACE操作替换字段"""
        target = {"camera": {"angle": "eye_level"}}
        patch = Patch(
            op=PatchOperation.REPLACE,
            path="/camera/angle",
            value="top_down",
            reason="改为俯视"
        )
        
        result = self.generator.apply_patches(target, [patch])
        
        assert result["camera"]["angle"] == "top_down"

    def test_patch_replace_array_element(self):
        """测试REPLACE操作替换数组元素"""
        target = {"panels": [
            {"description": "旧描述"},
            {"description": "保持不变"}
        ]}
        patch = Patch(
            op=PatchOperation.REPLACE,
            path="/panels/0/description",
            value="新描述",
            reason="修改第一格描述"
        )
        
        result = self.generator.apply_patches(target, [patch])
        
        assert result["panels"][0]["description"] == "新描述"
        assert result["panels"][1]["description"] == "保持不变"

    # === MOVE操作测试 ===

    def test_patch_move_field(self):
        """测试MOVE操作移动字段"""
        target = {"source": "value", "other": "keep"}
        # 将source字段移动到新位置renamed
        patch = Patch(
            op=PatchOperation.MOVE,
            path="/renamed",
            from_path="/source",
            reason="重命名字段"
        )
        
        result = self.generator.apply_patches(target, [patch])
        
        assert "source" not in result
        assert result["renamed"] == "value"
        assert result["other"] == "keep"

    # === COPY操作测试 ===

    def test_patch_copy_field(self):
        """测试COPY操作复制字段"""
        target = {"source": "原始值", "other": "其他"}
        patch = Patch(
            op=PatchOperation.COPY,
            path="/target",
            from_path="/source",
            reason="复制字段"
        )
        
        result = self.generator.apply_patches(target, [patch])
        
        assert result["source"] == "原始值"
        assert result["target"] == "原始值"

    # === 多Patch测试 ===

    def test_apply_multiple_patches(self):
        """测试应用多个Patch"""
        target = {
            "panel_number": 1,
            "description": "原始描述",
            "characters": ["角色A"]
        }
        patches = [
            Patch(
                op=PatchOperation.REPLACE,
                path="/description",
                value="新描述",
                reason="修改描述"
            ),
            Patch(
                op=PatchOperation.ADD,
                path="/characters/-",
                value="角色B",
                reason="添加角色"
            ),
            Patch(
                op=PatchOperation.ADD,
                path="/mood",
                value="紧张",
                reason="添加情绪"
            ),
        ]
        
        result = self.generator.apply_patches(target, patches)
        
        assert result["description"] == "新描述"
        assert "角色B" in result["characters"]
        assert result["mood"] == "紧张"


class TestJsonPointerParsing:
    """测试JSON Pointer解析"""

    def setup_method(self):
        self.generator = PatchGenerator()

    def test_parse_simple_path(self):
        """测试解析简单路径"""
        parts = self.generator._parse_json_pointer("/name")
        assert parts == ["name"]

    def test_parse_nested_path(self):
        """测试解析嵌套路径"""
        parts = self.generator._parse_json_pointer("/panel/camera/angle")
        assert parts == ["panel", "camera", "angle"]

    def test_parse_array_path(self):
        """测试解析数组路径"""
        parts = self.generator._parse_json_pointer("/panels/0/description")
        assert parts == ["panels", "0", "description"]

    def test_parse_empty_path(self):
        """测试解析空路径"""
        parts = self.generator._parse_json_pointer("")
        assert parts == []

    def test_parse_root_path(self):
        """测试解析根路径"""
        parts = self.generator._parse_json_pointer("/")
        assert parts == []


class TestPatchModel:
    """测试Patch模型"""

    def test_create_patch_with_required_fields(self):
        """测试创建基本Patch"""
        patch = Patch(
            op=PatchOperation.REPLACE,
            path="/test",
            value="new value",
            reason="test reason"
        )
        
        assert patch.op == PatchOperation.REPLACE
        assert patch.path == "/test"
        assert patch.value == "new value"

    def test_create_simple_patch_helper(self):
        """测试便捷创建方法"""
        patch = PatchGenerator.create_simple_patch(
            op=PatchOperation.ADD,
            path="/new_field",
            value=123,
            reason="添加数字字段"
        )
        
        assert patch.op == PatchOperation.ADD
        assert patch.value == 123


class TestPatchSerialization:
    """测试Patch序列化"""

    def test_patches_to_json(self):
        """测试将Patch列表转为JSON"""
        patches = [
            Patch(
                op=PatchOperation.REPLACE,
                path="/camera/angle",
                value="top_down",
                reason="改为俯视"
            ),
            Patch(
                op=PatchOperation.ADD,
                path="/characters/-",
                value="新角色",
                reason="添加角色"
            ),
        ]
        
        json_str = PatchGenerator.patches_to_json(patches)
        
        import json
        data = json.loads(json_str)
        assert len(data) == 2
        assert data[0]["op"] == "replace"
        assert data[1]["op"] == "add"


class TestPatchResult:
    """测试PatchResult模型"""

    def test_create_success_result(self):
        """测试创建成功结果"""
        result = PatchResult(
            success=True,
            patches=[Patch(op=PatchOperation.ADD, path="/test", value="v", reason="r")],
            target_type=PatchTarget.PANEL,
            summary="测试摘要"
        )
        
        assert result.success is True
        assert len(result.patches) == 1
        assert result.error is None

    def test_create_error_result(self):
        """测试创建错误结果"""
        result = PatchResult(
            success=False,
            patches=[],
            target_type=PatchTarget.STORYBOARD,
            error="发生错误"
        )
        
        assert result.success is False
        assert result.error == "发生错误"


# === 异步测试 ===

@pytest.mark.asyncio
async def test_generate_patch_returns_result():
    """测试generate_patch返回PatchResult"""
    # 这个测试需要mock LLM，暂时跳过实际调用
    generator = PatchGenerator()
    
    # 至少验证方法签名正确
    assert hasattr(generator, 'generate_patch')
    assert callable(generator.generate_patch)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
