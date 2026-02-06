"""
Script Pipeline - 3 阶段 LLM 流水线

Parse → Plan → Bind

这是核心的剧本到分镜转换流水线。
"""
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from app.schemas.script_ir import (
    ScriptIR, CharacterIR, SceneIR, BeatIR,
    CharacterRelationship,
)
from app.schemas.director_profile import (
    DirectorProfile,
    get_default_director,
)

logger = logging.getLogger(__name__)


# ============ Task A: Parse 输出 ============

class ParseResult(BaseModel):
    """Parse 阶段输出"""
    success: bool
    script_ir: Optional[ScriptIR] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # 统计
    character_count: int = 0
    scene_count: int = 0
    beat_count: int = 0


# ============ Task B: Plan 输出 ============

class PanelPlanSpec(BaseModel):
    """分镜计划规格（严格版）"""
    panel_id: str
    beat_id: str  # 关联的 beat
    panel_index: int
    
    # 镜头
    shot_type: str  # ECU/CU/MCU/MS/MLS/LS/WS
    camera_move: str  # static/push_in/pull_out/pan/tilt/handheld
    camera_angle: str  # eye_level/high/low/dutch
    duration_sec: float = Field(ge=1.0, le=15.0)
    lens_hint: Optional[str] = None  # 35mm, 50mm, 85mm...
    
    # 场景
    scene_id: str
    location: str
    time_of_day: str
    weather: str
    mood: str
    
    # 角色
    cast: List[str]  # 角色 ID 列表
    actions: str = Field(min_length=30)  # 动作描述（至少 30 字）
    dialogue: Optional[str] = None
    
    # 导演注释
    composition_notes: str  # 构图要点
    continuity_notes: str  # 一致性约束
    
    # 原文对齐
    source_beat_quote: str


class StoryboardPlan(BaseModel):
    """导演计划"""
    chapter_id: Optional[str] = None
    panels: List[PanelPlanSpec]
    
    # 元数据
    total_duration: float = 0.0
    director_notes: str = ""
    
    # 验证结果
    validation_score: float = 100.0
    validation_issues: List[str] = Field(default_factory=list)


class PlanResult(BaseModel):
    """Plan 阶段输出"""
    success: bool
    plan: Optional[StoryboardPlan] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ============ Task C: Bind 输出 ============

class AssetMatch(BaseModel):
    """资产匹配结果"""
    ref_id: str  # 引用 ID (角色/场景 ID)
    ref_name: str  # 引用名称
    ref_type: str  # character/scene
    
    match_status: str  # exact/fuzzy/pending
    matched_asset_id: Optional[str] = None
    matched_asset_name: Optional[str] = None
    confidence: float = 0.0
    
    # 匹配理由
    match_reason: str = ""
    
    # pending 时的建议
    suggested_asset_type: Optional[str] = None
    suggested_asset_description: Optional[str] = None


class AssetsLockProposal(BaseModel):
    """资产锁定建议"""
    chapter_id: Optional[str] = None
    
    character_matches: List[AssetMatch] = Field(default_factory=list)
    scene_matches: List[AssetMatch] = Field(default_factory=list)
    
    # 缺失资产清单
    missing_assets: List[Dict[str, str]] = Field(
        default_factory=list,
        description="缺失的资产列表，每项包含 type, name, description"
    )
    
    # 总体状态
    all_resolved: bool = False
    pending_count: int = 0


class BindResult(BaseModel):
    """Bind 阶段输出"""
    success: bool
    proposal: Optional[AssetsLockProposal] = None
    errors: List[str] = Field(default_factory=list)


# ============ 流水线服务 ============

class ScriptPipelineService:
    """
    剧本处理流水线
    
    3 阶段:
    1. Parse: 剧本 → ScriptIR
    2. Plan: ScriptIR + DirectorProfile → StoryboardPlan
    3. Bind: StoryboardPlan + 资产库 → AssetsLockProposal
    """
    
    def __init__(self, llm_service=None):
        """
        Args:
            llm_service: LLM 服务实例（用于调用 LLM API）
        """
        self.llm = llm_service
        
    async def run_full_pipeline(
        self,
        script_text: str,
        director: Optional[DirectorProfile] = None,
        assets_index: Optional[Dict[str, List[Dict]]] = None,
        chapter_id: Optional[str] = None
    ) -> Tuple[ParseResult, PlanResult, BindResult]:
        """
        运行完整流水线
        
        Args:
            script_text: 剧本原文
            director: 导演风格约束（默认使用默认导演）
            assets_index: 资产库索引 {"characters": [...], "scenes": [...]}
            chapter_id: 章节 ID
        
        Returns:
            (ParseResult, PlanResult, BindResult)
        """
        director = director or get_default_director()
        assets_index = assets_index or {"characters": [], "scenes": []}
        
        # Task A: Parse
        parse_result = await self.task_parse(script_text)
        if not parse_result.success:
            return (
                parse_result,
                PlanResult(success=False, errors=["Parse 失败，跳过 Plan"]),
                BindResult(success=False, errors=["Parse 失败，跳过 Bind"])
            )
        
        # Task B: Plan
        plan_result = await self.task_plan(parse_result.script_ir, director)
        if not plan_result.success:
            return (
                parse_result,
                plan_result,
                BindResult(success=False, errors=["Plan 失败，跳过 Bind"])
            )
        
        # Task C: Bind
        bind_result = await self.task_bind(plan_result.plan, assets_index)
        
        return parse_result, plan_result, bind_result
    
    # ===== Task A: Parse =====
    
    async def task_parse(self, script_text: str) -> ParseResult:
        """
        Task A: 结构化解析
        
        输入：剧本全文
        输出：ScriptIR（角色表/场景表/beats）
        """
        from app.services.brain.base import get_brain_service
        
        system_prompt = self._build_parse_prompt()
        user_prompt = f"""请解析以下剧本，提取角色、场景和剧情节拍。

---剧本开始---
{script_text}
---剧本结束---

请严格按照 JSON Schema 格式返回，确保：
1. 每个 beat 都有 source_quote（原文摘录）
2. 角色和场景都被正确识别
3. 情绪变化用 "起始 → 结束" 格式
"""
        
        try:
            brain = get_brain_service()
            
            # 调用 LLM
            response = await brain._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format="json"
            )
            
            # 解析 JSON
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                # 尝试清理
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                data = json.loads(response)
            
            # 构建 ScriptIR
            script_ir = self._build_script_ir(data, script_text)
            
            # 验证完整性
            issues = script_ir.validate_integrity()
            
            return ParseResult(
                success=True,
                script_ir=script_ir,
                warnings=issues,
                character_count=len(script_ir.characters),
                scene_count=len(script_ir.scenes),
                beat_count=len(script_ir.beats)
            )
            
        except Exception as e:
            logger.error(f"Task Parse failed: {e}")
            return ParseResult(success=False, errors=[str(e)])
    
    def _build_parse_prompt(self) -> str:
        """构建 Parse 阶段的系统提示词"""
        return """你是一位专业的剧本分析师。你的任务是将剧本文本解析为结构化数据。

## 输出格式

返回 JSON 对象，包含以下字段：

```json
{
  "characters": [
    {
      "id": "char_01",
      "name": "周昀",
      "aliases": ["他", "男主"],
      "gender": "male",
      "age_range": "20s",
      "appearance_keywords": ["斯文", "眼镜", "书卷气"],
      "personality_keywords": ["内敛", "温柔", "专一"],
      "relationships": [
        {"target_id": "char_02", "relation_type": "crush", "description": "暗恋对象"}
      ],
      "importance": "protagonist"
    }
  ],
  "scenes": [
    {
      "id": "scene_01",
      "name": "旧书店",
      "location_type": "indoor",
      "time_period": "afternoon",
      "weather": "rainy",
      "atmosphere_keywords": ["温馨", "怀旧", "书香"],
      "props": ["书架", "旧书", "落地灯"],
      "visual_description": "昏黄灯光下的老式书店，木质书架摆满旧书"
    }
  ],
  "beats": [
    {
      "id": "beat_01",
      "index": 0,
      "who": ["char_01", "char_02"],
      "where": "scene_01",
      "when": "某个雨天下午",
      "what_happens": "周昀在书店里看着窗外的雨，林知夏推门进来",
      "why_intent": "建立两人初次相遇的场景",
      "emotion_shift": "平静 → 心动",
      "source_quote": "雨下得很轻，像有人把城市的喧嚣也一并...",
      "tension_level": 3,
      "pacing": "slow",
      "dialogue": null,
      "suggested_duration": 5.0,
      "suggested_panel_count": 2
    }
  ],
  "total_duration_hint": 60.0,
  "emotional_arc": "平静 → 心动 → 遗憾 → 释然",
  "key_moments": ["beat_03", "beat_07"],
  "themes": ["暗恋", "青春", "遗憾"]
}
```

## 解析规则

1. **角色识别**：提取所有有名字或有意义的角色，包括别名
2. **场景识别**：识别所有场所，注意时间和天气
3. **节拍切分**：按"事件/动作"切分，不是按段落
   - 每个 beat 应该是一个可视化的单元
   - 预估每个 beat 4-8 秒
4. **原文对齐**：每个 beat 必须包含原文摘录 (source_quote)
5. **情绪标注**：用 "起始 → 结束" 格式描述情绪变化

## 重要

- 所有字段必须填写
- 角色/场景 ID 必须在 beats 中被引用
- source_quote 必须是原文片段，用于防止幻觉
"""
    
    def _build_script_ir(self, data: Dict, script_text: str) -> ScriptIR:
        """从 LLM 输出构建 ScriptIR"""
        import uuid
        
        # 解析角色
        characters = []
        for c in data.get("characters", []):
            relationships = []
            for r in c.get("relationships", []):
                relationships.append(CharacterRelationship(
                    target_id=r.get("target_id", ""),
                    relation_type=r.get("relation_type", ""),
                    description=r.get("description", "")
                ))
            
            characters.append(CharacterIR(
                id=c.get("id", f"char_{uuid.uuid4().hex[:8]}"),
                name=c.get("name", "未知角色"),
                aliases=c.get("aliases", []),
                gender=c.get("gender"),
                age_range=c.get("age_range"),
                appearance_keywords=c.get("appearance_keywords", []),
                personality_keywords=c.get("personality_keywords", []),
                relationships=relationships,
                importance=c.get("importance", "supporting")
            ))
        
        # 解析场景
        scenes = []
        for s in data.get("scenes", []):
            scenes.append(SceneIR(
                id=s.get("id", f"scene_{uuid.uuid4().hex[:8]}"),
                name=s.get("name", "未知场景"),
                location_type=s.get("location_type", "indoor"),
                time_period=s.get("time_period", "day"),
                weather=s.get("weather", "clear"),
                atmosphere_keywords=s.get("atmosphere_keywords", []),
                props=s.get("props", []),
                visual_description=s.get("visual_description", "")
            ))
        
        # 解析节拍
        beats = []
        for i, b in enumerate(data.get("beats", [])):
            beats.append(BeatIR(
                id=b.get("id", f"beat_{i:02d}"),
                index=i,
                who=b.get("who", []),
                where=b.get("where", ""),
                when=b.get("when", ""),
                what_happens=b.get("what_happens", ""),
                why_intent=b.get("why_intent", ""),
                emotion_shift=b.get("emotion_shift", "neutral → neutral"),
                source_quote=b.get("source_quote", ""),
                tension_level=b.get("tension_level", 5),
                pacing=b.get("pacing", "normal"),
                dialogue=b.get("dialogue"),
                suggested_duration=b.get("suggested_duration", 4.0),
                suggested_panel_count=b.get("suggested_panel_count", 1)
            ))
        
        return ScriptIR(
            script_hash=ScriptIR.compute_hash(script_text),
            characters=characters,
            scenes=scenes,
            beats=beats,
            total_duration_hint=data.get("total_duration_hint", 60.0),
            emotional_arc=data.get("emotional_arc", ""),
            key_moments=data.get("key_moments", []),
            themes=data.get("themes", [])
        )
    
    # ===== Task B: Plan =====
    
    async def task_plan(
        self, 
        script_ir: ScriptIR, 
        director: DirectorProfile
    ) -> PlanResult:
        """
        Task B: 导演计划
        
        输入：ScriptIR + DirectorProfile
        输出：StoryboardPlan
        """
        from app.services.brain.base import get_brain_service
        
        system_prompt = self._build_plan_prompt(director)
        user_prompt = f"""请根据以下剧本结构和导演约束，生成分镜计划。

## 剧本结构 (ScriptIR)

### 角色
{json.dumps([c.model_dump() for c in script_ir.characters], ensure_ascii=False, indent=2)}

### 场景
{json.dumps([s.model_dump() for s in script_ir.scenes], ensure_ascii=False, indent=2)}

### 剧情节拍
{json.dumps([b.model_dump() for b in script_ir.beats], ensure_ascii=False, indent=2)}

## 导演约束
{director.to_prompt_context()}

请为每个 beat 生成 1-2 个分镜，确保所有字段完整。
"""
        
        try:
            brain = get_brain_service()
            
            response = await brain._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format="json"
            )
            
            # 解析
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                data = json.loads(response)
            
            # 构建 StoryboardPlan
            plan = self._build_storyboard_plan(data, script_ir)
            
            # 验证
            issues = self._validate_plan(plan, script_ir, director)
            plan.validation_issues = issues
            plan.validation_score = max(0, 100 - len(issues) * 10)
            
            return PlanResult(
                success=True,
                plan=plan,
                warnings=issues
            )
            
        except Exception as e:
            logger.error(f"Task Plan failed: {e}")
            return PlanResult(success=False, errors=[str(e)])
    
    def _build_plan_prompt(self, director: DirectorProfile) -> str:
        """构建 Plan 阶段的系统提示词"""
        # 获取镜头规则
        shot_rules = "\n".join([
            f"- {r.emotion_trigger}: {r.recommended_shot.value} + {r.recommended_move.value} ({r.rationale})"
            for r in director.shot_grammar.emotion_shot_rules
        ])
        
        return f"""你是一位专业的漫画分镜导演。你的任务是将剧情节拍转化为分镜计划。

## 导演风格
{director.to_prompt_context()}

## 镜头语法规则
{shot_rules}

## 输出格式

返回 JSON 对象：

```json
{{
  "panels": [
    {{
      "panel_id": "panel_001",
      "beat_id": "beat_01",
      "panel_index": 0,
      
      "shot_type": "MS",
      "camera_move": "static",
      "camera_angle": "eye_level",
      "duration_sec": 3.5,
      "lens_hint": "50mm",
      
      "scene_id": "scene_01",
      "location": "旧书店内部",
      "time_of_day": "afternoon",
      "weather": "rainy",
      "mood": "温柔、怀旧",
      
      "cast": ["char_01"],
      "actions": "周昀站在书架旁，手指轻轻划过书脊，目光望向窗外的雨帘。他的眼神中带着一丝若有所思的神色，似乎在等待什么。窗外的雨声隐约可闻。",
      "dialogue": null,
      
      "composition_notes": "人物置于右三分之一处，窗户在左侧形成明暗对比",
      "continuity_notes": "保持书店昏黄灯光，雨天氛围",
      
      "source_beat_quote": "雨下得很轻，像有人把城市的喧嚣也一并..."
    }}
  ],
  "total_duration": 60.0,
  "director_notes": "整体节奏舒缓，强调情感细节"
}}
```

## 分镜规则

1. **每个 beat 生成 1-2 个 panel**
2. **actions 至少 50 字**，详细描述动作、表情、环境细节
3. **shot_type 必须符合情绪**：
   - 情绪高潮 → CU/ECU
   - 对话场景 → MS/MCU
   - 建立场景 → WS/LS
4. **duration_sec 范围**：{director.min_shot_duration} - {director.max_shot_duration} 秒
5. **source_beat_quote 必须填写**：来自对应 beat 的原文
"""
    
    def _build_storyboard_plan(self, data: Dict, script_ir: ScriptIR) -> StoryboardPlan:
        """构建 StoryboardPlan"""
        import uuid
        
        panels = []
        for i, p in enumerate(data.get("panels", [])):
            panels.append(PanelPlanSpec(
                panel_id=p.get("panel_id", f"panel_{i:03d}"),
                beat_id=p.get("beat_id", ""),
                panel_index=i,
                shot_type=p.get("shot_type", "MS"),
                camera_move=p.get("camera_move", "static"),
                camera_angle=p.get("camera_angle", "eye_level"),
                duration_sec=p.get("duration_sec", 3.0),
                lens_hint=p.get("lens_hint"),
                scene_id=p.get("scene_id", ""),
                location=p.get("location", ""),
                time_of_day=p.get("time_of_day", "day"),
                weather=p.get("weather", "clear"),
                mood=p.get("mood", ""),
                cast=p.get("cast", []),
                actions=p.get("actions", ""),
                dialogue=p.get("dialogue"),
                composition_notes=p.get("composition_notes", ""),
                continuity_notes=p.get("continuity_notes", ""),
                source_beat_quote=p.get("source_beat_quote", "")
            ))
        
        return StoryboardPlan(
            panels=panels,
            total_duration=data.get("total_duration", sum(p.duration_sec for p in panels)),
            director_notes=data.get("director_notes", "")
        )
    
    def _validate_plan(
        self, 
        plan: StoryboardPlan, 
        script_ir: ScriptIR,
        director: DirectorProfile
    ) -> List[str]:
        """验证分镜计划"""
        issues = []
        
        beat_ids = {b.id for b in script_ir.beats}
        scene_ids = {s.id for s in script_ir.scenes}
        char_ids = {c.id for c in script_ir.characters}
        
        for p in plan.panels:
            # 检查 beat 引用
            if p.beat_id and p.beat_id not in beat_ids:
                issues.append(f"Panel {p.panel_id}: 引用了未知的 beat {p.beat_id}")
            
            # 检查场景引用
            if p.scene_id and p.scene_id not in scene_ids:
                issues.append(f"Panel {p.panel_id}: 引用了未知的场景 {p.scene_id}")
            
            # 检查角色引用
            for cast_id in p.cast:
                if cast_id not in char_ids:
                    issues.append(f"Panel {p.panel_id}: 引用了未知的角色 {cast_id}")
            
            # 检查 actions 长度
            if len(p.actions) < 30:
                issues.append(f"Panel {p.panel_id}: actions 过短 ({len(p.actions)} 字)")
            
            # 检查 source_beat_quote
            if not p.source_beat_quote:
                issues.append(f"Panel {p.panel_id}: 缺少原文引用")
            
            # 检查时长范围
            if p.duration_sec < director.min_shot_duration or p.duration_sec > director.max_shot_duration:
                issues.append(f"Panel {p.panel_id}: 时长 {p.duration_sec}s 超出范围")
        
        return issues
    
    # ===== Task C: Bind =====
    
    async def task_bind(
        self, 
        plan: StoryboardPlan,
        assets_index: Dict[str, List[Dict]]
    ) -> BindResult:
        """
        Task C: 资产绑定建议
        
        输入：StoryboardPlan + 资产库索引
        输出：AssetsLockProposal
        """
        try:
            # 收集所有引用的角色和场景
            used_chars = set()
            used_scenes = set()
            
            for panel in plan.panels:
                used_chars.update(panel.cast)
                if panel.scene_id:
                    used_scenes.add(panel.scene_id)
            
            # 匹配角色
            char_matches = []
            for char_id in used_chars:
                match = self._match_asset(
                    char_id, "character",
                    assets_index.get("characters", [])
                )
                char_matches.append(match)
            
            # 匹配场景
            scene_matches = []
            for scene_id in used_scenes:
                match = self._match_asset(
                    scene_id, "scene",
                    assets_index.get("scenes", [])
                )
                scene_matches.append(match)
            
            # 收集缺失资产
            missing = []
            for m in char_matches + scene_matches:
                if m.match_status == "pending":
                    missing.append({
                        "type": m.ref_type,
                        "name": m.ref_name,
                        "description": m.suggested_asset_description or ""
                    })
            
            proposal = AssetsLockProposal(
                character_matches=char_matches,
                scene_matches=scene_matches,
                missing_assets=missing,
                all_resolved=len(missing) == 0,
                pending_count=len(missing)
            )
            
            return BindResult(success=True, proposal=proposal)
            
        except Exception as e:
            logger.error(f"Task Bind failed: {e}")
            return BindResult(success=False, errors=[str(e)])
    
    def _match_asset(
        self, 
        ref_id: str, 
        ref_type: str,
        assets: List[Dict]
    ) -> AssetMatch:
        """匹配资产"""
        ref_name = ref_id.replace("char_", "").replace("scene_", "")
        
        # 精确匹配
        for asset in assets:
            if asset.get("id") == ref_id:
                return AssetMatch(
                    ref_id=ref_id,
                    ref_name=ref_name,
                    ref_type=ref_type,
                    match_status="exact",
                    matched_asset_id=asset["id"],
                    matched_asset_name=asset.get("name", ""),
                    confidence=1.0,
                    match_reason="ID 精确匹配"
                )
        
        # 名称模糊匹配
        for asset in assets:
            asset_name = asset.get("name", "").lower()
            if ref_name.lower() in asset_name or asset_name in ref_name.lower():
                return AssetMatch(
                    ref_id=ref_id,
                    ref_name=ref_name,
                    ref_type=ref_type,
                    match_status="fuzzy",
                    matched_asset_id=asset["id"],
                    matched_asset_name=asset.get("name", ""),
                    confidence=0.7,
                    match_reason="名称部分匹配"
                )
        
        # 未匹配
        return AssetMatch(
            ref_id=ref_id,
            ref_name=ref_name,
            ref_type=ref_type,
            match_status="pending",
            confidence=0.0,
            match_reason="未找到匹配资产",
            suggested_asset_type=ref_type,
            suggested_asset_description=f"需要创建 {ref_type}: {ref_name}"
        )


# ============ 便捷函数 ============

def create_pipeline() -> ScriptPipelineService:
    """创建流水线实例"""
    return ScriptPipelineService()
