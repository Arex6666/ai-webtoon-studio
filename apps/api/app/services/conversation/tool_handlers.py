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
        panel_ids: Optional[List[str]] = None,
        quality: str = "draft",
        chapter_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        渲染指定的分镜 (Agent 工具: 将每个 panel 作为独立 Celery 任务排队)

        Args:
            panel_ids: 分镜ID列表 (可选, 若缺省则渲染整章)
            quality: 质量 (draft, final)
            chapter_id: 章节ID (当 panel_ids 未提供时必填)

        Returns:
            {success, chapter_id, queued_count, jobs}
        """
        if not chapter_id and not panel_ids:
            return {"success": False, "error": "chapter_id or panel_ids required"}

        try:
            from app.models.chapter import Chapter
            from app.api.routes.jobs import create_job_record, JobType
            from app.workers.image_worker import execute_image_job

            # 加载 panels
            q = self.db.query(Panel)
            if panel_ids:
                q = q.filter(Panel.id.in_(panel_ids))
            if chapter_id:
                q = q.filter(Panel.chapter_id == chapter_id)
            panels = q.all()

            if not panels:
                return {"success": False, "error": "no panels to render"}

            # 若未显式传入 chapter_id, 从首个 panel 推导
            resolved_chapter_id = chapter_id or panels[0].chapter_id

            # 校验 chapter 存在 (仅在显式指定时)
            if chapter_id:
                chapter = self.db.query(Chapter).filter(Chapter.id == chapter_id).first()
                if not chapter:
                    return {"success": False, "error": "chapter not found"}

            queued = []
            for p in panels:
                job = create_job_record(
                    db=self.db,
                    job_type=JobType.IMAGE.value,
                    provider="comfyui",
                    inputs={"quality": quality},
                    panel_id=p.id,
                    chapter_id=p.chapter_id,
                )
                async_result = execute_image_job.delay(job.id, p.id)
                queued.append({
                    "panel_id": p.id,
                    "job_id": job.id,
                    "task_id": async_result.id,
                })

            logger.info(
                f"render_panels queued {len(queued)} jobs for chapter={resolved_chapter_id} quality={quality}"
            )

            return {
                "success": True,
                "chapter_id": resolved_chapter_id,
                "queued_count": len(queued),
                "jobs": queued,
            }

        except Exception as e:
            logger.error(f"render_panels handler failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    async def get_render_status(
        self,
        job_ids: List[str],
    ) -> Dict[str, Any]:
        """
        获取渲染状态
        
        Args:
            job_ids: 任务ID列表
            
        Returns:
            状态信息
        """
        try:
            logger.info(f"Getting status for {len(job_ids)} jobs")
            
            # TODO: 从实际的任务队列获取状态
            # 目前返回模拟结果
            statuses = [
                {
                    "job_id": job_id,
                    "status": "processing",
                    "progress": 0.5,
                }
                for job_id in job_ids
            ]
            
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
        分析分镜质量
        
        Args:
            panel_id: 分镜ID
            
        Returns:
            质量分析结果
        """
        try:
            logger.info(f"Analyzing quality for panel {panel_id}")
            
            # 获取分镜
            panel = self.db.query(Panel).filter(Panel.id == panel_id).first()
            if not panel:
                return {
                    "success": False,
                    "error": f"分镜 {panel_id} 不存在",
                }
            
            # 调用QA服务
            # TODO: 实际QA分析
            analysis = {
                "panel_id": panel_id,
                "overall_score": 0.8,
                "issues": [],
                "suggestions": [],
            }
            
            return {
                "success": True,
                "analysis": analysis,
                "message": f"分镜质量评分: {analysis['overall_score']:.0%}",
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
        建议修复方案
        
        Args:
            panel_id: 分镜ID
            issues: 问题列表
            
        Returns:
            修复建议
        """
        try:
            logger.info(f"Suggesting fixes for panel {panel_id}, issues: {issues}")
            
            # TODO: 调用LLM生成修复建议
            suggestions = [
                {
                    "issue": issue,
                    "fix": f"建议修复: {issue}",
                    "auto_fixable": False,
                }
                for issue in issues
            ]
            
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
