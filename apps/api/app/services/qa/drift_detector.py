"""
脸漂移检测服务
检测生成图像与角色 Embedding 的一致性
"""
import logging
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DriftResult(BaseModel):
    """漂移检测结果"""
    is_drifted: bool
    similarity: float
    threshold: float
    severity: str  # none, mild, moderate, severe
    suggestion: Optional[str] = None


class DriftDetector:
    """
    脸漂移检测器
    比较生成图像与角色原始 Embedding 的相似度
    """
    
    # 相似度阈值
    THRESHOLD_PASS = 0.7      # 通过阈值
    THRESHOLD_WARNING = 0.6   # 警告阈值
    THRESHOLD_FAIL = 0.5      # 失败阈值
    
    def __init__(self):
        self._face_extractor = None
    
    def _get_face_extractor(self):
        """延迟获取 FaceExtractor"""
        if self._face_extractor is None:
            from app.services.identity import get_face_extractor
            self._face_extractor = get_face_extractor()
        return self._face_extractor
    
    async def check_drift(
        self,
        generated_image: bytes,
        reference_embedding: bytes,
        threshold: float = None
    ) -> DriftResult:
        """
        检测生成图像是否与参考 embedding 存在漂移
        
        Args:
            generated_image: 生成的图像数据
            reference_embedding: 序列化的参考 embedding
            threshold: 自定义阈值（默认使用 THRESHOLD_PASS）
            
        Returns:
            DriftResult 包含检测结果
        """
        threshold = threshold or self.THRESHOLD_PASS
        
        extractor = self._get_face_extractor()
        
        # 从生成图像提取 embedding
        gen_embedding, _ = extractor.extract_embedding(generated_image)
        
        if gen_embedding is None:
            logger.warning("No face detected in generated image")
            return DriftResult(
                is_drifted=True,
                similarity=0.0,
                threshold=threshold,
                severity="severe",
                suggestion="生成图像中未检测到人脸，建议重新生成或调整构图"
            )
        
        # 反序列化参考 embedding
        ref_embedding = extractor.deserialize_embedding(reference_embedding)
        
        # 计算相似度
        similarity = extractor.compute_similarity(gen_embedding, ref_embedding)
        
        # 判断漂移程度
        if similarity >= self.THRESHOLD_PASS:
            severity = "none"
            is_drifted = False
            suggestion = None
        elif similarity >= self.THRESHOLD_WARNING:
            severity = "mild"
            is_drifted = True
            suggestion = "轻微漂移，建议提高 FaceID 权重后重试"
        elif similarity >= self.THRESHOLD_FAIL:
            severity = "moderate"
            is_drifted = True
            suggestion = "中度漂移，建议检查角色定妆照质量或更换参考图"
        else:
            severity = "severe"
            is_drifted = True
            suggestion = "严重漂移，建议重新提取角色 Embedding 或手动调整"
        
        logger.info(f"Drift check: similarity={similarity:.3f}, severity={severity}")
        
        return DriftResult(
            is_drifted=is_drifted,
            similarity=similarity,
            threshold=threshold,
            severity=severity,
            suggestion=suggestion
        )
    
    async def batch_check(
        self,
        images: list,
        reference_embedding: bytes,
        threshold: float = None
    ) -> Dict[str, Any]:
        """
        批量检测多张图像的漂移情况
        
        Args:
            images: 图像数据列表
            reference_embedding: 参考 embedding
            threshold: 阈值
            
        Returns:
            批量检测结果，包含平均分和各图像结果
        """
        results = []
        total_similarity = 0
        drifted_count = 0
        
        for i, img_data in enumerate(images):
            result = await self.check_drift(img_data, reference_embedding, threshold)
            results.append({
                "index": i,
                "similarity": result.similarity,
                "is_drifted": result.is_drifted,
                "severity": result.severity
            })
            total_similarity += result.similarity
            if result.is_drifted:
                drifted_count += 1
        
        avg_similarity = total_similarity / len(images) if images else 0
        
        return {
            "total_images": len(images),
            "drifted_count": drifted_count,
            "average_similarity": avg_similarity,
            "pass_rate": (len(images) - drifted_count) / len(images) if images else 0,
            "results": results
        }
    
    def get_recommended_adjustment(
        self,
        current_similarity: float,
        current_weight: float = 0.7
    ) -> Dict[str, float]:
        """
        根据当前相似度推荐参数调整
        
        Args:
            current_similarity: 当前相似度
            current_weight: 当前 FaceID 权重
            
        Returns:
            推荐的参数调整
        """
        if current_similarity >= self.THRESHOLD_PASS:
            return {"faceid_weight": current_weight, "adjustment": "无需调整"}
        
        # 相似度越低，需要的权重越高
        gap = self.THRESHOLD_PASS - current_similarity
        
        if gap < 0.1:
            # 轻微调整
            new_weight = min(1.0, current_weight + 0.1)
        elif gap < 0.2:
            # 中度调整
            new_weight = min(1.0, current_weight + 0.2)
        else:
            # 大幅调整
            new_weight = min(1.0, current_weight + 0.3)
        
        return {
            "faceid_weight": new_weight,
            "adjustment": f"建议将权重从 {current_weight:.2f} 调整为 {new_weight:.2f}"
        }


# 单例实例
_drift_detector: Optional[DriftDetector] = None


def get_drift_detector() -> DriftDetector:
    """获取 DriftDetector 单例"""
    global _drift_detector
    if _drift_detector is None:
        _drift_detector = DriftDetector()
    return _drift_detector
