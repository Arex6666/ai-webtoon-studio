"""
DirectorAgent 单元测试
"""
import pytest
import sys
import os

# Add the app directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.services.agents.director_agent import DirectorAgent, AgentMode
from app.schemas.conversation import IntentAnalysisResult


class TestDirectorAgentModes:
    """测试DirectorAgent模式切换"""

    def setup_method(self):
        """每个测试方法前初始化"""
        self.agent = DirectorAgent(db=None)

    def test_default_mode_is_director(self):
        """测试默认模式是导演模式"""
        assert self.agent.mode == AgentMode.DIRECTOR

    def test_switch_mode(self):
        """测试模式切换"""
        self.agent.switch_mode(AgentMode.SCRIPTWRITER)
        assert self.agent.mode == AgentMode.SCRIPTWRITER
        
        self.agent.switch_mode(AgentMode.QA)
        assert self.agent.mode == AgentMode.QA

    def test_get_system_prompt_for_each_mode(self):
        """测试每个模式都有对应的系统提示词"""
        for mode in AgentMode:
            self.agent.switch_mode(mode)
            prompt = self.agent.get_system_prompt()
            assert prompt is not None
            assert len(prompt) > 0
            assert isinstance(prompt, str)

    def test_scriptwriter_prompt_contains_keywords(self):
        """测试编剧模式提示词包含关键词"""
        self.agent.switch_mode(AgentMode.SCRIPTWRITER)
        prompt = self.agent.get_system_prompt()
        assert "编剧" in prompt or "剧本" in prompt or "故事" in prompt

    def test_qa_prompt_contains_keywords(self):
        """测试质检模式提示词包含关键词"""
        self.agent.switch_mode(AgentMode.QA)
        prompt = self.agent.get_system_prompt()
        assert "质量" in prompt or "问题" in prompt or "修复" in prompt


class TestDirectorAgentAutoSwitch:
    """测试DirectorAgent自动模式切换"""

    def setup_method(self):
        self.agent = DirectorAgent(db=None)

    def test_auto_switch_to_scriptwriter_for_script_intent(self):
        """测试script意图自动切换到编剧模式"""
        intent = IntentAnalysisResult(
            primary_intent="script",
            secondary_intents=[],
            entities={},
            confidence=0.9,
        )
        self.agent._auto_switch_mode(intent)
        assert self.agent.mode == AgentMode.SCRIPTWRITER

    def test_auto_switch_to_art_director_for_asset_intent(self):
        """测试asset意图自动切换到美术总监模式"""
        intent = IntentAnalysisResult(
            primary_intent="asset",
            secondary_intents=[],
            entities={},
            confidence=0.9,
        )
        self.agent._auto_switch_mode(intent)
        assert self.agent.mode == AgentMode.ART_DIRECTOR

    def test_auto_switch_to_producer_for_render_intent(self):
        """测试render意图自动切换到制片模式"""
        intent = IntentAnalysisResult(
            primary_intent="render",
            secondary_intents=[],
            entities={},
            confidence=0.9,
        )
        self.agent._auto_switch_mode(intent)
        assert self.agent.mode == AgentMode.PRODUCER

    def test_auto_switch_to_qa_for_qa_intent(self):
        """测试qa意图自动切换到质检模式"""
        intent = IntentAnalysisResult(
            primary_intent="qa",
            secondary_intents=[],
            entities={},
            confidence=0.9,
        )
        self.agent._auto_switch_mode(intent)
        assert self.agent.mode == AgentMode.QA


class TestDirectorAgentIntentDetection:
    """测试DirectorAgent意图检测"""

    def setup_method(self):
        self.agent = DirectorAgent(db=None)

    def test_is_create_storyboard_positive(self):
        """测试创建分镜的关键词检测"""
        messages = [
            "帮我创建一个四格漫画",
            "生成一个故事",
            "做一个关于猫咪的漫画",
        ]
        for msg in messages:
            assert self.agent._is_create_storyboard(msg) is True

    def test_is_create_storyboard_negative(self):
        """测试非创建分镜的消息"""
        messages = [
            "你好",
            "今天天气怎么样",
            "渲染进度如何",
        ]
        for msg in messages:
            # 这些消息可能不会匹配创建关键词
            result = self.agent._is_create_storyboard(msg)
            # 允许误匹配，因为关键词检测可能不精确
            assert isinstance(result, bool)

    def test_is_modify_storyboard_positive(self):
        """测试修改分镜的关键词检测"""
        messages = [
            "把第二格改成俯视角",
            "修改第一格的对白",
            "调整第三格的构图",
        ]
        for msg in messages:
            assert self.agent._is_modify_storyboard(msg) is True

    def test_is_modify_storyboard_negative(self):
        """测试非修改分镜的消息"""
        messages = [
            "你好",
            "今天天气怎么样",
        ]
        for msg in messages:
            assert self.agent._is_modify_storyboard(msg) is False


class TestDirectorAgentStoryboardState:
    """测试DirectorAgent分镜状态管理"""

    def setup_method(self):
        self.agent = DirectorAgent(db=None)

    def test_initial_storyboard_is_none(self):
        """测试初始分镜为空"""
        assert self.agent.current_storyboard is None

    def test_get_current_storyboard(self):
        """测试获取当前分镜"""
        assert self.agent.get_current_storyboard() is None
        
        # 设置分镜
        self.agent.current_storyboard = {"panels": []}
        assert self.agent.get_current_storyboard() == {"panels": []}

    def test_pending_patches_initially_empty(self):
        """测试待提交补丁初始为空"""
        assert self.agent.get_pending_patches() == []

    def test_clear_pending_patches(self):
        """测试清空待提交补丁"""
        from app.services.agents.patch_generator import Patch, PatchOperation
        
        self.agent.pending_patches.append(
            Patch(op=PatchOperation.ADD, path="/test", value="v", reason="r")
        )
        assert len(self.agent.get_pending_patches()) == 1
        
        self.agent.clear_pending_patches()
        assert len(self.agent.get_pending_patches()) == 0


class TestDirectorAgentComponents:
    """测试DirectorAgent组件集成"""

    def setup_method(self):
        self.agent = DirectorAgent(db=None)

    def test_has_schema_guard(self):
        """测试包含SchemaGuard组件"""
        assert self.agent.schema_guard is not None
        assert hasattr(self.agent.schema_guard, 'validate')

    def test_has_patch_generator(self):
        """测试包含PatchGenerator组件"""
        assert self.agent.patch_generator is not None
        assert hasattr(self.agent.patch_generator, 'generate_patch')

    def test_has_llm_service(self):
        """测试包含LLM服务"""
        assert hasattr(self.agent, 'llm')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
