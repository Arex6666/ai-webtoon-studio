"""
AutoStoryboardOrchestrator - 全自动分镜编排器

实现流程:
1. LLM 解析剧本并结构化 (ScriptPipelineService.task_parse)
2. 并行处理:
   a) 角色链: 提取角色 → 入库 → (可选)生成定妆照 → FaceID Embedding → 绑定
   b) 场景链: 提取场景 → 入库 → (可选)生成BG → 控制图生成 → 绑定
3. 合并结果 → 生成 StoryboardPlan
"""
import asyncio
import logging
import uuid
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session

from app.schemas.automation import (
    AutomationConfig,
    AutomationResult,
    AutomationProgress,
    AutomationStage,
    CharacterChainResult,
    SceneChainResult,
)
from app.schemas.script_ir import ScriptIR, CharacterIR, SceneIR
from app.services.script_pipeline import (
    ScriptPipelineService,
    ParseResult,
    PlanResult,
    BindResult,
)
from app.schemas.director_profile import (
    get_default_director,
    get_romance_director,
    get_thriller_director,
    get_contemplative_director,
)
from app.models.asset import Asset
from app.services.identity import get_face_extractor, get_embedding_storage
from app.services.scene_anchor import get_control_map_generator, get_anchor_storage
from app.services.asset_image_generator import get_asset_image_generator

logger = logging.getLogger(__name__)


class AutoStoryboardOrchestrator:
    """
    全自动分镜编排器
    
    将剧本自动转化为分镜计划，同时自动处理角色和场景的资产入库。
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.pipeline = ScriptPipelineService()
        self._progress_callbacks: List[callable] = []
    
    def on_progress(self, callback: callable):
        """注册进度回调"""
        self._progress_callbacks.append(callback)
    
    def _emit_progress(self, progress: AutomationProgress):
        """发送进度更新"""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    async def run_full_automation(
        self,
        chapter_id: str,
        script_text: str,
        config: Optional[AutomationConfig] = None,
    ) -> AutomationResult:
        """
        运行完整的自动化流程
        
        Args:
            chapter_id: 章节 ID
            script_text: 剧本文本
            config: 自动化配置
            
        Returns:
            AutomationResult
        """
        config = config or AutomationConfig()
        result = AutomationResult(
            success=False,
            chapter_id=chapter_id,
        )
        
        try:
            # ========== 阶段 1: Parse ==========
            result.progress.stage = AutomationStage.PARSING
            result.progress.current_task = "正在解析剧本..."
            result.progress.progress = 5.0
            self._emit_progress(result.progress)
            
            parse_result = await self.pipeline.task_parse(script_text)
            
            if not parse_result.success:
                result.errors.extend(parse_result.errors)
                result.progress.stage = AutomationStage.FAILED
                return result
            
            script_ir = parse_result.script_ir
            result.warnings.extend(parse_result.warnings)
            
            # 设置计数
            result.progress.total_characters = len(script_ir.characters)
            result.progress.total_scenes = len(script_ir.scenes)
            result.progress.progress = 15.0
            self._emit_progress(result.progress)
            
            logger.info(
                f"Parse 完成: {len(script_ir.characters)} 角色, "
                f"{len(script_ir.scenes)} 场景, {len(script_ir.beats)} beats"
            )
            
            # ========== 阶段 2: 并行处理角色链和场景链 ==========
            character_task = self._process_character_chain(
                script_ir.characters,
                config,
                result.progress,
            )
            scene_task = self._process_scene_chain(
                script_ir.scenes,
                config,
                result.progress,
            )
            
            # 并发执行两个链
            char_results, scene_results = await asyncio.gather(
                character_task,
                scene_task,
                return_exceptions=True,
            )
            
            # 处理角色链结果
            if isinstance(char_results, Exception):
                result.errors.append(f"角色处理链失败: {char_results}")
                char_results = []
            result.characters = char_results
            
            # 处理场景链结果
            if isinstance(scene_results, Exception):
                result.errors.append(f"场景处理链失败: {scene_results}")
                scene_results = []
            result.scenes = scene_results
            
            # 统计
            result.assets_created = sum(
                1 for c in result.characters if c.asset_created
            ) + sum(
                1 for s in result.scenes if s.asset_created
            )
            result.embeddings_extracted = sum(
                1 for c in result.characters if c.embedding_extracted
            )
            result.control_maps_generated = sum(
                len(s.control_maps) for s in result.scenes
            )
            
            # ========== 阶段 3: 资产绑定 ==========
            result.progress.stage = AutomationStage.BINDING
            result.progress.current_task = "绑定资产..."
            result.progress.progress = 80.0
            self._emit_progress(result.progress)
            
            # 构建资产索引
            assets_index = self._build_assets_index(result.characters, result.scenes)
            
            # ========== 阶段 4: 生成 Plan ==========
            result.progress.stage = AutomationStage.PLANNING
            result.progress.current_task = "生成分镜计划..."
            result.progress.progress = 85.0
            self._emit_progress(result.progress)
            
            director = self._get_director(config.director_preset)
            plan_result = await self.pipeline.task_plan(script_ir, director)
            
            if not plan_result.success:
                result.errors.extend(plan_result.errors)
                result.warnings.extend(plan_result.warnings)
                # 即使 plan 失败，角色和场景处理可能仍然成功
                result.progress.stage = AutomationStage.FAILED
                return result
            
            result.warnings.extend(plan_result.warnings)
            
            # ========== 阶段 5: Bind + 保存 ==========
            bind_result = await self.pipeline.task_bind(plan_result.plan, assets_index)
            
            if bind_result.success:
                result.progress.progress = 95.0
                self._emit_progress(result.progress)
                
                # 保存 Draft
                draft_id = await self._save_draft(
                    chapter_id,
                    script_ir,
                    plan_result.plan,
                    bind_result.proposal,
                )
                result.draft_id = draft_id
                result.storyboard_plan_id = draft_id
            
            # ========== 完成 ==========
            result.success = len(result.errors) == 0
            result.progress.stage = AutomationStage.COMPLETED
            result.progress.progress = 100.0
            result.progress.current_task = "完成"
            self._emit_progress(result.progress)
            
            logger.info(
                f"自动化完成: {result.assets_created} 资产创建, "
                f"{result.embeddings_extracted} embedding, "
                f"{result.control_maps_generated} 控制图"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"自动化失败: {e}", exc_info=True)
            result.errors.append(str(e))
            result.progress.stage = AutomationStage.FAILED
            return result
    
    async def _process_character_chain(
        self,
        characters: List[CharacterIR],
        config: AutomationConfig,
        progress: AutomationProgress,
    ) -> List[CharacterChainResult]:
        """
        处理角色链
        
        流程:
        1. 查找或创建角色资产
        2. (可选) 生成定妆照
        3. 提取 FaceID Embedding
        4. 绑定
        """
        progress.stage = AutomationStage.CHARACTER_CHAIN
        results = []
        
        for i, char in enumerate(characters):
            progress.current_task = f"处理角色: {char.name}"
            progress.processed_characters = i
            # 进度: 15% - 50% 给角色链
            progress.progress = 15.0 + (35.0 * (i + 1) / max(len(characters), 1))
            self._emit_progress(progress)
            
            result = CharacterChainResult(
                character_id=str(uuid.uuid4()),
                ref_id=char.id,
                name=char.name,
                aliases=char.aliases,
            )
            
            try:
                # 1. 查找或创建资产
                asset = await self._find_or_create_character_asset(
                    char,
                    config.auto_create_assets,
                )
                
                if asset:
                    result.asset_id = asset.id
                    result.asset_existed = not result.asset_created
                    
                    # 2. 提取 Embedding (如果有图片)
                    if config.auto_extract_embeddings:
                        embedding_result = await self._extract_character_embedding(
                            asset=asset,
                            auto_generate=config.auto_generate_portraits,
                            character=char,
                            project_id=None,  # TODO: 获取 project_id
                        )
                        result.embedding_extracted = embedding_result.get("success", False)
                        result.embedding_path = embedding_result.get("path")
                        result.embedding_source_count = embedding_result.get("source_count", 0)
                        
                        if embedding_result.get("error"):
                            result.errors.append(embedding_result["error"])
                else:
                    result.errors.append(f"未能创建角色资产: {char.name}")
                    
            except Exception as e:
                logger.error(f"处理角色 {char.name} 失败: {e}")
                result.errors.append(str(e))
            
            results.append(result)
        
        progress.processed_characters = len(characters)
        return results
    
    async def _process_scene_chain(
        self,
        scenes: List[SceneIR],
        config: AutomationConfig,
        progress: AutomationProgress,
    ) -> List[SceneChainResult]:
        """
        处理场景链
        
        流程:
        1. 查找或创建场景资产
        2. (可选) 生成空镜背景
        3. 生成控制图 (Depth/Canny/Lineart)
        4. 绑定
        """
        results = []
        
        for i, scene in enumerate(scenes):
            progress.current_task = f"处理场景: {scene.name}"
            progress.processed_scenes = i
            # 进度: scene chain 与 character chain 并行，但我们在这里也更新
            self._emit_progress(progress)
            
            result = SceneChainResult(
                scene_id=str(uuid.uuid4()),
                ref_id=scene.id,
                name=scene.name,
                location_type=scene.location_type,
            )
            
            try:
                # 1. 查找或创建资产
                asset = await self._find_or_create_scene_asset(
                    scene,
                    config.auto_create_assets,
                )
                
                if asset:
                    result.asset_id = asset.id
                    result.asset_existed = not result.asset_created
                    
                    # 2. 生成控制图 (如果有 anchor 图片)
                    if config.auto_generate_control_maps:
                        maps_result = await self._generate_scene_control_maps(
                            asset=asset,
                            auto_generate=config.auto_generate_backgrounds,
                            scene=scene,
                            project_id=None,  # TODO: 获取 project_id
                        )
                        result.anchor_generated = maps_result.get("success", False)
                        result.anchor_path = maps_result.get("anchor_path")
                        result.control_maps = maps_result.get("control_maps", {})
                        
                        if maps_result.get("error"):
                            result.errors.append(maps_result["error"])
                else:
                    result.errors.append(f"未能创建场景资产: {scene.name}")
                    
            except Exception as e:
                logger.error(f"处理场景 {scene.name} 失败: {e}")
                result.errors.append(str(e))
            
            results.append(result)
        
        progress.processed_scenes = len(scenes)
        return results
    
    async def _find_or_create_character_asset(
        self,
        char: CharacterIR,
        auto_create: bool,
    ) -> Optional[Asset]:
        """查找或创建角色资产"""
        # 先尝试查找
        asset = self.db.query(Asset).filter(
            Asset.asset_type == "character",
            Asset.name.ilike(f"%{char.name}%"),
        ).first()
        
        if asset:
            logger.info(f"找到现有角色资产: {asset.name}")
            return asset
        
        # 尝试按别名查找
        for alias in char.aliases:
            asset = self.db.query(Asset).filter(
                Asset.asset_type == "character",
                Asset.name.ilike(f"%{alias}%"),
            ).first()
            if asset:
                logger.info(f"通过别名找到角色资产: {asset.name}")
                return asset
        
        # 创建新资产
        if auto_create:
            asset = Asset(
                id=str(uuid.uuid4()),
                name=char.name,
                asset_type="character",
                tags=char.appearance_keywords + char.personality_keywords,
                metadata_json={
                    "aliases": char.aliases,
                    "gender": char.gender,
                    "age_range": char.age_range,
                    "importance": char.importance,
                    "script_ref_id": char.id,
                    "auto_created": True,
                },
            )
            self.db.add(asset)
            self.db.commit()
            logger.info(f"创建新角色资产: {char.name}")
            return asset
        
        return None
    
    async def _find_or_create_scene_asset(
        self,
        scene: SceneIR,
        auto_create: bool,
    ) -> Optional[Asset]:
        """查找或创建场景资产"""
        # 先尝试查找
        asset = self.db.query(Asset).filter(
            Asset.asset_type == "scene",
            Asset.name.ilike(f"%{scene.name}%"),
        ).first()
        
        if asset:
            logger.info(f"找到现有场景资产: {asset.name}")
            return asset
        
        # 创建新资产
        if auto_create:
            asset = Asset(
                id=str(uuid.uuid4()),
                name=scene.name,
                asset_type="scene",
                tags=scene.atmosphere_keywords,
                metadata_json={
                    "location_type": scene.location_type,
                    "time_period": scene.time_period,
                    "weather": scene.weather,
                    "props": scene.props,
                    "visual_description": scene.visual_description,
                    "script_ref_id": scene.id,
                    "auto_created": True,
                },
            )
            self.db.add(asset)
            self.db.commit()
            logger.info(f"创建新场景资产: {scene.name}")
            return asset
        
        return None
    
    async def _extract_character_embedding(
        self,
        asset: Asset,
        auto_generate: bool,
        character: CharacterIR = None,
        project_id: str = None,
    ) -> Dict[str, Any]:
        """提取角色 FaceID Embedding"""
        result = {
            "success": False,
            "path": None,
            "source_count": 0,
            "portrait_url": None,
            "error": None,
        }
        
        try:
            storage = get_embedding_storage()
            
            # 检查是否已有 embedding
            existing = storage.get_embedding(asset.id)
            if existing is not None:
                result["success"] = True
                result["path"] = storage.get_embedding_path(asset.id)
                result["source_count"] = existing.get("source_count", 1)
                logger.info(f"角色 {asset.name} 已有 embedding")
                return result
            
            # 检查是否有定妆照
            portrait_path = asset.metadata_json.get("portrait_path") if asset.metadata_json else None
            
            if not portrait_path:
                # 自动生成定妆照
                if auto_generate and character:
                    logger.info(f"为角色 {asset.name} 自动生成定妆照...")
                    generator = get_asset_image_generator()
                    gen_result = await generator.generate_character_portrait(
                        character=character,
                        asset=asset,
                        project_id=project_id or "default",
                    )
                    
                    if gen_result["success"]:
                        result["success"] = True
                        result["path"] = gen_result.get("embedding_path")
                        result["portrait_url"] = gen_result.get("image_url")
                        result["source_count"] = 1
                        
                        # 更新 asset 元数据
                        if asset.metadata_json is None:
                            asset.metadata_json = {}
                        asset.metadata_json["portrait_path"] = gen_result.get("image_url")
                        asset.metadata_json["portrait_auto_generated"] = True
                        self.db.commit()
                        
                        logger.info(f"角色 {asset.name} 定妆照生成成功")
                        return result
                    else:
                        result["error"] = gen_result.get("error") or "定妆照生成失败"
                else:
                    result["error"] = f"角色 {asset.name} 缺少定妆照，请手动上传或启用自动生成"
                return result
            
            # 使用已有定妆照提取 embedding
            logger.info(f"使用已有定妆照为角色 {asset.name} 提取 embedding")
            result["error"] = "使用已有定妆照提取 embedding (需要实现)"  # TODO: 从存储读取图片
            
        except Exception as e:
            logger.error(f"提取 embedding 失败: {e}")
            result["error"] = str(e)
        
        return result
    
    async def _generate_scene_control_maps(
        self,
        asset: Asset,
        auto_generate: bool,
        scene: SceneIR = None,
        project_id: str = None,
    ) -> Dict[str, Any]:
        """生成场景控制图"""
        result = {
            "success": False,
            "anchor_path": None,
            "control_maps": {},
            "error": None,
        }
        
        try:
            storage = get_anchor_storage()
            
            # 检查是否已有控制图
            existing = storage.get_anchor_info(asset.id)
            if existing:
                result["success"] = True
                result["anchor_path"] = existing.get("anchor_path")
                result["control_maps"] = existing.get("control_maps", {})
                logger.info(f"场景 {asset.name} 已有控制图")
                return result
            
            # 检查是否有空镜图
            anchor_path = asset.metadata_json.get("anchor_path") if asset.metadata_json else None
            
            if not anchor_path:
                # 自动生成空镜图
                if auto_generate and scene:
                    logger.info(f"为场景 {asset.name} 自动生成空镜图...")
                    generator = get_asset_image_generator()
                    gen_result = await generator.generate_scene_background(
                        scene=scene,
                        asset=asset,
                        project_id=project_id or "default",
                    )
                    
                    if gen_result["success"]:
                        result["success"] = True
                        result["anchor_path"] = gen_result.get("image_url")
                        result["control_maps"] = gen_result.get("control_maps", {})
                        
                        # 更新 asset 元数据
                        if asset.metadata_json is None:
                            asset.metadata_json = {}
                        asset.metadata_json["anchor_path"] = gen_result.get("image_url")
                        asset.metadata_json["anchor_auto_generated"] = True
                        self.db.commit()
                        
                        logger.info(f"场景 {asset.name} 空镜图生成成功")
                        return result
                    else:
                        result["error"] = gen_result.get("error") or "空镜图生成失败"
                else:
                    result["error"] = f"场景 {asset.name} 缺少空镜图，请手动上传或启用自动生成"
                return result
            
            # 使用已有空镜图生成控制图
            logger.info(f"使用已有空镜图为场景 {asset.name} 生成控制图")
            result["error"] = "使用已有空镜图生成控制图 (需要实现)"  # TODO: 从存储读取图片
            
        except Exception as e:
            logger.error(f"生成控制图失败: {e}")
            result["error"] = str(e)
        
        return result
    
    def _build_assets_index(
        self,
        characters: List[CharacterChainResult],
        scenes: List[SceneChainResult],
    ) -> Dict[str, List[Dict]]:
        """构建资产索引供 Bind 使用"""
        return {
            "characters": [
                {
                    "id": c.ref_id,
                    "name": c.name,
                    "asset_id": c.asset_id,
                    "embedding_path": c.embedding_path,
                }
                for c in characters if c.asset_id
            ],
            "scenes": [
                {
                    "id": s.ref_id,
                    "name": s.name,
                    "asset_id": s.asset_id,
                    "anchor_path": s.anchor_path,
                    "control_maps": s.control_maps,
                }
                for s in scenes if s.asset_id
            ],
        }
    
    def _get_director(self, preset: str):
        """获取导演配置"""
        directors = {
            "default": get_default_director,
            "romance": get_romance_director,
            "thriller": get_thriller_director,
            "contemplative": get_contemplative_director,
        }
        return directors.get(preset, get_default_director)()
    
    async def _save_draft(
        self,
        chapter_id: str,
        script_ir: ScriptIR,
        plan,
        bind_proposal,
    ) -> Optional[str]:
        """保存为 Draft"""
        from app.models.storyboard_draft import StoryboardDraft
        
        try:
            draft_id = str(uuid.uuid4())
            draft = StoryboardDraft(
                id=draft_id,
                chapter_id=chapter_id,
                status="auto_generated",
                analysis_json=script_ir.model_dump() if script_ir else {},
                storyboard_json=plan.model_dump() if plan else {},
                metadata_json={
                    "bind_proposal": bind_proposal.model_dump() if bind_proposal else {},
                    "auto_generated": True,
                },
            )
            self.db.add(draft)
            self.db.commit()
            logger.info(f"保存 Draft: {draft_id}")
            return draft_id
        except Exception as e:
            logger.error(f"保存 Draft 失败: {e}")
            return None


# ============ 便捷函数 ============

def create_orchestrator(db: Session) -> AutoStoryboardOrchestrator:
    """创建编排器实例"""
    return AutoStoryboardOrchestrator(db)
