"""
自动重试管理器
当检测到质量问题时自动调整参数并重试
"""
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from enum import Enum

logger = logging.getLogger(__name__)


class RetryReason(str, Enum):
    """重试原因"""
    FACE_DRIFT = "face_drift"
    NO_FACE = "no_face"
    LOW_QUALITY = "low_quality"
    SEGMENTATION_FAIL = "segmentation_fail"


class RetryAction(BaseModel):
    """重试动作"""
    action_type: str  # retry, adjust_and_retry, manual_fix, give_up
    parameter_changes: Dict[str, Any] = {}
    message: str
    retry_count: int = 0
    max_retries: int = 3


class AutoRetryManager:
    """
    自动重试管理器
    根据检测结果决定是否重试以及如何调整参数
    """
    
    MAX_RETRIES = 3
    
    def __init__(self):
        self._retry_history: Dict[str, List[Dict]] = {}
    
    def should_retry(
        self,
        panel_id: str,
        issue_type: RetryReason,
        current_params: Dict[str, Any],
        quality_score: float = 0.0
    ) -> RetryAction:
        """
        判断是否应该重试
        
        Args:
            panel_id: 分镜 ID
            issue_type: 问题类型
            current_params: 当前参数
            quality_score: 质量分数
            
        Returns:
            RetryAction 包含重试建议
        """
        # 获取重试历史
        history = self._retry_history.get(panel_id, [])
        retry_count = len(history)
        
        # 超过最大重试次数
        if retry_count >= self.MAX_RETRIES:
            return RetryAction(
                action_type="manual_fix",
                message=f"已重试 {retry_count} 次，建议手动调整",
                retry_count=retry_count,
                max_retries=self.MAX_RETRIES
            )
        
        # 根据问题类型决定调整策略
        if issue_type == RetryReason.FACE_DRIFT:
            return self._handle_face_drift(panel_id, current_params, retry_count, quality_score)
        
        elif issue_type == RetryReason.NO_FACE:
            return self._handle_no_face(panel_id, current_params, retry_count)
        
        elif issue_type == RetryReason.LOW_QUALITY:
            return self._handle_low_quality(panel_id, current_params, retry_count)
        
        elif issue_type == RetryReason.SEGMENTATION_FAIL:
            return self._handle_segmentation_fail(panel_id, current_params, retry_count)
        
        return RetryAction(
            action_type="manual_fix",
            message="未知问题类型，请手动检查",
            retry_count=retry_count,
            max_retries=self.MAX_RETRIES
        )
    
    def _handle_face_drift(
        self,
        panel_id: str,
        params: Dict,
        retry_count: int,
        similarity: float
    ) -> RetryAction:
        """处理脸漂移问题"""
        current_weight = params.get("faceid_weight", 0.7)
        
        # 逐步提高 FaceID 权重
        weight_increase = 0.1 * (retry_count + 1)
        new_weight = min(1.0, current_weight + weight_increase)
        
        # 如果相似度很低，可能需要降低 CFG
        current_cfg = params.get("cfg", 7.0)
        new_cfg = current_cfg
        if similarity < 0.5:
            new_cfg = max(4.0, current_cfg - 1.0)
        
        return RetryAction(
            action_type="adjust_and_retry",
            parameter_changes={
                "faceid_weight": new_weight,
                "cfg": new_cfg,
                "seed": -1  # 换种子
            },
            message=f"检测到脸漂移 (相似度={similarity:.2f})，提高 FaceID 权重至 {new_weight:.2f}",
            retry_count=retry_count,
            max_retries=self.MAX_RETRIES
        )
    
    def _handle_no_face(
        self,
        panel_id: str,
        params: Dict,
        retry_count: int
    ) -> RetryAction:
        """处理无人脸检测问题"""
        # 可能是构图问题，尝试调整
        current_shot = params.get("shot_type", "medium")
        
        # 建议使用更近的景别
        shot_suggestions = {
            "wide": "full",
            "full": "medium",
            "medium": "close",
            "extreme_wide": "wide"
        }
        
        new_shot = shot_suggestions.get(current_shot, "medium")
        
        return RetryAction(
            action_type="adjust_and_retry",
            parameter_changes={
                "shot_type": new_shot,
                "seed": -1
            },
            message=f"未检测到人脸，建议将景别从 {current_shot} 调整为 {new_shot}",
            retry_count=retry_count,
            max_retries=self.MAX_RETRIES
        )
    
    def _handle_low_quality(
        self,
        panel_id: str,
        params: Dict,
        retry_count: int
    ) -> RetryAction:
        """处理低质量问题"""
        current_steps = params.get("steps", 30)
        
        # 增加采样步数
        new_steps = min(50, current_steps + 10)
        
        return RetryAction(
            action_type="adjust_and_retry",
            parameter_changes={
                "steps": new_steps,
                "seed": -1
            },
            message=f"图像质量较低，增加采样步数至 {new_steps}",
            retry_count=retry_count,
            max_retries=self.MAX_RETRIES
        )
    
    def _handle_segmentation_fail(
        self,
        panel_id: str,
        params: Dict,
        retry_count: int
    ) -> RetryAction:
        """处理分割失败问题"""
        return RetryAction(
            action_type="adjust_and_retry",
            parameter_changes={
                "segmentation_model": "isnet-anime",  # 尝试不同模型
                "seed": -1
            },
            message="分割失败，尝试使用动漫专用分割模型",
            retry_count=retry_count,
            max_retries=self.MAX_RETRIES
        )
    
    def record_retry(
        self,
        panel_id: str,
        action: RetryAction,
        result: Dict[str, Any]
    ):
        """记录重试历史"""
        if panel_id not in self._retry_history:
            self._retry_history[panel_id] = []
        
        self._retry_history[panel_id].append({
            "action": action.dict(),
            "result": result
        })
        
        logger.info(f"Recorded retry for panel {panel_id}, total retries: {len(self._retry_history[panel_id])}")
    
    def clear_history(self, panel_id: str):
        """清除重试历史（成功后调用）"""
        if panel_id in self._retry_history:
            del self._retry_history[panel_id]
    
    def get_history(self, panel_id: str) -> List[Dict]:
        """获取重试历史"""
        return self._retry_history.get(panel_id, [])


# 单例实例
_auto_retry_manager: Optional[AutoRetryManager] = None


def get_auto_retry_manager() -> AutoRetryManager:
    """获取 AutoRetryManager 单例"""
    global _auto_retry_manager
    if _auto_retry_manager is None:
        _auto_retry_manager = AutoRetryManager()
    return _auto_retry_manager
