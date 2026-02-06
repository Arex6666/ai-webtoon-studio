"""
Brain Service Base - LLM 服务基类
用于脚本分析、气泡位置建议等智能功能

扩展功能：
- 剧本自动分镜
- 连续性检测
- 一键修复建议
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============ 数据模型 ============

class ParsedPanel(BaseModel):
    """解析后的分镜"""
    panel_index: int
    action_description: str
    dialogue: Optional[str] = None
    shot_type: str = "medium"  # extreme_close, close, medium, full, wide, extreme_wide
    camera_angle: str = "eye_level"  # eye_level, high, low, bird, worm
    emotion: str = "neutral"
    characters: List[str] = []
    character_refs: List[str] = []  # 角色 ID 引用
    scene_description: Optional[str] = None
    scene_ref: Optional[str] = None  # 场景 ID 引用
    time_of_day: str = "day"
    weather: str = "clear"
    suggested_duration: float = 2.0  # 建议停留时间（秒）


class ContinuityIssue(BaseModel):
    """连续性问题"""
    panel_index: int = 0
    panel_ids: List[str] = []  # 受影响的分镜 ID
    type: str = "unknown"  # weather_change, time_change, costume_change, location_jump, face_drift
    issue_type: str = ""  # 兼容旧字段
    severity: str = "warning"  # info, warning, error
    description: str = ""  # 问题描述
    message: str = ""  # 兼容旧字段
    prev_value: Optional[str] = None
    current_value: Optional[str] = None
    suggestion: Optional[str] = None
    auto_fixable: bool = False


class ScriptParseResult(BaseModel):
    """剧本解析结果"""
    panels: List[ParsedPanel]
    detected_characters: List[str]
    detected_scenes: List[str]
    detected_props: List[str] = []  # S5-04: 检测到的物品
    total_duration: float
    continuity_issues: List[ContinuityIssue] = []


class ContinuityCheckResult(BaseModel):
    """连续性检测结果"""
    is_valid: bool
    issues: List[ContinuityIssue]
    auto_fix_available: bool = False
    suggested_fixes: List[Dict[str, Any]] = []


class BaseBrainService(ABC):
    """LLM 服务基类"""
    
    @abstractmethod
    async def analyze_script(self, script_text: str) -> List[Dict[str, Any]]:
        """
        分析脚本，拆解为分镜
        
        Returns:
            List of panel suggestions with:
            - action_description: 动作描述
            - dialogue: 对话内容
            - shot_type: 建议景别
            - emotion: 情绪基调
        """
        pass
    
    @abstractmethod
    async def parse_script(
        self, 
        script_text: str,
        style_hint: Optional[str] = None
    ) -> ScriptParseResult:
        """
        解析剧本为分镜（增强版）
        
        Args:
            script_text: 剧本文本（可以是一句话或完整剧本）
            style_hint: 风格提示（如"韩漫"、"日漫"）
            
        Returns:
            完整的解析结果，包含分镜列表和检测到的角色/场景
        """
        pass
    
    @abstractmethod
    async def check_continuity(
        self,
        panels: List[Dict[str, Any]],
        characters: Optional[Dict[str, Any]] = None,
        scenes: Optional[Dict[str, Any]] = None
    ) -> ContinuityCheckResult:
        """
        检测分镜序列的连续性
        
        Args:
            panels: 分镜列表
            characters: 角色资产信息（用于检测服装等一致性）
            scenes: 场景资产信息（用于检测场景一致性）
            
        Returns:
            连续性检测结果
        """
        pass
    
    @abstractmethod
    async def suggest_fix(
        self,
        issue: ContinuityIssue,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        为连续性问题提供修复建议
        
        Returns:
            修复建议，包含修改后的值
        """
        pass
    
    @abstractmethod
    async def suggest_bubble_positions(
        self,
        panel_spec: Dict[str, Any],
        layer_bbox: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        根据分镜规格和角色位置，建议气泡放置位置
        
        Returns:
            List of bubble position suggestions
        """
        pass
    
    @abstractmethod
    async def enhance_prompt(self, base_prompt: str, style: str) -> str:
        """
        增强/优化提示词
        """
        pass
    
    @abstractmethod
    async def qa_analyze(
        self,
        panel_spec: Dict[str, Any],
        rendered_images: List[str]
    ) -> Dict[str, Any]:
        """
        质量分析
        
        Returns:
            QA report with scores and issues
        """
        pass


def get_brain_service() -> BaseBrainService:
    """
    获取 Brain 服务实例
    如果配置了 LLM API Key 则使用真实服务，否则使用 Mock
    """
    # 使用 effective_llm_api_key 来检查是否有可用的 API Key
    api_key = settings.effective_llm_api_key
    
    if api_key:
        from .standard_llm import StandardLLMService
        
        # 预设 Base URL (如果用户未指定)
        base_url = settings.effective_llm_base_url
                
        logger.info(f"Using {settings.LLM_PROVIDER} LLM service with model {settings.effective_llm_model}")
        return StandardLLMService(base_url=base_url, api_key=api_key)
    else:
        logger.warning("No LLM API key configured, using MockBrainService")
        from .mock import MockBrainService
        return MockBrainService()

