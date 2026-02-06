"""
DependencyGraph - 依赖图+失效规则
定义元素间的依赖关系，计算修改影响范围
"""
import logging
import re
from typing import Dict, Any, Optional, List, Set
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """变更类型"""
    SCRIPT = "script"           # 剧本/对白文本
    DIALOGUE = "dialogue"       # 气泡对白
    CAMERA = "camera"           # 镜头角度/景别
    CHARACTER = "character"     # 角色外观
    SCENE = "scene"             # 场景
    PROP = "prop"               # 道具
    LAYOUT = "layout"           # 构图/排版
    STYLE = "style"             # 画风/风格


class RenderTarget(str, Enum):
    """渲染目标类型"""
    FULL_RENDER = "full_render"     # 完整渲染
    TYPESET_ONLY = "typeset_only"   # 仅排版
    COMPOSITE = "composite"          # 合成层
    NONE = "none"                   # 无需渲染


class InvalidationRule(BaseModel):
    """失效规则"""
    change_type: ChangeType = Field(..., description="变更类型")
    pattern: str = Field(..., description="路径匹配模式")
    render_target: RenderTarget = Field(..., description="需要重渲染的类型")
    scope: str = Field("panel", description="影响范围: panel/chapter/all")
    description: str = Field("", description="规则描述")


class InvalidatedPanel(BaseModel):
    """失效的分镜"""
    panel_id: str = Field(..., description="分镜ID或索引")
    render_target: RenderTarget = Field(..., description="需要的渲染类型")
    reason: str = Field("", description="失效原因")
    change_path: str = Field("", description="触发变更的路径")


class RenderPlan(BaseModel):
    """渲染计划"""
    full_render_panels: List[str] = Field(default_factory=list, description="需完整渲染的分镜")
    typeset_only_panels: List[str] = Field(default_factory=list, description="仅需排版的分镜")
    composite_panels: List[str] = Field(default_factory=list, description="需合成的分镜")
    summary: str = Field("", description="计划摘要")


class DependencyGraph:
    """
    依赖图+失效规则引擎
    
    根据变更类型和路径，计算需要重新渲染的分镜范围。
    """

    # 预定义的失效规则
    DEFAULT_RULES: List[InvalidationRule] = [
        # 对白/文本变更 -> 仅重排版
        InvalidationRule(
            change_type=ChangeType.DIALOGUE,
            pattern=r"/panels/(\d+)/dialogue",
            render_target=RenderTarget.TYPESET_ONLY,
            scope="panel",
            description="对白内容修改仅影响排版"
        ),
        InvalidationRule(
            change_type=ChangeType.SCRIPT,
            pattern=r"/panels/(\d+)/narration",
            render_target=RenderTarget.TYPESET_ONLY,
            scope="panel",
            description="旁白修改仅影响排版"
        ),
        
        # 镜头/构图变更 -> 该分镜完整渲染
        InvalidationRule(
            change_type=ChangeType.CAMERA,
            pattern=r"/panels/(\d+)/camera",
            render_target=RenderTarget.FULL_RENDER,
            scope="panel",
            description="镜头角度/景别改变需完整渲染"
        ),
        InvalidationRule(
            change_type=ChangeType.LAYOUT,
            pattern=r"/panels/(\d+)/(composition|layout|action)",
            render_target=RenderTarget.FULL_RENDER,
            scope="panel",
            description="构图/动作改变需完整渲染"
        ),
        
        # 角色外观变更 -> 所有包含该角色的分镜
        InvalidationRule(
            change_type=ChangeType.CHARACTER,
            pattern=r"/characters/(\d+)/(appearance|outfit|expression)",
            render_target=RenderTarget.FULL_RENDER,
            scope="all",
            description="角色外观改变影响所有相关分镜"
        ),
        
        # 场景变更 -> 所有使用该场景的分镜
        InvalidationRule(
            change_type=ChangeType.SCENE,
            pattern=r"/scenes/(\d+)",
            render_target=RenderTarget.FULL_RENDER,
            scope="all",
            description="场景改变影响所有相关分镜"
        ),
        
        # 风格变更 -> 所有分镜
        InvalidationRule(
            change_type=ChangeType.STYLE,
            pattern=r"/style",
            render_target=RenderTarget.FULL_RENDER,
            scope="all",
            description="画风改变需要全部重渲染"
        ),
        
        # 分镜描述变更 -> 该分镜完整渲染
        InvalidationRule(
            change_type=ChangeType.LAYOUT,
            pattern=r"/panels/(\d+)/description",
            render_target=RenderTarget.FULL_RENDER,
            scope="panel",
            description="分镜描述改变需完整渲染"
        ),
    ]

    def __init__(self, custom_rules: Optional[List[InvalidationRule]] = None):
        """
        初始化依赖图
        
        Args:
            custom_rules: 自定义规则，会与默认规则合并
        """
        self.rules = self.DEFAULT_RULES.copy()
        if custom_rules:
            self.rules.extend(custom_rules)

    def get_invalidated_panels(
        self,
        storyboard: Dict[str, Any],
        patch_paths: List[str],
    ) -> List[InvalidatedPanel]:
        """
        根据Patch路径计算失效的分镜
        
        Args:
            storyboard: 分镜数据
            patch_paths: 修改的路径列表
            
        Returns:
            失效的分镜列表
        """
        invalidated: Dict[str, InvalidatedPanel] = {}  # panel_id -> InvalidatedPanel
        
        for path in patch_paths:
            for rule in self.rules:
                match = re.match(rule.pattern, path)
                if match:
                    affected_panels = self._get_affected_panels(
                        storyboard, path, rule, match
                    )
                    for panel_id in affected_panels:
                        # 如果已存在，取更高优先级的渲染类型
                        if panel_id in invalidated:
                            existing = invalidated[panel_id]
                            if self._render_priority(rule.render_target) > self._render_priority(existing.render_target):
                                invalidated[panel_id] = InvalidatedPanel(
                                    panel_id=panel_id,
                                    render_target=rule.render_target,
                                    reason=rule.description,
                                    change_path=path,
                                )
                        else:
                            invalidated[panel_id] = InvalidatedPanel(
                                panel_id=panel_id,
                                render_target=rule.render_target,
                                reason=rule.description,
                                change_path=path,
                            )
                    break  # 一个路径匹配一个规则即可
        
        return list(invalidated.values())

    def _get_affected_panels(
        self,
        storyboard: Dict[str, Any],
        path: str,
        rule: InvalidationRule,
        match: re.Match,
    ) -> List[str]:
        """获取受影响的分镜ID列表"""
        panels = storyboard.get("panels", [])
        
        if rule.scope == "panel":
            # 仅影响匹配的分镜
            if match.groups():
                panel_idx = match.group(1)
                return [f"panel_{panel_idx}"]
            return []
            
        elif rule.scope == "chapter":
            # 影响当前章节的所有分镜
            return [f"panel_{i}" for i in range(len(panels))]
            
        elif rule.scope == "all":
            # 根据变更类型找到所有相关分镜
            if rule.change_type == ChangeType.CHARACTER:
                # 找到角色名称
                char_idx = int(match.group(1)) if match.groups() else -1
                characters = storyboard.get("characters", [])
                if 0 <= char_idx < len(characters):
                    char_name = characters[char_idx].get("name", "")
                    # 找到包含该角色的所有分镜
                    affected = []
                    for i, panel in enumerate(panels):
                        panel_chars = panel.get("characters", [])
                        if char_name in panel_chars:
                            affected.append(f"panel_{i}")
                    return affected
                    
            elif rule.change_type == ChangeType.SCENE:
                # 找到场景名称
                scene_idx = int(match.group(1)) if match.groups() else -1
                scenes = storyboard.get("scenes", [])
                if 0 <= scene_idx < len(scenes):
                    scene_name = scenes[scene_idx].get("name", "")
                    # 找到使用该场景的所有分镜
                    affected = []
                    for i, panel in enumerate(panels):
                        if panel.get("scene") == scene_name:
                            affected.append(f"panel_{i}")
                    return affected
                    
            elif rule.change_type == ChangeType.STYLE:
                # 风格变更影响所有分镜
                return [f"panel_{i}" for i in range(len(panels))]
        
        return []

    def _render_priority(self, render_target: RenderTarget) -> int:
        """获取渲染优先级（数字越大优先级越高）"""
        priority_map = {
            RenderTarget.NONE: 0,
            RenderTarget.TYPESET_ONLY: 1,
            RenderTarget.COMPOSITE: 2,
            RenderTarget.FULL_RENDER: 3,
        }
        return priority_map.get(render_target, 0)

    def build_render_plan(
        self,
        storyboard: Dict[str, Any],
        patch_paths: List[str],
    ) -> RenderPlan:
        """
        构建渲染计划
        
        Args:
            storyboard: 分镜数据
            patch_paths: 修改的路径列表
            
        Returns:
            渲染计划
        """
        invalidated = self.get_invalidated_panels(storyboard, patch_paths)
        
        full_render = []
        typeset_only = []
        composite = []
        
        for panel in invalidated:
            if panel.render_target == RenderTarget.FULL_RENDER:
                full_render.append(panel.panel_id)
            elif panel.render_target == RenderTarget.TYPESET_ONLY:
                typeset_only.append(panel.panel_id)
            elif panel.render_target == RenderTarget.COMPOSITE:
                composite.append(panel.panel_id)
        
        # 去重
        full_render = list(set(full_render))
        typeset_only = list(set(typeset_only) - set(full_render))
        composite = list(set(composite) - set(full_render) - set(typeset_only))
        
        summary_parts = []
        if full_render:
            summary_parts.append(f"{len(full_render)}格需完整渲染")
        if typeset_only:
            summary_parts.append(f"{len(typeset_only)}格需重排版")
        if composite:
            summary_parts.append(f"{len(composite)}格需合成")
        
        return RenderPlan(
            full_render_panels=sorted(full_render),
            typeset_only_panels=sorted(typeset_only),
            composite_panels=sorted(composite),
            summary=", ".join(summary_parts) if summary_parts else "无需重渲染",
        )

    def analyze_patch_impact(
        self,
        storyboard: Dict[str, Any],
        patches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        分析Patch影响
        
        Args:
            storyboard: 分镜数据
            patches: Patch列表
            
        Returns:
            影响分析结果
        """
        # 提取所有路径
        paths = [p.get("path", "") for p in patches]
        
        # 获取失效分镜
        invalidated = self.get_invalidated_panels(storyboard, paths)
        
        # 构建渲染计划
        render_plan = self.build_render_plan(storyboard, paths)
        
        return {
            "total_patches": len(patches),
            "affected_panels": len(invalidated),
            "invalidated_panels": [p.dict() for p in invalidated],
            "render_plan": render_plan.dict(),
        }

    def get_rules(self) -> List[InvalidationRule]:
        """获取所有规则"""
        return self.rules

    def add_rule(self, rule: InvalidationRule) -> None:
        """添加自定义规则"""
        self.rules.append(rule)
