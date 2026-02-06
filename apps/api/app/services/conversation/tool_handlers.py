"""
ToolHandlers - 工具处理函数
为 ToolRegistry 中的工具提供实际的处理逻辑
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models import Panel, Asset
from app.models.asset import AssetType

logger = logging.getLogger(__name__)


class ToolHandlers:
    """工具处理函数集合"""

    def __init__(self, db: Session):
        self.db = db
        self._script_service = None
        self._qa_service = None

    @property
    def script_service(self):
        """懒加载脚本服务"""
        if self._script_service is None:
            from app.services.script.script_pipeline_service import ScriptPipelineService
            self._script_service = ScriptPipelineService(self.db)
        return self._script_service

    @property
    def qa_service(self):
        """懒加载QA服务"""
        if self._qa_service is None:
            from app.services.qa.draft_qa import DraftQA
            self._qa_service = DraftQA(self.db)
        return self._qa_service

    # ===== 剧本相关工具 =====

    async def generate_storyboard(
        self,
        story: str,
        panel_count: int = 4,
        style: Optional[str] = None,
        project_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成分镜
        
        Args:
            story: 故事描述/剧本
            panel_count: 分镜数量
            style: 风格提示
            project_id: 项目ID
            chapter_id: 章节ID
            
        Returns:
            生成结果
        """
        try:
            logger.info(f"Generating storyboard with {panel_count} panels")
            
            # 调用脚本解析服务
            from app.services.brain.standard_llm import StandardLLMService
            llm = StandardLLMService()
            
            parse_result = await llm.parse_script(
                script_text=story,
                style_hint=style or "korean_webtoon"
            )
            
            # 限制分镜数量
            panels = parse_result.panels[:panel_count] if parse_result.panels else []
            
            # 构建返回结果
            storyboard_data = {
                "panels": [
                    {
                        "panel_index": p.panel_index,
                        "action_description": p.action_description,
                        "dialogue": p.dialogue,
                        "shot_type": p.shot_type,
                        "camera_angle": p.camera_angle,
                        "emotion": p.emotion,
                        "characters": p.characters,
                        "scene_ref": p.scene_ref,
                    }
                    for p in panels
                ],
                "detected_characters": parse_result.detected_characters,
                "detected_scenes": parse_result.detected_scenes,
                "detected_props": parse_result.detected_props,
                "total_panels": len(panels),
            }
            
            logger.info(f"Generated {len(panels)} panels, detected {len(parse_result.detected_characters)} characters")
            
            return {
                "success": True,
                "storyboard": storyboard_data,
                "message": f"成功生成 {len(panels)} 格分镜",
            }
            
        except Exception as e:
            logger.error(f"Storyboard generation failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    async def refine_script(
        self,
        script_id: str,
        feedback: str,
    ) -> Dict[str, Any]:
        """
        根据反馈优化剧本
        
        Args:
            script_id: 剧本/章节ID
            feedback: 反馈内容
            
        Returns:
            优化结果
        """
        try:
            logger.info(f"Refining script {script_id} with feedback")
            
            # TODO: 实现剧本优化逻辑
            # 目前返回占位结果
            return {
                "success": True,
                "message": f"已收到反馈，正在优化剧本...",
                "script_id": script_id,
            }
            
        except Exception as e:
            logger.error(f"Script refinement failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # ===== 资产相关工具 =====

    async def create_character(
        self,
        name: str,
        description: str,
        appearance: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建角色资产
        
        Args:
            name: 角色名称
            description: 角色描述
            appearance: 外貌特征
            project_id: 项目ID
            
        Returns:
            创建结果
        """
        try:
            logger.info(f"Creating character: {name}")
            
            # 检查是否已存在同名角色
            existing = self.db.query(Asset).filter(
                Asset.name == name,
                Asset.type == AssetType.CHARACTER,
            ).first()
            
            if existing:
                return {
                    "success": False,
                    "error": f"角色 '{name}' 已存在",
                    "existing_asset_id": str(existing.id),
                }
            
            # 创建资产记录
            asset = Asset(
                project_id=project_id or "default",
                name=name,
                type=AssetType.CHARACTER,
                description=description,
                data_json={
                    "appearance": appearance,
                    "visual_prompt": f"{name}, {appearance}",
                },
            )
            self.db.add(asset)
            self.db.commit()
            self.db.refresh(asset)
            
            logger.info(f"Created character asset: {asset.id}")
            
            return {
                "success": True,
                "asset_id": str(asset.id),
                "name": name,
                "message": f"成功创建角色 '{name}'",
            }
            
        except Exception as e:
            logger.error(f"Character creation failed: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e),
            }

    async def create_scene(
        self,
        name: str,
        description: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建场景资产
        
        Args:
            name: 场景名称
            description: 场景描述
            project_id: 项目ID
            
        Returns:
            创建结果
        """
        try:
            logger.info(f"Creating scene: {name}")
            
            # 检查是否已存在同名场景
            existing = self.db.query(Asset).filter(
                Asset.name == name,
                Asset.type == AssetType.SCENE,
            ).first()
            
            if existing:
                return {
                    "success": False,
                    "error": f"场景 '{name}' 已存在",
                    "existing_asset_id": str(existing.id),
                }
            
            # 创建资产记录
            asset = Asset(
                project_id=project_id or "default",
                name=name,
                type=AssetType.SCENE,
                description=description,
                data_json={
                    "visual_prompt": f"scene, {name}, {description}",
                },
            )
            self.db.add(asset)
            self.db.commit()
            self.db.refresh(asset)
            
            logger.info(f"Created scene asset: {asset.id}")
            
            return {
                "success": True,
                "asset_id": str(asset.id),
                "name": name,
                "message": f"成功创建场景 '{name}'",
            }
            
        except Exception as e:
            logger.error(f"Scene creation failed: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e),
            }

    async def query_assets(
        self,
        asset_type: str,
        query: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询现有资产
        
        Args:
            asset_type: 资产类型 (character, scene, prop)
            query: 查询关键词
            project_id: 项目ID
            
        Returns:
            查询结果
        """
        try:
            logger.info(f"Querying assets: type={asset_type}, query={query}")
            
            # 映射类型
            type_map = {
                "character": AssetType.CHARACTER,
                "scene": AssetType.SCENE,
                "prop": AssetType.PROP,
            }
            
            db_type = type_map.get(asset_type.lower())
            if not db_type:
                return {
                    "success": False,
                    "error": f"未知的资产类型: {asset_type}",
                }
            
            # 构建查询
            db_query = self.db.query(Asset).filter(Asset.type == db_type)
            
            if project_id:
                db_query = db_query.filter(Asset.project_id == project_id)
            
            if query:
                db_query = db_query.filter(Asset.name.ilike(f"%{query}%"))
            
            assets = db_query.limit(20).all()
            
            result_assets = [
                {
                    "id": str(a.id),
                    "name": a.name,
                    "description": a.description,
                    "type": a.type.value if hasattr(a.type, 'value') else str(a.type),
                    "thumbnail_url": a.thumbnail_url,
                }
                for a in assets
            ]
            
            return {
                "success": True,
                "assets": result_assets,
                "total": len(result_assets),
                "message": f"找到 {len(result_assets)} 个{asset_type}资产",
            }
            
        except Exception as e:
            logger.error(f"Asset query failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # ===== 渲染相关工具 =====

    async def render_panels(
        self,
        panel_ids: List[str],
        quality: str = "draft",
        chapter_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        渲染指定的分镜 — 创建真实的 RenderJob 记录
        """
        try:
            import uuid
            from app.models.render_job import RenderJob, JobType, JobStatus

            logger.info(f"Rendering {len(panel_ids)} panels with quality={quality}")

            tier = "hero" if quality == "final" else "fast" if quality == "draft" else "normal"
            jobs_created = []

            for panel_id in panel_ids:
                panel = self.db.query(Panel).filter(Panel.id == panel_id).first()
                if not panel:
                    logger.warning(f"Panel {panel_id} not found, skipping")
                    continue

                job = RenderJob(
                    id=str(uuid.uuid4()),
                    panel_id=panel_id,
                    chapter_id=chapter_id or panel.chapter_id,
                    job_type=JobType.FULL_RENDER,
                    status=JobStatus.QUEUED,
                    tier=tier,
                )
                self.db.add(job)
                jobs_created.append({
                    "job_id": job.id,
                    "panel_id": panel_id,
                    "status": "queued",
                })

            self.db.commit()

            return {
                "success": True,
                "jobs": jobs_created,
                "panel_count": len(jobs_created),
                "quality": quality,
                "message": f"已创建 {len(jobs_created)} 个渲染任务",
            }

        except Exception as e:
            logger.error(f"Render panels failed: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e),
            }

    async def get_render_status(
        self,
        job_ids: List[str],
    ) -> Dict[str, Any]:
        """
        获取渲染状态 — 查询真实的 RenderJob 表
        """
        try:
            from app.models.render_job import RenderJob

            logger.info(f"Getting status for {len(job_ids)} jobs")

            statuses = []
            for job_id in job_ids:
                job = self.db.query(RenderJob).filter(RenderJob.id == job_id).first()
                if job:
                    statuses.append({
                        "job_id": job.id,
                        "panel_id": job.panel_id,
                        "status": job.status,
                        "progress": job.progress or 0,
                        "current_step": job.current_step,
                        "error": job.error_message if hasattr(job, 'error_message') else None,
                    })
                else:
                    statuses.append({
                        "job_id": job_id,
                        "status": "not_found",
                        "progress": 0,
                    })

            return {
                "success": True,
                "statuses": statuses,
            }

        except Exception as e:
            logger.error(f"Get render status failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # ===== QA相关工具 =====

    async def analyze_quality(
        self,
        panel_id: str,
    ) -> Dict[str, Any]:
        """
        分析分镜质量 — 使用 DraftQA 服务进行真实评估
        """
        try:
            from app.services.draft_qa import DraftQA
            from app.models.storyboard_draft import StoryboardDraft

            logger.info(f"Analyzing quality for panel {panel_id}")

            panel = self.db.query(Panel).filter(Panel.id == panel_id).first()
            if not panel:
                return {
                    "success": False,
                    "error": f"分镜 {panel_id} 不存在",
                }

            # 构造 StoryboardDraft 以利用 DraftQA
            panel_data = panel.data_json or {}
            draft = StoryboardDraft()
            draft.panels_json = [panel_data]

            qa = DraftQA()
            result = qa.evaluate(draft)

            return {
                "success": True,
                "analysis": {
                    "panel_id": panel_id,
                    "overall_score": result.score / 100.0,
                    "passed": result.passed,
                    "error_count": result.error_count,
                    "warning_count": result.warning_count,
                    "fixable_count": result.fixable_count,
                    "issues": [i.to_dict() for i in result.issues],
                },
                "message": f"分镜质量评分: {result.score:.0f}/100 ({'通过' if result.passed else '需修复'})",
            }

        except Exception as e:
            logger.error(f"Quality analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def suggest_fixes(
        self,
        panel_id: str,
        issues: List[str],
    ) -> Dict[str, Any]:
        """
        建议修复方案 — 使用 LLM 生成修复建议
        """
        try:
            from app.services.brain.standard_llm import StandardLLMService

            logger.info(f"Suggesting fixes for panel {panel_id}, issues: {issues}")

            panel = self.db.query(Panel).filter(Panel.id == panel_id).first()
            panel_context = ""
            if panel and panel.data_json:
                desc = panel.data_json.get("action_description", "")
                panel_context = f"\n分镜描述: {desc}" if desc else ""

            llm = StandardLLMService()
            issues_text = "\n".join(f"- {issue}" for issue in issues)

            response = await llm._chat_completion(
                [
                    {"role": "system", "content": "你是漫画质检专家。根据问题列表，为每个问题提供具体、可操作的修复建议。返回JSON数组: [{\"issue\": \"原始问题\", \"fix\": \"修复建议\", \"auto_fixable\": true/false}]"},
                    {"role": "user", "content": f"分镜 {panel_id} 的问题：{panel_context}\n\n{issues_text}"},
                ],
                response_format="json",
            )

            import json
            suggestions = json.loads(response)
            if isinstance(suggestions, dict):
                suggestions = suggestions.get("suggestions", [suggestions])

            return {
                "success": True,
                "suggestions": suggestions,
                "message": f"生成了 {len(suggestions)} 条修复建议",
            }

        except Exception as e:
            logger.error(f"Suggest fixes failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_all_handlers(self) -> Dict[str, callable]:
        """获取所有工具处理函数的映射"""
        return {
            "generate_storyboard": self.generate_storyboard,
            "refine_script": self.refine_script,
            "create_character": self.create_character,
            "create_scene": self.create_scene,
            "query_assets": self.query_assets,
            "render_panels": self.render_panels,
            "get_render_status": self.get_render_status,
            "analyze_quality": self.analyze_quality,
            "suggest_fixes": self.suggest_fixes,
        }
