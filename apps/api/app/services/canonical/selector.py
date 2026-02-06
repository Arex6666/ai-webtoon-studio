"""
Candidate Selector - 候选定妆照评分与选优
P0-CH-04: 评分框架 + 工程版评分 + 可解释结果

评分维度:
- face_detected: 是否检测到人脸
- face_size: 人脸框面积占比
- single_face: 是否单人脸 (多人脸重罚)
- center_ok: 主体是否居中
- pose_ok: 姿态是否正面 (yaw/pitch)
- quality: 检测置信度
"""
import logging
import io
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
import numpy as np

logger = logging.getLogger(__name__)


# ============ Score Model ============

class CandidateScore(BaseModel):
    """候选评分结果"""
    path: str = Field(..., description="候选图片路径")
    total: float = Field(0.0, description="总分 (0-100)")
    breakdown: Dict[str, float] = Field(default_factory=dict, description="各维度分数")
    flags: List[str] = Field(default_factory=list, description="标记 (face_obscured, multi_face...)")
    notes: str = Field("", description="简短解释")
    
    # 原始检测数据
    face_detected: bool = False
    face_count: int = 0
    det_score: float = 0.0
    bbox: Optional[List[float]] = None
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    
    def to_reason_text(self) -> str:
        """生成人话版选择原因"""
        parts = []
        if self.breakdown.get("face_detected", 0) > 0:
            parts.append("正脸清晰")
        if self.breakdown.get("single_face", 0) > 0:
            parts.append("单人像")
        if self.breakdown.get("pose_ok", 0) > 0 and self.yaw is not None:
            parts.append(f"姿态稳定(yaw={abs(self.yaw):.0f}°)")
        if self.breakdown.get("center_ok", 0) > 0:
            parts.append("居中")
        if self.breakdown.get("quality", 0) > 8:
            parts.append("高清晰度")
        
        if not parts:
            return "未检测到有效人脸"
        
        return "、".join(parts)


# ============ Scoring Weights ============

SCORE_WEIGHTS = {
    "face_detected": 30,   # 是否检测到人脸 (必要条件)
    "face_size": 20,       # 人脸大小
    "single_face": 15,     # 单人脸 (多人脸重罚)
    "center_ok": 10,       # 居中
    "pose_ok": 15,         # 姿态
    "quality": 10,         # 检测质量
}


# ============ Scorer Class ============

class CandidateScorer:
    """候选评分器"""
    
    def __init__(self):
        self._face_analyzer = None
    
    def _get_face_analyzer(self):
        """延迟加载 InsightFace"""
        if self._face_analyzer is None:
            try:
                from insightface.app import FaceAnalysis
                self._face_analyzer = FaceAnalysis(
                    name="buffalo_l",
                    providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
                )
                self._face_analyzer.prepare(ctx_id=0, det_size=(640, 640))
                logger.info("InsightFace analyzer loaded")
            except Exception as e:
                logger.warning(f"Failed to load InsightFace: {e}")
                self._face_analyzer = "unavailable"
        return self._face_analyzer if self._face_analyzer != "unavailable" else None
    
    async def score_candidate(
        self,
        image_data: bytes,
        image_path: str,
        character_spec: Optional[Dict[str, Any]] = None,
        style_profile: Optional[str] = None,
    ) -> CandidateScore:
        """
        评分单个候选图片
        
        Args:
            image_data: 图片二进制数据
            image_path: 图片路径 (用于记录)
            character_spec: 角色规格 (用于特征匹配)
            style_profile: 风格配置
            
        Returns:
            CandidateScore
        """
        score = CandidateScore(path=image_path)
        
        # 尝试使用 InsightFace 检测
        analyzer = self._get_face_analyzer()
        
        if analyzer:
            score = await self._score_with_insightface(image_data, image_path, analyzer)
        else:
            # Fallback: 基于规则的简单评分
            score = self._score_with_rules(image_data, image_path)
        
        # 计算总分
        score.total = sum(score.breakdown.values())
        
        # 生成解释
        score.notes = score.to_reason_text()
        
        return score
    
    async def _score_with_insightface(
        self,
        image_data: bytes,
        image_path: str,
        analyzer,
    ) -> CandidateScore:
        """使用 InsightFace 评分"""
        import cv2
        
        score = CandidateScore(path=image_path)
        
        try:
            # 解码图片
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                score.flags.append("decode_failed")
                return score
            
            img_height, img_width = img.shape[:2]
            img_area = img_height * img_width
            
            # 检测人脸
            faces = analyzer.get(img)
            score.face_count = len(faces)
            
            if len(faces) == 0:
                # 未检测到人脸
                score.flags.append("no_face")
                score.breakdown = {k: 0 for k in SCORE_WEIGHTS}
                return score
            
            # 检测到人脸
            score.face_detected = True
            score.breakdown["face_detected"] = SCORE_WEIGHTS["face_detected"]
            
            # 多人脸检测
            if len(faces) > 1:
                score.flags.append("multi_face")
                score.breakdown["single_face"] = -SCORE_WEIGHTS["single_face"]  # 负分!
            else:
                score.breakdown["single_face"] = SCORE_WEIGHTS["single_face"]
            
            # 取最大/最可信的人脸
            face = max(faces, key=lambda f: f.det_score)
            score.det_score = float(face.det_score)
            
            # Bounding box
            bbox = face.bbox.tolist()
            score.bbox = bbox
            
            # 人脸大小评分
            face_width = bbox[2] - bbox[0]
            face_height = bbox[3] - bbox[1]
            face_area = face_width * face_height
            face_ratio = face_area / img_area
            
            # 理想: 脸占比 5%-30%
            if 0.05 <= face_ratio <= 0.30:
                score.breakdown["face_size"] = SCORE_WEIGHTS["face_size"]
            elif face_ratio < 0.02:
                score.breakdown["face_size"] = 0
                score.flags.append("face_too_small")
            elif face_ratio > 0.50:
                score.breakdown["face_size"] = SCORE_WEIGHTS["face_size"] * 0.5
                score.flags.append("face_too_large")
            else:
                score.breakdown["face_size"] = SCORE_WEIGHTS["face_size"] * 0.7
            
            # 居中评分
            face_center_x = (bbox[0] + bbox[2]) / 2
            face_center_y = (bbox[1] + bbox[3]) / 2
            img_center_x = img_width / 2
            img_center_y = img_height / 2
            
            offset_x = abs(face_center_x - img_center_x) / img_width
            offset_y = abs(face_center_y - img_center_y) / img_height
            offset = (offset_x + offset_y) / 2
            
            if offset < 0.15:
                score.breakdown["center_ok"] = SCORE_WEIGHTS["center_ok"]
            elif offset < 0.25:
                score.breakdown["center_ok"] = SCORE_WEIGHTS["center_ok"] * 0.7
            else:
                score.breakdown["center_ok"] = SCORE_WEIGHTS["center_ok"] * 0.3
                score.flags.append("off_center")
            
            # 姿态评分 (从 3D pose 获取)
            if hasattr(face, 'pose') and face.pose is not None:
                pose = face.pose
                score.yaw = float(pose[1]) if len(pose) > 1 else 0
                score.pitch = float(pose[0]) if len(pose) > 0 else 0
                
                # 理想: yaw < 15°, pitch < 10°
                yaw_ok = abs(score.yaw) < 15
                pitch_ok = abs(score.pitch) < 10
                
                if yaw_ok and pitch_ok:
                    score.breakdown["pose_ok"] = SCORE_WEIGHTS["pose_ok"]
                elif abs(score.yaw) < 30 and abs(score.pitch) < 20:
                    score.breakdown["pose_ok"] = SCORE_WEIGHTS["pose_ok"] * 0.6
                else:
                    score.breakdown["pose_ok"] = 0
                    score.flags.append("extreme_pose")
            else:
                # 无姿态信息，给中等分
                score.breakdown["pose_ok"] = SCORE_WEIGHTS["pose_ok"] * 0.5
            
            # 质量评分 (基于检测置信度)
            if score.det_score >= 0.9:
                score.breakdown["quality"] = SCORE_WEIGHTS["quality"]
            elif score.det_score >= 0.7:
                score.breakdown["quality"] = SCORE_WEIGHTS["quality"] * 0.8
            elif score.det_score >= 0.5:
                score.breakdown["quality"] = SCORE_WEIGHTS["quality"] * 0.5
            else:
                score.breakdown["quality"] = 0
                score.flags.append("low_confidence")
            
        except Exception as e:
            logger.error(f"InsightFace scoring failed: {e}")
            score.flags.append("scoring_error")
        
        return score
    
    def _score_with_rules(
        self,
        image_data: bytes,
        image_path: str,
    ) -> CandidateScore:
        """基于规则的简单评分 (无视觉模型)"""
        score = CandidateScore(path=image_path)
        
        # 基于文件大小的粗略评估
        file_size = len(image_data)
        
        if file_size < 10000:  # < 10KB
            score.flags.append("file_too_small")
            score.breakdown = {k: 0 for k in SCORE_WEIGHTS}
        elif file_size < 50000:  # < 50KB
            # 可能质量较低
            score.breakdown = {k: v * 0.5 for k, v in SCORE_WEIGHTS.items()}
        else:
            # 假设正常
            score.breakdown = {k: v * 0.7 for k, v in SCORE_WEIGHTS.items()}
            score.face_detected = True
        
        return score
    
    def select_best(self, candidates: List[CandidateScore]) -> Optional[CandidateScore]:
        """
        从候选中选择最佳
        
        Args:
            candidates: 候选评分列表
            
        Returns:
            最佳候选，如果全部不合格返回 None
        """
        if not candidates:
            return None
        
        # 过滤掉有严重问题的候选
        valid = [c for c in candidates if "multi_face" not in c.flags and c.face_detected]
        
        if not valid:
            # 如果没有有效的，从原列表选最高分
            valid = candidates
        
        # 按总分排序
        sorted_candidates = sorted(valid, key=lambda c: c.total, reverse=True)
        
        best = sorted_candidates[0]
        
        # 记录选择原因
        if len(sorted_candidates) > 1:
            second = sorted_candidates[1]
            margin = best.total - second.total
            logger.info(f"Selected {best.path} (score={best.total:.1f}) over {second.path} (score={second.total:.1f}), margin={margin:.1f}")
        
        return best


# ============ 便捷函数 ============

_scorer: Optional[CandidateScorer] = None


def get_candidate_scorer() -> CandidateScorer:
    """获取评分器单例"""
    global _scorer
    if _scorer is None:
        _scorer = CandidateScorer()
    return _scorer


async def score_and_select(
    candidates: List[Tuple[str, bytes]],  # [(path, image_data), ...]
    character_spec: Optional[Dict[str, Any]] = None,
    style_profile: Optional[str] = None,
) -> Tuple[List[CandidateScore], Optional[CandidateScore]]:
    """
    评分并选择最佳候选
    
    Returns:
        (所有评分, 最佳候选)
    """
    scorer = get_candidate_scorer()
    
    scores = []
    for path, image_data in candidates:
        score = await scorer.score_candidate(image_data, path, character_spec, style_profile)
        scores.append(score)
        logger.info(f"Scored {path}: {score.total:.1f} - {score.notes}")
    
    best = scorer.select_best(scores)
    
    return scores, best
