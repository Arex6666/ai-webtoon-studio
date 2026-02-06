"""
StudioOrchestrator - 统一编排器
整合所有Agent模块，提供端到端的工作流编排
"""
import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

# Phase 1: Director Agent Core
from app.services.agents.director_agent import DirectorAgent, AgentMode
from app.services.agents.schema_guard import SchemaGuard, SchemaType
from app.services.agents.patch_generator import PatchGenerator, PatchTarget

# Phase 2: Project Graph
from app.services.graph.version_manager import VersionManager, SnapshotType
from app.services.graph.dependency_graph import DependencyGraph
from app.services.graph.graph_store import GraphStore

# Phase 3: Asset Hub
from app.services.asset_hub.asset_matcher import AssetMatcher, AssetType, MatchRequest
from app.services.asset_hub.lock_gate import AssetLockGate, BindingType, LockStatus
from app.services.asset_hub.asset_generator import AssetGenerator, GenerationRequest

# Phase 4: Factory
from app.services.layer_factory.prompt_compiler import PromptCompiler, PromptStyle
from app.services.layer_factory.render_planner import RenderPlanner, RenderPriority

logger = logging.getLogger(__name__)


class WorkflowStage(str, Enum):
    """工作流阶段"""
    IDEATION = "ideation"           # 创意构思
    SCRIPTING = "scripting"         # 剧本创作
    STORYBOARDING = "storyboarding" # 分镜设计
    ASSET_BINDING = "asset_binding" # 资产绑定
    RENDERING = "rendering"         # 渲染生成
    QA_REVIEW = "qa_review"         # 质量审核
    EXPORT = "export"               # 导出发布


class SessionState(BaseModel):
    """会话状态"""
    session_id: str
    project_id: str
    stage: WorkflowStage = Field(default=WorkflowStage.IDEATION)
    storyboard_id: Optional[str] = None
    current_storyboard: Optional[Dict[str, Any]] = None
    pending_assets: int = 0
    pending_renders: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class OrchestratorResult(BaseModel):
    """编排结果"""
    success: bool = Field(..., description="是否成功")
    stage: WorkflowStage = Field(..., description="当前阶段")
    message: str = Field("", description="消息")
    data: Optional[Dict[str, Any]] = Field(None, description="返回数据")
    next_actions: List[str] = Field(default_factory=list, description="建议的下一步操作")


class StudioOrchestrator:
    """
    统一编排器
    
    整合Phase 1-4所有模块，提供端到端工作流:
    1. 创意构思 → DirectorAgent对话
    2. 分镜创建 → SchemaGuard验证 + GraphStore保存
    3. 资产绑定 → AssetMatcher匹配 + LockGate确认
    4. 渲染生成 → PromptCompiler编译 + RenderPlanner规划
    5. 质量审核 → DirectorAgent QA模式
    """

    def __init__(self, project_id: str):
        """
        初始化编排器
        
        Args:
            project_id: 项目ID
        """
        self.project_id = project_id
        
        # Phase 1: Director Agent
        self.director = DirectorAgent()
        self.schema_guard = SchemaGuard()
        self.patch_generator = PatchGenerator()
        
        # Phase 2: Project Graph
        self.graph_store = GraphStore()
        self.version_manager = self.graph_store.version_manager
        self.dependency_graph = self.graph_store.dependency_graph
        
        # Phase 3: Asset Hub
        self.asset_matcher = AssetMatcher()
        self.lock_gate = AssetLockGate()
        self.asset_generator = AssetGenerator()
        
        # Phase 4: Factory
        self.prompt_compiler = PromptCompiler()
        self.render_planner = RenderPlanner()
        
        # Session state
        self._sessions: Dict[str, SessionState] = {}

    def create_session(self, session_id: str) -> SessionState:
        """创建会话"""
        state = SessionState(
            session_id=session_id,
            project_id=self.project_id,
        )
        self._sessions[session_id] = state
        logger.info(f"Created session {session_id} for project {self.project_id}")
        return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """获取会话"""
        return self._sessions.get(session_id)

    async def process_message(
        self,
        session_id: str,
        message: str,
    ) -> AsyncGenerator[str, None]:
        """
        处理用户消息
        
        流式返回响应
        """
        session = self._sessions.get(session_id)
        if not session:
            session = self.create_session(session_id)
        
        # 使用DirectorAgent处理
        async for chunk in self.director.process(
            user_message=message,
            conversation_history=[],
            db=None,
        ):
            yield chunk
        
        # 更新会话状态
        session.updated_at = datetime.now()
        
        # 检查是否有分镜更新
        if self.director.current_storyboard:
            session.current_storyboard = self.director.current_storyboard
            if not session.storyboard_id:
                session.storyboard_id = f"sb_{session_id[:8]}"
            session.stage = WorkflowStage.STORYBOARDING

    async def create_storyboard(
        self,
        session_id: str,
        prompt: str,
    ) -> OrchestratorResult:
        """
        创建分镜
        
        Args:
            session_id: 会话ID
            prompt: 创作提示
            
        Returns:
            编排结果
        """
        session = self._sessions.get(session_id) or self.create_session(session_id)
        
        try:
            # 切换到编剧模式
            self.director.switch_mode(AgentMode.SCRIPTWRITER)
            
            # 收集完整响应
            full_response = ""
            async for chunk in self.director.process(
                user_message=f"请根据以下描述创建分镜：{prompt}",
                conversation_history=[],
                db=None,
            ):
                full_response += chunk
            
            if self.director.current_storyboard:
                storyboard = self.director.current_storyboard
                storyboard_id = f"sb_{session_id[:8]}_{datetime.now().strftime('%H%M%S')}"
                
                # 保存到GraphStore
                snapshot = self.graph_store.save_state(
                    storyboard_id,
                    storyboard,
                    reason="Initial creation",
                    snapshot_type=SnapshotType.MANUAL,
                )
                
                # 更新会话
                session.storyboard_id = storyboard_id
                session.current_storyboard = storyboard
                session.stage = WorkflowStage.STORYBOARDING
                
                return OrchestratorResult(
                    success=True,
                    stage=WorkflowStage.STORYBOARDING,
                    message="分镜创建成功",
                    data={
                        "storyboard_id": storyboard_id,
                        "storyboard": storyboard,
                        "snapshot_id": snapshot.id,
                        "panel_count": len(storyboard.get("panels", [])),
                    },
                    next_actions=["bind_assets", "modify_storyboard", "preview"],
                )
            else:
                return OrchestratorResult(
                    success=False,
                    stage=session.stage,
                    message="分镜创建失败",
                    next_actions=["retry", "modify_prompt"],
                )
                
        except Exception as e:
            logger.error(f"Storyboard creation failed: {e}", exc_info=True)
            return OrchestratorResult(
                success=False,
                stage=session.stage,
                message=f"创建失败: {str(e)}",
            )

    async def modify_storyboard(
        self,
        session_id: str,
        instruction: str,
    ) -> OrchestratorResult:
        """
        修改分镜
        
        Args:
            session_id: 会话ID
            instruction: 修改指令
            
        Returns:
            编排结果
        """
        session = self._sessions.get(session_id)
        if not session or not session.current_storyboard:
            return OrchestratorResult(
                success=False,
                stage=WorkflowStage.IDEATION,
                message="请先创建分镜",
            )
        
        try:
            # 生成Patch
            patch_result = await self.patch_generator.generate_patch(
                user_instruction=instruction,
                current_state=session.current_storyboard,
                target_type=PatchTarget.STORYBOARD,
            )
            
            if not patch_result.success:
                return OrchestratorResult(
                    success=False,
                    stage=session.stage,
                    message="生成修改方案失败",
                )
            
            # 应用Patch并保存
            patches = [p.dict() for p in patch_result.patches]
            apply_result = self.graph_store.apply_patches(
                session.storyboard_id,
                patches,
                summary=instruction,
            )
            
            if apply_result.success:
                session.current_storyboard = apply_result.new_state
                
                return OrchestratorResult(
                    success=True,
                    stage=WorkflowStage.STORYBOARDING,
                    message="分镜修改成功",
                    data={
                        "storyboard": apply_result.new_state,
                        "patches_applied": len(patches),
                        "render_plan": apply_result.render_plan.dict() if apply_result.render_plan else None,
                    },
                    next_actions=["continue_editing", "bind_assets", "start_render"],
                )
            else:
                return OrchestratorResult(
                    success=False,
                    stage=session.stage,
                    message=f"应用修改失败: {apply_result.error}",
                )
                
        except Exception as e:
            logger.error(f"Storyboard modification failed: {e}", exc_info=True)
            return OrchestratorResult(
                success=False,
                stage=session.stage,
                message=f"修改失败: {str(e)}",
            )

    async def bind_assets(
        self,
        session_id: str,
    ) -> OrchestratorResult:
        """
        执行资产绑定
        
        自动匹配分镜中的角色、场景、道具到资产库
        """
        session = self._sessions.get(session_id)
        if not session or not session.current_storyboard:
            return OrchestratorResult(
                success=False,
                stage=WorkflowStage.IDEATION,
                message="请先创建分镜",
            )
        
        try:
            # 执行资产匹配
            match_result = self.asset_matcher.extract_and_match(
                session.current_storyboard,
                project_id=self.project_id,
            )
            
            # 为每个匹配结果创建绑定
            results_data = match_result.get("results", {})
            for name, match in results_data.items():
                match_data = match if isinstance(match, dict) else match.dict()
                best = match_data.get("best_match")
                
                # 确定绑定类型
                asset_type = match_data.get("asset_type", "character")
                binding_type = BindingType.CHARACTER
                if asset_type == "scene":
                    binding_type = BindingType.SCENE
                elif asset_type == "prop":
                    binding_type = BindingType.PROP
                
                # 创建绑定
                self.lock_gate.create_binding(
                    storyboard_id=session.storyboard_id,
                    reference_name=name,
                    binding_type=binding_type,
                    asset_id=best.get("asset_id") if best else None,
                    asset_name=best.get("name") if best else None,
                    confidence=best.get("score", 0) if best else 0,
                    candidates=match_data.get("candidates", []),
                )
            
            # 获取绑定摘要
            summary = self.lock_gate.get_binding_summary(session.storyboard_id)
            session.pending_assets = summary.get("pending", 0)
            session.stage = WorkflowStage.ASSET_BINDING
            
            return OrchestratorResult(
                success=True,
                stage=WorkflowStage.ASSET_BINDING,
                message=f"资产匹配完成，{summary['pending']}项待确认",
                data={
                    "summary": summary,
                    "match_summary": match_result.get("summary", {}),
                },
                next_actions=["confirm_bindings", "generate_assets", "view_pending"],
            )
            
        except Exception as e:
            logger.error(f"Asset binding failed: {e}", exc_info=True)
            return OrchestratorResult(
                success=False,
                stage=session.stage,
                message=f"资产绑定失败: {str(e)}",
            )

    async def prepare_render(
        self,
        session_id: str,
        panel_ids: Optional[List[str]] = None,
        priority: RenderPriority = RenderPriority.NORMAL,
    ) -> OrchestratorResult:
        """
        准备渲染
        
        编译提示词并生成渲染计划
        """
        session = self._sessions.get(session_id)
        if not session or not session.current_storyboard:
            return OrchestratorResult(
                success=False,
                stage=WorkflowStage.IDEATION,
                message="请先创建分镜",
            )
        
        # 检查资产绑定状态
        if session.storyboard_id:
            binding_summary = self.lock_gate.get_binding_summary(session.storyboard_id)
            if not binding_summary.get("ready_to_render", False):
                pending = binding_summary.get("pending", 0)
                return OrchestratorResult(
                    success=False,
                    stage=WorkflowStage.ASSET_BINDING,
                    message=f"还有{pending}项资产待确认",
                    next_actions=["confirm_bindings", "force_render"],
                )
        
        try:
            panels = session.current_storyboard.get("panels", [])
            
            # 编译提示词
            prompts = self.prompt_compiler.compile_batch(
                panels,
                session.current_storyboard,
            )
            
            # 生成渲染计划
            if panel_ids:
                plan = self.render_planner.create_selective_plan(
                    session.current_storyboard,
                    session.storyboard_id,
                    panel_ids,
                    priority=priority,
                )
            else:
                plan = self.render_planner.create_full_render_plan(
                    session.current_storyboard,
                    session.storyboard_id,
                    priority=priority,
                )
            
            session.pending_renders = plan.total_jobs
            session.stage = WorkflowStage.RENDERING
            
            plan_summary = self.render_planner.get_plan_summary(plan)
            
            return OrchestratorResult(
                success=True,
                stage=WorkflowStage.RENDERING,
                message=f"渲染计划已生成，共{plan.total_jobs}个任务",
                data={
                    "plan": plan_summary,
                    "prompts": [p.dict() for p in prompts],
                },
                next_actions=["execute_render", "modify_plan", "preview_prompts"],
            )
            
        except Exception as e:
            logger.error(f"Render preparation failed: {e}", exc_info=True)
            return OrchestratorResult(
                success=False,
                stage=session.stage,
                message=f"渲染准备失败: {str(e)}",
            )

    def get_workflow_status(self, session_id: str) -> Dict[str, Any]:
        """获取工作流状态"""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        binding_summary = {}
        if session.storyboard_id:
            binding_summary = self.lock_gate.get_binding_summary(session.storyboard_id)
        
        return {
            "session_id": session_id,
            "project_id": self.project_id,
            "stage": session.stage.value,
            "storyboard_id": session.storyboard_id,
            "has_storyboard": session.current_storyboard is not None,
            "panel_count": len(session.current_storyboard.get("panels", [])) if session.current_storyboard else 0,
            "asset_bindings": binding_summary,
            "pending_renders": session.pending_renders,
            "updated_at": session.updated_at.isoformat(),
        }

    def rollback_storyboard(
        self,
        session_id: str,
        snapshot_id: str,
    ) -> OrchestratorResult:
        """回滚分镜到指定版本"""
        session = self._sessions.get(session_id)
        if not session or not session.storyboard_id:
            return OrchestratorResult(
                success=False,
                stage=WorkflowStage.IDEATION,
                message="无可回滚的分镜",
            )
        
        result = self.graph_store.rollback(session.storyboard_id, snapshot_id)
        
        if result.success:
            session.current_storyboard = result.new_state
            return OrchestratorResult(
                success=True,
                stage=session.stage,
                message="回滚成功",
                data={"storyboard": result.new_state},
            )
        else:
            return OrchestratorResult(
                success=False,
                stage=session.stage,
                message=f"回滚失败: {result.error}",
            )

    def get_version_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取版本历史"""
        session = self._sessions.get(session_id)
        if not session or not session.storyboard_id:
            return []
        
        return self.graph_store.get_snapshot_list(session.storyboard_id)
