"""
VersionManager - 版本管理器
分镜快照、回滚和Patch历史追踪
"""
import logging
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class SnapshotType(str, Enum):
    """快照类型"""
    MANUAL = "manual"           # 用户手动保存
    AUTO = "auto"               # 自动保存
    BEFORE_PATCH = "before_patch"  # Patch应用前
    MILESTONE = "milestone"     # 里程碑(锁定)


class Snapshot(BaseModel):
    """快照模型"""
    id: str = Field(..., description="快照ID")
    storyboard_id: str = Field(..., description="分镜ID")
    data: Dict[str, Any] = Field(..., description="快照数据")
    snapshot_type: SnapshotType = Field(default=SnapshotType.AUTO)
    reason: str = Field("", description="保存原因")
    created_at: datetime = Field(default_factory=datetime.now)
    parent_id: Optional[str] = Field(None, description="父快照ID")
    patch_ids: List[str] = Field(default_factory=list, description="关联的Patch ID列表")


class PatchRecord(BaseModel):
    """Patch记录模型"""
    id: str = Field(..., description="Patch记录ID")
    storyboard_id: str = Field(..., description="分镜ID")
    patches: List[Dict[str, Any]] = Field(..., description="Patch操作列表")
    summary: str = Field("", description="修改摘要")
    applied_at: datetime = Field(default_factory=datetime.now)
    before_snapshot_id: Optional[str] = Field(None, description="应用前快照ID")
    after_snapshot_id: Optional[str] = Field(None, description="应用后快照ID")


class DiffItem(BaseModel):
    """差异项"""
    path: str = Field(..., description="JSON路径")
    type: str = Field(..., description="差异类型: added/removed/changed")
    old_value: Optional[Any] = Field(None, description="旧值")
    new_value: Optional[Any] = Field(None, description="新值")


class DiffResult(BaseModel):
    """差异结果"""
    snapshot_id_1: str = Field(..., description="快照1 ID")
    snapshot_id_2: str = Field(..., description="快照2 ID")
    differences: List[DiffItem] = Field(default_factory=list)
    summary: str = Field("", description="差异摘要")


class VersionManager:
    """
    版本管理器
    
    提供分镜的快照管理、版本回滚和Patch历史追踪功能。
    当前实现使用内存存储，后续可替换为数据库存储。
    """

    def __init__(self):
        # 内存存储 (后续可替换为数据库)
        self._snapshots: Dict[str, Snapshot] = {}
        self._patch_records: Dict[str, PatchRecord] = {}
        self._storyboard_snapshots: Dict[str, List[str]] = {}  # storyboard_id -> snapshot_ids
        self._storyboard_patches: Dict[str, List[str]] = {}    # storyboard_id -> patch_ids

    def create_snapshot(
        self,
        storyboard_id: str,
        data: Dict[str, Any],
        reason: str = "",
        snapshot_type: SnapshotType = SnapshotType.AUTO,
        parent_id: Optional[str] = None,
    ) -> Snapshot:
        """
        创建快照
        
        Args:
            storyboard_id: 分镜ID
            data: 分镜数据
            reason: 保存原因
            snapshot_type: 快照类型
            parent_id: 父快照ID
            
        Returns:
            创建的快照
        """
        # 生成快照ID
        snapshot_id = self._generate_snapshot_id(storyboard_id, data)
        
        # 如果已存在相同内容的快照，返回现有快照
        if snapshot_id in self._snapshots:
            logger.debug(f"Snapshot {snapshot_id} already exists, returning existing")
            return self._snapshots[snapshot_id]
        
        # 创建快照
        snapshot = Snapshot(
            id=snapshot_id,
            storyboard_id=storyboard_id,
            data=json.loads(json.dumps(data)),  # 深拷贝
            snapshot_type=snapshot_type,
            reason=reason,
            parent_id=parent_id or self._get_latest_snapshot_id(storyboard_id),
        )
        
        # 存储
        self._snapshots[snapshot_id] = snapshot
        
        if storyboard_id not in self._storyboard_snapshots:
            self._storyboard_snapshots[storyboard_id] = []
        self._storyboard_snapshots[storyboard_id].append(snapshot_id)
        
        logger.info(f"Created snapshot {snapshot_id} for storyboard {storyboard_id}")
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """获取快照"""
        return self._snapshots.get(snapshot_id)

    def get_latest_snapshot(self, storyboard_id: str) -> Optional[Snapshot]:
        """获取最新快照"""
        snapshot_id = self._get_latest_snapshot_id(storyboard_id)
        if snapshot_id:
            return self._snapshots.get(snapshot_id)
        return None

    def list_snapshots(
        self,
        storyboard_id: str,
        limit: int = 20,
    ) -> List[Snapshot]:
        """列出分镜的所有快照"""
        snapshot_ids = self._storyboard_snapshots.get(storyboard_id, [])
        snapshots = [self._snapshots[sid] for sid in snapshot_ids if sid in self._snapshots]
        # 按时间倒序
        snapshots.sort(key=lambda s: s.created_at, reverse=True)
        return snapshots[:limit]

    def rollback_to(
        self,
        storyboard_id: str,
        snapshot_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        回滚到指定快照
        
        Args:
            storyboard_id: 分镜ID
            snapshot_id: 目标快照ID
            
        Returns:
            回滚后的分镜数据，如果快照不存在返回None
        """
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            logger.warning(f"Snapshot {snapshot_id} not found")
            return None
            
        if snapshot.storyboard_id != storyboard_id:
            logger.warning(f"Snapshot {snapshot_id} does not belong to storyboard {storyboard_id}")
            return None
        
        # 创建回滚记录快照
        self.create_snapshot(
            storyboard_id=storyboard_id,
            data=snapshot.data,
            reason=f"Rollback to snapshot {snapshot_id}",
            snapshot_type=SnapshotType.MANUAL,
            parent_id=snapshot_id,
        )
        
        logger.info(f"Rolled back storyboard {storyboard_id} to snapshot {snapshot_id}")
        return json.loads(json.dumps(snapshot.data))

    def record_patch(
        self,
        storyboard_id: str,
        patches: List[Dict[str, Any]],
        summary: str = "",
        before_snapshot_id: Optional[str] = None,
        after_snapshot_id: Optional[str] = None,
    ) -> PatchRecord:
        """
        记录Patch操作
        
        Args:
            storyboard_id: 分镜ID
            patches: Patch操作列表
            summary: 修改摘要
            before_snapshot_id: 应用前快照ID
            after_snapshot_id: 应用后快照ID
            
        Returns:
            Patch记录
        """
        patch_id = self._generate_patch_id()
        
        record = PatchRecord(
            id=patch_id,
            storyboard_id=storyboard_id,
            patches=patches,
            summary=summary,
            before_snapshot_id=before_snapshot_id,
            after_snapshot_id=after_snapshot_id,
        )
        
        self._patch_records[patch_id] = record
        
        if storyboard_id not in self._storyboard_patches:
            self._storyboard_patches[storyboard_id] = []
        self._storyboard_patches[storyboard_id].append(patch_id)
        
        # 关联到快照
        if after_snapshot_id and after_snapshot_id in self._snapshots:
            self._snapshots[after_snapshot_id].patch_ids.append(patch_id)
        
        logger.info(f"Recorded patch {patch_id} for storyboard {storyboard_id}")
        return record

    def get_patch_history(
        self,
        storyboard_id: str,
        limit: int = 50,
    ) -> List[PatchRecord]:
        """获取Patch历史"""
        patch_ids = self._storyboard_patches.get(storyboard_id, [])
        records = [self._patch_records[pid] for pid in patch_ids if pid in self._patch_records]
        # 按时间倒序
        records.sort(key=lambda r: r.applied_at, reverse=True)
        return records[:limit]

    def get_diff(
        self,
        snapshot_id_1: str,
        snapshot_id_2: str,
    ) -> Optional[DiffResult]:
        """
        计算两个快照之间的差异
        
        Args:
            snapshot_id_1: 快照1 ID
            snapshot_id_2: 快照2 ID
            
        Returns:
            差异结果
        """
        snapshot1 = self._snapshots.get(snapshot_id_1)
        snapshot2 = self._snapshots.get(snapshot_id_2)
        
        if not snapshot1 or not snapshot2:
            logger.warning(f"One or both snapshots not found: {snapshot_id_1}, {snapshot_id_2}")
            return None
        
        differences = self._compute_diff(snapshot1.data, snapshot2.data, "")
        
        return DiffResult(
            snapshot_id_1=snapshot_id_1,
            snapshot_id_2=snapshot_id_2,
            differences=differences,
            summary=f"Found {len(differences)} differences",
        )

    def _compute_diff(
        self,
        data1: Any,
        data2: Any,
        path: str,
    ) -> List[DiffItem]:
        """递归计算差异"""
        differences = []
        
        if type(data1) != type(data2):
            differences.append(DiffItem(
                path=path or "/",
                type="changed",
                old_value=data1,
                new_value=data2,
            ))
            return differences
        
        if isinstance(data1, dict):
            all_keys = set(data1.keys()) | set(data2.keys())
            for key in all_keys:
                child_path = f"{path}/{key}"
                if key not in data1:
                    differences.append(DiffItem(
                        path=child_path,
                        type="added",
                        old_value=None,
                        new_value=data2[key],
                    ))
                elif key not in data2:
                    differences.append(DiffItem(
                        path=child_path,
                        type="removed",
                        old_value=data1[key],
                        new_value=None,
                    ))
                else:
                    differences.extend(self._compute_diff(data1[key], data2[key], child_path))
                    
        elif isinstance(data1, list):
            max_len = max(len(data1), len(data2))
            for i in range(max_len):
                child_path = f"{path}/{i}"
                if i >= len(data1):
                    differences.append(DiffItem(
                        path=child_path,
                        type="added",
                        old_value=None,
                        new_value=data2[i],
                    ))
                elif i >= len(data2):
                    differences.append(DiffItem(
                        path=child_path,
                        type="removed",
                        old_value=data1[i],
                        new_value=None,
                    ))
                else:
                    differences.extend(self._compute_diff(data1[i], data2[i], child_path))
        else:
            if data1 != data2:
                differences.append(DiffItem(
                    path=path or "/",
                    type="changed",
                    old_value=data1,
                    new_value=data2,
                ))
        
        return differences

    def _generate_snapshot_id(
        self,
        storyboard_id: str,
        data: Dict[str, Any],
    ) -> str:
        """生成基于内容的快照ID"""
        content = json.dumps(data, sort_keys=True, ensure_ascii=False)
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"snap_{storyboard_id[:8]}_{content_hash}"

    def _generate_patch_id(self) -> str:
        """生成Patch ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"patch_{timestamp}"

    def _get_latest_snapshot_id(self, storyboard_id: str) -> Optional[str]:
        """获取最新快照ID"""
        snapshot_ids = self._storyboard_snapshots.get(storyboard_id, [])
        return snapshot_ids[-1] if snapshot_ids else None

    def clear_storyboard_history(self, storyboard_id: str) -> None:
        """清空分镜历史（用于测试）"""
        # 清除快照
        for sid in self._storyboard_snapshots.get(storyboard_id, []):
            if sid in self._snapshots:
                del self._snapshots[sid]
        self._storyboard_snapshots[storyboard_id] = []
        
        # 清除Patch记录
        for pid in self._storyboard_patches.get(storyboard_id, []):
            if pid in self._patch_records:
                del self._patch_records[pid]
        self._storyboard_patches[storyboard_id] = []
