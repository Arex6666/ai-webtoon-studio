"""
AssetLockGate - 资产门禁确认模块
管理资产绑定的确认、锁定和解锁状态
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class LockStatus(str, Enum):
    """锁定状态"""
    PENDING = "pending"         # 待确认
    CONFIRMED = "confirmed"     # 已确认
    LOCKED = "locked"           # 已锁定（不可修改）
    REJECTED = "rejected"       # 已拒绝


class BindingType(str, Enum):
    """绑定类型"""
    CHARACTER = "character"
    SCENE = "scene"
    PROP = "prop"


class AssetBinding(BaseModel):
    """资产绑定"""
    id: str = Field(..., description="绑定ID")
    storyboard_id: str = Field(..., description="分镜ID")
    reference_name: str = Field(..., description="分镜中的引用名称")
    binding_type: BindingType = Field(..., description="绑定类型")
    asset_id: Optional[str] = Field(None, description="绑定的资产ID")
    asset_name: Optional[str] = Field(None, description="资产名称")
    status: LockStatus = Field(default=LockStatus.PENDING, description="状态")
    confidence: float = Field(0.0, description="匹配置信度")
    confirmed_by: Optional[str] = Field(None, description="确认者")
    confirmed_at: Optional[datetime] = Field(None, description="确认时间")
    locked_at: Optional[datetime] = Field(None, description="锁定时间")
    candidates: List[Dict[str, Any]] = Field(default_factory=list, description="候选资产列表")


class ConfirmAction(BaseModel):
    """确认操作"""
    binding_id: str = Field(..., description="绑定ID")
    action: str = Field(..., description="操作: confirm/reject/change")
    new_asset_id: Optional[str] = Field(None, description="新资产ID（change时使用）")
    reason: Optional[str] = Field(None, description="操作原因")


class LockGateResult(BaseModel):
    """门禁操作结果"""
    success: bool = Field(..., description="是否成功")
    binding_id: str = Field(..., description="绑定ID")
    new_status: LockStatus = Field(..., description="新状态")
    message: str = Field("", description="消息")


class AssetLockGate:
    """
    资产门禁管理器
    
    功能:
    1. 管理资产绑定的确认流程
    2. 支持自动确认高置信度匹配
    3. 锁定已确认的绑定防止意外修改
    4. 提供批量确认/拒绝操作
    """

    def __init__(
        self,
        auto_confirm_threshold: float = 0.95,
    ):
        """
        初始化门禁
        
        Args:
            auto_confirm_threshold: 自动确认阈值
        """
        self.auto_confirm_threshold = auto_confirm_threshold
        
        # 绑定存储
        self._bindings: Dict[str, AssetBinding] = {}
        self._storyboard_bindings: Dict[str, List[str]] = {}  # storyboard_id -> binding_ids

    def create_binding(
        self,
        storyboard_id: str,
        reference_name: str,
        binding_type: BindingType,
        asset_id: Optional[str] = None,
        asset_name: Optional[str] = None,
        confidence: float = 0.0,
        candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> AssetBinding:
        """
        创建资产绑定
        
        Args:
            storyboard_id: 分镜ID
            reference_name: 引用名称
            binding_type: 绑定类型
            asset_id: 资产ID
            asset_name: 资产名称
            confidence: 匹配置信度
            candidates: 候选资产列表
            
        Returns:
            创建的绑定
        """
        binding_id = f"bind_{storyboard_id[:8]}_{reference_name}_{binding_type}"
        
        # 根据置信度决定初始状态
        if asset_id and confidence >= self.auto_confirm_threshold:
            status = LockStatus.CONFIRMED
            confirmed_at = datetime.now()
        else:
            status = LockStatus.PENDING
            confirmed_at = None
        
        binding = AssetBinding(
            id=binding_id,
            storyboard_id=storyboard_id,
            reference_name=reference_name,
            binding_type=binding_type,
            asset_id=asset_id,
            asset_name=asset_name,
            status=status,
            confidence=confidence,
            confirmed_at=confirmed_at,
            candidates=candidates or [],
        )
        
        self._bindings[binding_id] = binding
        
        if storyboard_id not in self._storyboard_bindings:
            self._storyboard_bindings[storyboard_id] = []
        self._storyboard_bindings[storyboard_id].append(binding_id)
        
        logger.info(f"Created binding {binding_id} with status {status}")
        return binding

    def confirm_binding(
        self,
        binding_id: str,
        confirmed_by: Optional[str] = None,
    ) -> LockGateResult:
        """确认绑定"""
        binding = self._bindings.get(binding_id)
        if not binding:
            return LockGateResult(
                success=False,
                binding_id=binding_id,
                new_status=LockStatus.PENDING,
                message="绑定不存在"
            )
        
        if binding.status == LockStatus.LOCKED:
            return LockGateResult(
                success=False,
                binding_id=binding_id,
                new_status=binding.status,
                message="绑定已锁定，无法修改"
            )
        
        if not binding.asset_id:
            return LockGateResult(
                success=False,
                binding_id=binding_id,
                new_status=binding.status,
                message="未绑定资产，无法确认"
            )
        
        binding.status = LockStatus.CONFIRMED
        binding.confirmed_by = confirmed_by
        binding.confirmed_at = datetime.now()
        
        return LockGateResult(
            success=True,
            binding_id=binding_id,
            new_status=LockStatus.CONFIRMED,
            message=f"已确认绑定: {binding.reference_name} -> {binding.asset_name}"
        )

    def reject_binding(
        self,
        binding_id: str,
        reason: Optional[str] = None,
    ) -> LockGateResult:
        """拒绝绑定"""
        binding = self._bindings.get(binding_id)
        if not binding:
            return LockGateResult(
                success=False,
                binding_id=binding_id,
                new_status=LockStatus.PENDING,
                message="绑定不存在"
            )
        
        if binding.status == LockStatus.LOCKED:
            return LockGateResult(
                success=False,
                binding_id=binding_id,
                new_status=binding.status,
                message="绑定已锁定，无法修改"
            )
        
        binding.status = LockStatus.REJECTED
        binding.asset_id = None
        binding.asset_name = None
        
        return LockGateResult(
            success=True,
            binding_id=binding_id,
            new_status=LockStatus.REJECTED,
            message=f"已拒绝绑定: {binding.reference_name}" + (f" ({reason})" if reason else "")
        )

    def change_binding(
        self,
        binding_id: str,
        new_asset_id: str,
        new_asset_name: str,
    ) -> LockGateResult:
        """更换绑定资产"""
        binding = self._bindings.get(binding_id)
        if not binding:
            return LockGateResult(
                success=False,
                binding_id=binding_id,
                new_status=LockStatus.PENDING,
                message="绑定不存在"
            )
        
        if binding.status == LockStatus.LOCKED:
            return LockGateResult(
                success=False,
                binding_id=binding_id,
                new_status=binding.status,
                message="绑定已锁定，无法修改"
            )
        
        binding.asset_id = new_asset_id
        binding.asset_name = new_asset_name
        binding.status = LockStatus.CONFIRMED
        binding.confidence = 1.0  # 用户选择的置信度为1
        binding.confirmed_at = datetime.now()
        
        return LockGateResult(
            success=True,
            binding_id=binding_id,
            new_status=LockStatus.CONFIRMED,
            message=f"已更换绑定: {binding.reference_name} -> {new_asset_name}"
        )

    def lock_binding(self, binding_id: str) -> LockGateResult:
        """锁定绑定（防止修改）"""
        binding = self._bindings.get(binding_id)
        if not binding:
            return LockGateResult(
                success=False,
                binding_id=binding_id,
                new_status=LockStatus.PENDING,
                message="绑定不存在"
            )
        
        if binding.status != LockStatus.CONFIRMED:
            return LockGateResult(
                success=False,
                binding_id=binding_id,
                new_status=binding.status,
                message="只有已确认的绑定才能锁定"
            )
        
        binding.status = LockStatus.LOCKED
        binding.locked_at = datetime.now()
        
        return LockGateResult(
            success=True,
            binding_id=binding_id,
            new_status=LockStatus.LOCKED,
            message=f"已锁定绑定: {binding.reference_name}"
        )

    def unlock_binding(self, binding_id: str) -> LockGateResult:
        """解锁绑定"""
        binding = self._bindings.get(binding_id)
        if not binding:
            return LockGateResult(
                success=False,
                binding_id=binding_id,
                new_status=LockStatus.PENDING,
                message="绑定不存在"
            )
        
        if binding.status == LockStatus.LOCKED:
            binding.status = LockStatus.CONFIRMED
            binding.locked_at = None
            return LockGateResult(
                success=True,
                binding_id=binding_id,
                new_status=LockStatus.CONFIRMED,
                message=f"已解锁绑定: {binding.reference_name}"
            )
        
        return LockGateResult(
            success=False,
            binding_id=binding_id,
            new_status=binding.status,
            message="绑定未锁定"
        )

    def get_binding(self, binding_id: str) -> Optional[AssetBinding]:
        """获取绑定"""
        return self._bindings.get(binding_id)

    def get_storyboard_bindings(
        self,
        storyboard_id: str,
        status_filter: Optional[LockStatus] = None,
    ) -> List[AssetBinding]:
        """获取分镜的所有绑定"""
        binding_ids = self._storyboard_bindings.get(storyboard_id, [])
        bindings = [self._bindings[bid] for bid in binding_ids if bid in self._bindings]
        
        if status_filter:
            bindings = [b for b in bindings if b.status == status_filter]
        
        return bindings

    def get_pending_bindings(self, storyboard_id: str) -> List[AssetBinding]:
        """获取待确认的绑定"""
        return self.get_storyboard_bindings(storyboard_id, LockStatus.PENDING)

    def batch_confirm(
        self,
        binding_ids: List[str],
        confirmed_by: Optional[str] = None,
    ) -> List[LockGateResult]:
        """批量确认"""
        return [self.confirm_binding(bid, confirmed_by) for bid in binding_ids]

    def batch_lock(self, storyboard_id: str) -> List[LockGateResult]:
        """锁定分镜的所有已确认绑定"""
        confirmed = self.get_storyboard_bindings(storyboard_id, LockStatus.CONFIRMED)
        return [self.lock_binding(b.id) for b in confirmed]

    def get_binding_summary(self, storyboard_id: str) -> Dict[str, Any]:
        """获取绑定状态汇总"""
        bindings = self.get_storyboard_bindings(storyboard_id)
        
        return {
            "total": len(bindings),
            "pending": sum(1 for b in bindings if b.status == LockStatus.PENDING),
            "confirmed": sum(1 for b in bindings if b.status == LockStatus.CONFIRMED),
            "locked": sum(1 for b in bindings if b.status == LockStatus.LOCKED),
            "rejected": sum(1 for b in bindings if b.status == LockStatus.REJECTED),
            "ready_to_render": all(b.status in [LockStatus.CONFIRMED, LockStatus.LOCKED] for b in bindings) if bindings else False,
        }
