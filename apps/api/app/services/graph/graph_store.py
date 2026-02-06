"""
GraphStore - Project Graph存储层
统一存储接口，整合VersionManager和持久化
"""
import logging
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from app.services.graph.version_manager import (
    VersionManager,
    Snapshot,
    SnapshotType,
    PatchRecord,
)
from app.services.graph.dependency_graph import (
    DependencyGraph,
    RenderPlan,
)

logger = logging.getLogger(__name__)


class ApplyResult(BaseModel):
    """Patch应用结果"""
    success: bool = Field(..., description="是否成功")
    storyboard_id: str = Field(..., description="分镜ID")
    new_state: Dict[str, Any] = Field(..., description="修改后状态")
    before_snapshot_id: Optional[str] = Field(None, description="应用前快照ID")
    after_snapshot_id: Optional[str] = Field(None, description="应用后快照ID")
    patch_record_id: Optional[str] = Field(None, description="Patch记录ID")
    render_plan: Optional[RenderPlan] = Field(None, description="渲染计划")
    error: Optional[str] = Field(None, description="错误信息")


class GraphStore:
    """
    Project Graph存储层
    
    整合版本管理和依赖图，提供统一的状态管理接口。
    """

    def __init__(self):
        self.version_manager = VersionManager()
        self.dependency_graph = DependencyGraph()
        
        # 当前状态缓存
        self._current_states: Dict[str, Dict[str, Any]] = {}

    def get_current_state(self, storyboard_id: str) -> Optional[Dict[str, Any]]:
        """
        获取分镜当前状态
        
        Args:
            storyboard_id: 分镜ID
            
        Returns:
            当前分镜状态
        """
        # 优先从缓存获取
        if storyboard_id in self._current_states:
            return json.loads(json.dumps(self._current_states[storyboard_id]))
        
        # 从最新快照获取
        snapshot = self.version_manager.get_latest_snapshot(storyboard_id)
        if snapshot:
            self._current_states[storyboard_id] = snapshot.data
            return json.loads(json.dumps(snapshot.data))
        
        return None

    def save_state(
        self,
        storyboard_id: str,
        state: Dict[str, Any],
        reason: str = "",
        snapshot_type: SnapshotType = SnapshotType.AUTO,
    ) -> Snapshot:
        """
        保存分镜状态
        
        Args:
            storyboard_id: 分镜ID
            state: 分镜状态
            reason: 保存原因
            snapshot_type: 快照类型
            
        Returns:
            创建的快照
        """
        # 更新缓存
        self._current_states[storyboard_id] = json.loads(json.dumps(state))
        
        # 创建快照
        return self.version_manager.create_snapshot(
            storyboard_id=storyboard_id,
            data=state,
            reason=reason,
            snapshot_type=snapshot_type,
        )

    def apply_patches(
        self,
        storyboard_id: str,
        patches: List[Dict[str, Any]],
        summary: str = "",
    ) -> ApplyResult:
        """
        应用Patch并保存
        
        Args:
            storyboard_id: 分镜ID
            patches: Patch列表
            summary: 修改摘要
            
        Returns:
            应用结果
        """
        try:
            # 获取当前状态
            current_state = self.get_current_state(storyboard_id)
            if current_state is None:
                return ApplyResult(
                    success=False,
                    storyboard_id=storyboard_id,
                    new_state={},
                    error="Storyboard not found",
                )
            
            # 创建应用前快照
            before_snapshot = self.version_manager.create_snapshot(
                storyboard_id=storyboard_id,
                data=current_state,
                reason="Before patch",
                snapshot_type=SnapshotType.BEFORE_PATCH,
            )
            
            # 导入PatchGenerator应用补丁
            from app.services.agents.patch_generator import PatchGenerator, Patch, PatchOperation
            
            pg = PatchGenerator()
            patch_objects = []
            for p in patches:
                patch_objects.append(Patch(
                    op=PatchOperation(p["op"]),
                    path=p["path"],
                    value=p.get("value"),
                    from_path=p.get("from"),
                    reason=p.get("reason", ""),
                ))
            
            # 应用补丁
            new_state = pg.apply_patches(current_state, patch_objects)
            
            # 创建应用后快照
            after_snapshot = self.version_manager.create_snapshot(
                storyboard_id=storyboard_id,
                data=new_state,
                reason=summary or "After patch",
                snapshot_type=SnapshotType.AUTO,
            )
            
            # 记录Patch
            patch_record = self.version_manager.record_patch(
                storyboard_id=storyboard_id,
                patches=patches,
                summary=summary,
                before_snapshot_id=before_snapshot.id,
                after_snapshot_id=after_snapshot.id,
            )
            
            # 更新缓存
            self._current_states[storyboard_id] = new_state
            
            # 构建渲染计划
            patch_paths = [p["path"] for p in patches]
            render_plan = self.dependency_graph.build_render_plan(new_state, patch_paths)
            
            return ApplyResult(
                success=True,
                storyboard_id=storyboard_id,
                new_state=new_state,
                before_snapshot_id=before_snapshot.id,
                after_snapshot_id=after_snapshot.id,
                patch_record_id=patch_record.id,
                render_plan=render_plan,
            )
            
        except Exception as e:
            logger.error(f"Failed to apply patches: {e}", exc_info=True)
            return ApplyResult(
                success=False,
                storyboard_id=storyboard_id,
                new_state={},
                error=str(e),
            )

    def rollback(
        self,
        storyboard_id: str,
        snapshot_id: str,
    ) -> ApplyResult:
        """
        回滚到指定快照
        
        Args:
            storyboard_id: 分镜ID
            snapshot_id: 目标快照ID
            
        Returns:
            回滚结果
        """
        rolled_back_state = self.version_manager.rollback_to(storyboard_id, snapshot_id)
        
        if rolled_back_state is None:
            return ApplyResult(
                success=False,
                storyboard_id=storyboard_id,
                new_state={},
                error=f"Snapshot {snapshot_id} not found",
            )
        
        # 更新缓存
        self._current_states[storyboard_id] = rolled_back_state
        
        return ApplyResult(
            success=True,
            storyboard_id=storyboard_id,
            new_state=rolled_back_state,
        )

    def get_snapshot_list(
        self,
        storyboard_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取快照列表"""
        snapshots = self.version_manager.list_snapshots(storyboard_id, limit)
        return [
            {
                "id": s.id,
                "reason": s.reason,
                "type": s.snapshot_type,
                "created_at": s.created_at.isoformat(),
            }
            for s in snapshots
        ]

    def get_patch_history(
        self,
        storyboard_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取Patch历史"""
        records = self.version_manager.get_patch_history(storyboard_id, limit)
        return [
            {
                "id": r.id,
                "summary": r.summary,
                "patch_count": len(r.patches),
                "applied_at": r.applied_at.isoformat(),
            }
            for r in records
        ]

    def get_diff(
        self,
        snapshot_id_1: str,
        snapshot_id_2: str,
    ) -> Optional[Dict[str, Any]]:
        """获取两个快照的差异"""
        diff = self.version_manager.get_diff(snapshot_id_1, snapshot_id_2)
        if diff:
            return diff.dict()
        return None

    def analyze_impact(
        self,
        storyboard_id: str,
        patches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        分析Patch影响（不应用）
        
        Args:
            storyboard_id: 分镜ID
            patches: Patch列表
            
        Returns:
            影响分析
        """
        state = self.get_current_state(storyboard_id)
        if not state:
            return {"error": "Storyboard not found"}
        
        return self.dependency_graph.analyze_patch_impact(state, patches)

    def clear_cache(self, storyboard_id: Optional[str] = None) -> None:
        """清除缓存"""
        if storyboard_id:
            self._current_states.pop(storyboard_id, None)
        else:
            self._current_states.clear()
