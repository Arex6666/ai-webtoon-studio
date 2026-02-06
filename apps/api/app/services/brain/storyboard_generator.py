"""
Storyboard Generator - 两段式 LLM 生成器

实现 run_storyboard_task：
1. 第一阶段：剧本 → ScriptAnalysisV1
2. 第二阶段：分析 + 资产 + 风格 → StoryboardDraftV2

S4-01-03: 集成 Repair Loop 自动修复
"""
import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from pydantic import ValidationError

from .prompt_contract import (
    PromptContract, PromptMeta, PromptConstraints, StyleProfile,
    get_default_style, get_style_by_name
)
from .prompt_composer import PromptComposer
from .digests import digest_text, digest_assets, get_enum_digest
from .repair import (
    validate_and_repair_analysis,
    validate_and_repair_storyboard,
    RepairPlan
)

logger = logging.getLogger(__name__)


class StoryboardGenerator:
    """
    分镜生成器
    
    两段式生成：
    1. parse_script → ScriptAnalysisV1
    2. generate_storyboard → StoryboardDraftV2
    """
    
    def __init__(self, llm_service=None):
        """
        Args:
            llm_service: LLM 服务实例
        """
        self.llm = llm_service
        
    async def run_full_generation(
        self,
        chapter_id: str,
        script_text: str,
        style_profile: Optional[StyleProfile] = None,
        assets_context: Optional[Dict[str, Any]] = None,
        constraints: Optional[PromptConstraints] = None,
        prompt_version: str = "pc_v1",
        max_repair_attempts: int = 3,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        运行完整的两段式生成 (含自动修复)
        
        Returns:
            (analysis_result, storyboard_result, metadata)
        """
        style = style_profile or get_default_style()
        constr = constraints or PromptConstraints()
        
        # 创建 Composer
        composer = PromptComposer(
            script_text=script_text,
            style_profile=style,
            assets_context=assets_context,
            constraints=constr,
            prompt_version=prompt_version,
            chapter_id=chapter_id,
        )
        
        metadata = {
            "prompt_version": prompt_version,
            "script_digest": composer.script_digest,
            "assets_digest": composer.assets_digest,
            "enum_digest": composer.enum_digest,
            "style_profile": style.model_dump() if style else None,
            "constraints": constr.model_dump(),
        }
        
        # === 第一阶段：剧本分析 ===
        logger.info(f"[Storyboard] Phase 1: Script Analysis for chapter {chapter_id}")
        
        analysis_contract = composer.compose_analysis_contract()
        analysis_result = await self._call_llm(analysis_contract)
        
        if not analysis_result.get("success"):
            return (
                {"success": False, "error": analysis_result.get("error", "Analysis failed")},
                {"success": False, "error": "Skipped due to analysis failure"},
                metadata
            )
        
        analysis_json = analysis_result.get("data", {})
        
        # S4-01-03: 使用 Repair Loop 验证和修复分析结果
        logger.info(f"[Storyboard] Phase 1.5: Validating and repairing analysis...")
        analysis_ok, analysis_model_or_data, analysis_plan = await validate_and_repair_analysis(
            data=analysis_json,
            script_text=script_text,
            max_attempts=max_repair_attempts
        )
        
        metadata["analysis_schema_version"] = analysis_json.get("schema_version")
        metadata["analysis_attempts_used"] = analysis_plan.attempts_used
        metadata["analysis_final_status"] = analysis_plan.final_status
        
        if not analysis_ok:
            logger.warning(f"[Storyboard] Analysis validation failed after {analysis_plan.attempts_used} attempts")
            analysis_result["validation_issues"] = [i.model_dump() for i in analysis_plan.issues]
            analysis_result["repair_status"] = "failed"
            # 继续使用最后的 JSON，但标记为 needs_fix
            analysis_json = analysis_plan.repaired_json or analysis_json
        else:
            analysis_result["repair_status"] = analysis_plan.final_status
            if hasattr(analysis_model_or_data, 'model_dump'):
                analysis_json = analysis_model_or_data.model_dump()
            elif isinstance(analysis_model_or_data, dict):
                analysis_json = analysis_model_or_data
        
        # === 第二阶段：分镜生成 ===
        logger.info(f"[Storyboard] Phase 2: Storyboard Generation for chapter {chapter_id}")
        
        storyboard_contract = composer.compose_storyboard_contract(analysis_json)
        storyboard_result = await self._call_llm(storyboard_contract)
        
        if not storyboard_result.get("success"):
            return (
                analysis_result,
                {"success": False, "error": storyboard_result.get("error", "Storyboard failed")},
                metadata
            )
        
        storyboard_json = storyboard_result.get("data", {})
        
        # S4-01-03: 使用 Repair Loop 验证和修复分镜结果
        logger.info(f"[Storyboard] Phase 2.5: Validating and repairing storyboard...")
        duration_range = (constr.per_panel_duration_s_min, constr.per_panel_duration_s_max)
        storyboard_ok, storyboard_model_or_data, storyboard_plan = await validate_and_repair_storyboard(
            data=storyboard_json,
            script_text=script_text,
            duration_range=duration_range,
            max_attempts=max_repair_attempts
        )
        
        metadata["storyboard_schema_version"] = storyboard_json.get("schema_version")
        metadata["storyboard_attempts_used"] = storyboard_plan.attempts_used
        metadata["storyboard_final_status"] = storyboard_plan.final_status
        
        if not storyboard_ok:
            logger.warning(f"[Storyboard] Storyboard validation failed after {storyboard_plan.attempts_used} attempts")
            storyboard_result["validation_issues"] = [i.model_dump() for i in storyboard_plan.issues]
            storyboard_result["repair_status"] = "failed"
            storyboard_result["needs_fix"] = True
            # 继续使用最后的 JSON
            storyboard_json = storyboard_plan.repaired_json or storyboard_json
        else:
            storyboard_result["repair_status"] = storyboard_plan.final_status
            if hasattr(storyboard_model_or_data, 'model_dump'):
                storyboard_json = storyboard_model_or_data.model_dump()
            elif isinstance(storyboard_model_or_data, dict):
                storyboard_json = storyboard_model_or_data
        
        # 更新结果中的 data
        analysis_result["data"] = analysis_json
        storyboard_result["data"] = storyboard_json
        
        return analysis_result, storyboard_result, metadata
    
    async def _call_llm(self, contract: PromptContract) -> Dict[str, Any]:
        """调用 LLM"""
        from .base import get_brain_service
        
        try:
            brain = get_brain_service()
            messages = contract.to_messages()
            
            response = await brain._chat_completion(
                messages=messages,
                response_format="json"
            )
            
            # 解析 JSON
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                # 尝试清理
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0]
                data = json.loads(response.strip())
            
            return {
                "success": True,
                "data": data,
                "raw_response": response[:1000] if len(response) > 1000 else response,
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"[Storyboard] JSON parse error: {e}")
            return {"success": False, "error": f"JSON parse error: {e}"}
        except Exception as e:
            logger.error(f"[Storyboard] LLM call error: {e}")
            return {"success": False, "error": str(e)}
    
    def _validate_analysis(self, data: Dict[str, Any]) -> Tuple[bool, list]:
        """验证 ScriptAnalysisV1"""
        errors = []
        
        # 检查 schema_version
        if data.get("schema_version") != "script_analysis_v1":
            errors.append("schema_version 必须是 'script_analysis_v1'")
        
        # 检查角色
        characters = data.get("characters", [])
        if not characters:
            errors.append("characters 不能为空")
        
        for i, char in enumerate(characters):
            if len(char.get("appearance_traits", [])) < 2:
                errors.append(f"角色 {i}: appearance_traits 少于 2 个")
            if len(char.get("personality_traits", [])) < 2:
                errors.append(f"角色 {i}: personality_traits 少于 2 个")
            if not char.get("first_appearance_span", {}).get("quote"):
                errors.append(f"角色 {i}: 缺少 first_appearance_span.quote")
        
        # 检查地点
        locations = data.get("locations", [])
        if not locations:
            errors.append("locations 不能为空")
        
        for i, loc in enumerate(locations):
            if not loc.get("first_appearance_span", {}).get("quote"):
                errors.append(f"地点 {i}: 缺少 first_appearance_span.quote")
        
        # 检查节拍
        beats = data.get("beats", [])
        if not beats:
            errors.append("beats 不能为空")
        
        for i, beat in enumerate(beats):
            if not beat.get("source_span", {}).get("quote"):
                errors.append(f"节拍 {i}: 缺少 source_span.quote")
        
        return len(errors) == 0, errors
    
    def _validate_storyboard(self, data: Dict[str, Any]) -> Tuple[bool, list]:
        """验证 StoryboardDraftV2"""
        errors = []
        
        # 检查 schema_version
        if data.get("schema_version") != "storyboard_draft_v2":
            errors.append("schema_version 必须是 'storyboard_draft_v2'")
        
        # 检查 panels
        panels = data.get("panels", [])
        if not panels:
            errors.append("panels 不能为空")
        
        valid_shot_types = ["ECU", "CU", "MS", "LS", "WS", "OTS"]
        valid_camera_moves = ["static", "pan", "tilt", "dolly_in", "dolly_out", "zoom_in", "zoom_out", "handheld"]
        valid_time_of_day = ["day", "night", "dawn", "dusk"]
        valid_weather = ["clear", "rainy", "cloudy", "foggy", "snowy"]
        
        for i, panel in enumerate(panels):
            idx = panel.get("index", i + 1)
            
            # 枚举检查
            if panel.get("shot_type") not in valid_shot_types:
                errors.append(f"Panel {idx}: shot_type 无效")
            if panel.get("camera_move") not in valid_camera_moves:
                errors.append(f"Panel {idx}: camera_move 无效")
            if panel.get("time_of_day") not in valid_time_of_day:
                errors.append(f"Panel {idx}: time_of_day 无效")
            if panel.get("weather") not in valid_weather:
                errors.append(f"Panel {idx}: weather 无效")
            
            # 硬约束检查
            comp_notes = panel.get("composition_notes", [])
            if len(comp_notes) < 2:
                errors.append(f"Panel {idx}: composition_notes 少于 2 条")
            
            cont_notes = panel.get("continuity_notes", [])
            if len(cont_notes) < 1:
                errors.append(f"Panel {idx}: continuity_notes 为空")
            
            if not panel.get("source_span", {}).get("quote"):
                errors.append(f"Panel {idx}: 缺少 source_span.quote")
            
            duration = panel.get("duration_s", 0)
            if duration < 1.5 or duration > 8.0:
                errors.append(f"Panel {idx}: duration_s ({duration}) 超出范围")
            
            visual_prompt = panel.get("visual_prompt", "")
            if len(visual_prompt) < 20:
                errors.append(f"Panel {idx}: visual_prompt 少于 20 字")
        
        return len(errors) == 0, errors


# ============ 便捷函数 ============

async def run_storyboard_task(
    chapter_id: str,
    script_text: str,
    style_preset: str = "default",
    constraints: Optional[Dict[str, Any]] = None,
    assets_context: Optional[Dict[str, Any]] = None,
    save_to_db: bool = True,
    db_session=None,
) -> Dict[str, Any]:
    """
    运行分镜生成任务
    
    Args:
        chapter_id: 章节 ID
        script_text: 剧本文本
        style_preset: 风格预设名称
        constraints: 生成约束
        assets_context: 资产上下文
        save_to_db: 是否保存到数据库
        db_session: 数据库会话
    
    Returns:
        生成结果
    """
    style = get_style_by_name(style_preset)
    
    constr = None
    if constraints:
        constr = PromptConstraints(**constraints)
    
    generator = StoryboardGenerator()
    analysis_result, storyboard_result, metadata = await generator.run_full_generation(
        chapter_id=chapter_id,
        script_text=script_text,
        style_profile=style,
        assets_context=assets_context,
        constraints=constr,
    )
    
    result = {
        "success": analysis_result.get("success") and storyboard_result.get("success"),
        "analysis": analysis_result,
        "storyboard": storyboard_result,
        "metadata": metadata,
    }
    
    # 保存到数据库
    if save_to_db and db_session and result["success"]:
        draft_id = await _save_draft_to_db(
            db_session,
            chapter_id,
            analysis_result.get("data"),
            storyboard_result.get("data"),
            metadata,
        )
        result["draft_id"] = draft_id
    
    return result


async def _save_draft_to_db(
    db,
    chapter_id: str,
    analysis_json: Dict[str, Any],
    storyboard_json: Dict[str, Any],
    metadata: Dict[str, Any],
) -> str:
    """保存生成结果到数据库"""
    from app.models.storyboard_draft import StoryboardDraft
    from app.models.chapter import Chapter
    import uuid
    
    draft_id = str(uuid.uuid4())
    
    # 转换 panels 格式
    panels_json = []
    for p in storyboard_json.get("panels", []):
        panels_json.append({
            "panel_id": f"panel_{p.get('index', 0):03d}",
            "order": p.get("index", 0),
            "title": f"分镜 {p.get('index', 0)}",
            "description": p.get("actions", ""),
            "action_description": p.get("actions", ""),
            "shot": {
                "shotType": p.get("shot_type"),
                "cameraMove": p.get("camera_move") or "static",  # P0-SHOT-FIX-01: 默认 static
                "durationSec": p.get("duration_s"),
                "lensHint": p.get("lens_hint"),
            },
            "camera": {
                "angle": p.get("camera_height", "eye"),
                "move": p.get("camera_move"),
            },
            "scene": {
                "location": p.get("location"),
                "timeOfDay": p.get("time_of_day"),
                "weather": p.get("weather"),
                "mood": p.get("mood"),
            },
            "characters": [{"character_id": c, "name": c} for c in p.get("cast", [])],
            "dialogue": [{"text": d} for d in p.get("dialogue_lines", [])],
            "composition_notes": p.get("composition_notes", []),
            "continuity_notes": p.get("continuity_notes", []),
            "visual_prompt": p.get("visual_prompt", ""),
            "source_span": p.get("source_span", {}),
        })
    
    # 提取角色和场景
    characters_json = analysis_json.get("characters", [])
    scenes_json = analysis_json.get("locations", [])
    
    draft = StoryboardDraft(
        id=draft_id,
        chapter_id=chapter_id,
        status="pending",
        panels_json=panels_json,
        characters_json=characters_json,
        scenes_json=scenes_json,
        generated_panels_count=len(panels_json),
        generated_characters_count=len(characters_json),
        generated_scenes_count=len(scenes_json),
        # S4-01: 版本追溯
        schema_version=storyboard_json.get("schema_version", "storyboard_draft_v2"),
        prompt_version=metadata.get("prompt_version", "pc_v1"),
        script_digest=metadata.get("script_digest"),
        analysis_digest=metadata.get("enum_digest"),  # 临时用 enum_digest
    )
    
    db.add(draft)
    
    # 更新 chapter 的 pending_draft_id
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if chapter:
        layout = chapter.layout_json or {}
        layout["pending_draft_id"] = draft_id
        chapter.layout_json = layout
    
    db.commit()
    
    return draft_id
