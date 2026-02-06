"""
AssetGenerator - 资产生成器
当匹配失败时，生成候选资产定义供用户确认
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum

from app.services.brain.standard_llm import StandardLLMService

logger = logging.getLogger(__name__)


class GenerationStatus(str, Enum):
    """生成状态"""
    PENDING = "pending"         # 待生成
    GENERATING = "generating"   # 生成中
    READY = "ready"             # 已生成，待确认
    CONFIRMED = "confirmed"     # 已确认
    REJECTED = "rejected"       # 已拒绝


class AssetDraft(BaseModel):
    """资产草稿"""
    id: str = Field(..., description="草稿ID")
    name: str = Field(..., description="资产名称")
    asset_type: str = Field(..., description="资产类型")
    description: str = Field("", description="描述")
    visual_prompt: str = Field("", description="视觉提示词")
    reference_context: str = Field("", description="来源上下文")
    tags: List[str] = Field(default_factory=list, description="标签")
    status: GenerationStatus = Field(default=GenerationStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class GenerationRequest(BaseModel):
    """生成请求"""
    name: str = Field(..., description="资产名称")
    asset_type: str = Field(..., description="资产类型: character/scene/prop")
    context: str = Field("", description="上下文信息")
    style_hint: Optional[str] = Field(None, description="风格提示")


class GenerationResult(BaseModel):
    """生成结果"""
    success: bool = Field(..., description="是否成功")
    draft: Optional[AssetDraft] = Field(None, description="生成的草稿")
    error: Optional[str] = Field(None, description="错误信息")


# LLM提示词模板
CHARACTER_GENERATION_PROMPT = """你是一个专业的角色设计师。根据名称和上下文生成角色定义。

角色名称: {name}
上下文: {context}
风格提示: {style_hint}

请生成JSON格式的角色定义:
{{
  "description": "角色描述（性格、背景）",
  "visual_prompt": "视觉描述，用于AI生图（外貌、服装、发型、配色）",
  "tags": ["标签1", "标签2"],
  "metadata": {{
    "age_range": "年龄范围",
    "personality": ["性格特点"],
    "role": "角色定位"
  }}
}}

只返回JSON，不要其他文字。"""

SCENE_GENERATION_PROMPT = """你是一个专业的场景设计师。根据名称和上下文生成场景定义。

场景名称: {name}
上下文: {context}
风格提示: {style_hint}

请生成JSON格式的场景定义:
{{
  "description": "场景描述（氛围、时间、特点）",
  "visual_prompt": "视觉描述，用于AI生图（环境、光影、构图建议）",
  "tags": ["标签1", "标签2"],
  "metadata": {{
    "time_of_day": "时间",
    "mood": "氛围",
    "key_elements": ["关键元素"]
  }}
}}

只返回JSON，不要其他文字。"""

PROP_GENERATION_PROMPT = """你是一个专业的道具设计师。根据名称和上下文生成道具定义。

道具名称: {name}
上下文: {context}
风格提示: {style_hint}

请生成JSON格式的道具定义:
{{
  "description": "道具描述（用途、材质）",
  "visual_prompt": "视觉描述，用于AI生图（外观、细节）",
  "tags": ["标签1", "标签2"],
  "metadata": {{
    "category": "类别",
    "significance": "重要性"
  }}
}}

只返回JSON，不要其他文字。"""


class AssetGenerator:
    """
    资产生成器
    
    功能:
    1. 使用LLM根据名称和上下文生成资产定义
    2. 生成视觉提示词用于后续图像生成
    3. 管理资产草稿的生命周期
    """

    def __init__(self):
        self.llm = StandardLLMService()
        self._drafts: Dict[str, AssetDraft] = {}
        self._counter = 0

    async def generate_asset(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        """
        生成资产定义
        
        Args:
            request: 生成请求
            
        Returns:
            生成结果
        """
        try:
            # 选择提示词模板
            if request.asset_type == "character":
                prompt_template = CHARACTER_GENERATION_PROMPT
            elif request.asset_type == "scene":
                prompt_template = SCENE_GENERATION_PROMPT
            elif request.asset_type == "prop":
                prompt_template = PROP_GENERATION_PROMPT
            else:
                return GenerationResult(
                    success=False,
                    error=f"不支持的资产类型: {request.asset_type}"
                )
            
            # 构建提示词
            prompt = prompt_template.format(
                name=request.name,
                context=request.context or "无特定上下文",
                style_hint=request.style_hint or "默认风格",
            )
            
            messages = [
                {"role": "system", "content": "你是一个资产设计助手，生成符合要求的资产定义。"},
                {"role": "user", "content": prompt},
            ]
            
            response = await self.llm._chat_completion(messages, response_format="json")
            
            import json
            data = json.loads(response)
            
            # 创建草稿
            draft = self._create_draft(
                name=request.name,
                asset_type=request.asset_type,
                description=data.get("description", ""),
                visual_prompt=data.get("visual_prompt", ""),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
                reference_context=request.context,
            )
            
            return GenerationResult(
                success=True,
                draft=draft,
            )
            
        except Exception as e:
            logger.error(f"Asset generation failed: {e}", exc_info=True)
            return GenerationResult(
                success=False,
                error=str(e),
            )

    def _create_draft(
        self,
        name: str,
        asset_type: str,
        description: str,
        visual_prompt: str,
        tags: List[str],
        metadata: Dict[str, Any],
        reference_context: str,
    ) -> AssetDraft:
        """创建资产草稿"""
        self._counter += 1
        draft_id = f"draft_{asset_type}_{self._counter:04d}"
        
        draft = AssetDraft(
            id=draft_id,
            name=name,
            asset_type=asset_type,
            description=description,
            visual_prompt=visual_prompt,
            reference_context=reference_context,
            tags=tags,
            status=GenerationStatus.READY,
            metadata=metadata,
        )
        
        self._drafts[draft_id] = draft
        logger.info(f"Created asset draft: {draft_id}")
        return draft

    def get_draft(self, draft_id: str) -> Optional[AssetDraft]:
        """获取草稿"""
        return self._drafts.get(draft_id)

    def list_drafts(
        self,
        asset_type: Optional[str] = None,
        status: Optional[GenerationStatus] = None,
    ) -> List[AssetDraft]:
        """列出草稿"""
        drafts = list(self._drafts.values())
        
        if asset_type:
            drafts = [d for d in drafts if d.asset_type == asset_type]
        if status:
            drafts = [d for d in drafts if d.status == status]
        
        return drafts

    def confirm_draft(self, draft_id: str) -> Optional[AssetDraft]:
        """确认草稿"""
        draft = self._drafts.get(draft_id)
        if draft and draft.status == GenerationStatus.READY:
            draft.status = GenerationStatus.CONFIRMED
            return draft
        return None

    def reject_draft(self, draft_id: str) -> Optional[AssetDraft]:
        """拒绝草稿"""
        draft = self._drafts.get(draft_id)
        if draft and draft.status == GenerationStatus.READY:
            draft.status = GenerationStatus.REJECTED
            return draft
        return None

    def update_draft(
        self,
        draft_id: str,
        updates: Dict[str, Any],
    ) -> Optional[AssetDraft]:
        """更新草稿"""
        draft = self._drafts.get(draft_id)
        if not draft:
            return None
        
        if draft.status not in [GenerationStatus.READY, GenerationStatus.PENDING]:
            return None
        
        for key, value in updates.items():
            if hasattr(draft, key):
                setattr(draft, key, value)
        
        return draft

    async def batch_generate(
        self,
        requests: List[GenerationRequest],
    ) -> List[GenerationResult]:
        """批量生成资产"""
        results = []
        for request in requests:
            result = await self.generate_asset(request)
            results.append(result)
        return results

    def get_visual_prompt(self, draft_id: str) -> Optional[str]:
        """获取视觉提示词（用于图像生成）"""
        draft = self._drafts.get(draft_id)
        if draft:
            return draft.visual_prompt
        return None

    def clear_drafts(self, status: Optional[GenerationStatus] = None) -> int:
        """清理草稿"""
        if status:
            to_remove = [k for k, v in self._drafts.items() if v.status == status]
        else:
            to_remove = list(self._drafts.keys())
        
        for key in to_remove:
            del self._drafts[key]
        
        return len(to_remove)
