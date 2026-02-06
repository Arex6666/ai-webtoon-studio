"""
QA 检测服务 - 图像质量自动检测
"""
import io
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import httpx

logger = logging.getLogger(__name__)


class QAIssueLevel(str, Enum):
    """问题严重等级"""
    ERROR = "error"       # 必须修复
    WARNING = "warning"   # 建议修复
    INFO = "info"         # 仅供参考


@dataclass
class QAIssue:
    """QA 问题"""
    code: str
    level: QAIssueLevel
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class QAReport:
    """QA 报告"""
    passed: bool
    score: float  # 0-1
    issues: List[QAIssue]
    checks_performed: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "issues": [asdict(i) for i in self.issues],
            "checks_performed": self.checks_performed,
        }


class ImageQAService:
    """图像质量检测服务"""
    
    # QA 阈值配置
    MIN_WIDTH = 1080
    MIN_HEIGHT = 1920
    BLACK_THRESHOLD = 10      # 黑图阈值（平均亮度）
    WHITE_THRESHOLD = 245     # 过曝阈值（平均亮度）
    BLUR_THRESHOLD = 100      # 模糊阈值（Laplacian 方差）
    MIN_ENTROPY = 4.0         # 最小熵值（检测空图）
    
    def __init__(self):
        self.checks = [
            self._check_resolution,
            self._check_black_image,
            self._check_overexposed,
            self._check_blur,
            self._check_entropy,
        ]
    
    async def analyze(self, image_url: str) -> QAReport:
        """
        分析图片质量
        
        Args:
            image_url: 图片 URL
        
        Returns:
            QAReport
        """
        issues: List[QAIssue] = []
        checks_performed: List[str] = []
        
        try:
            # 下载图片
            image_data = await self._download_image(image_url)
            if image_data is None:
                issues.append(QAIssue(
                    code="DOWNLOAD_FAILED",
                    level=QAIssueLevel.ERROR,
                    message="无法下载图片"
                ))
                return QAReport(passed=False, score=0, issues=issues, checks_performed=checks_performed)
            
            # 分析图片
            image_info = self._analyze_image(image_data)
            
            # 执行所有检查
            for check in self.checks:
                check_name, check_issues = check(image_info)
                checks_performed.append(check_name)
                issues.extend(check_issues)
            
            # 计算得分
            error_count = sum(1 for i in issues if i.level == QAIssueLevel.ERROR)
            warning_count = sum(1 for i in issues if i.level == QAIssueLevel.WARNING)
            
            if error_count > 0:
                score = 0.0
                passed = False
            elif warning_count > 0:
                score = max(0.5, 1.0 - warning_count * 0.1)
                passed = True
            else:
                score = 1.0
                passed = True
            
            return QAReport(
                passed=passed,
                score=score,
                issues=issues,
                checks_performed=checks_performed
            )
            
        except Exception as e:
            logger.error(f"QA analysis failed: {e}")
            issues.append(QAIssue(
                code="ANALYSIS_ERROR",
                level=QAIssueLevel.ERROR,
                message=f"分析失败: {str(e)}"
            ))
            return QAReport(passed=False, score=0, issues=issues, checks_performed=checks_performed)
    
    async def _download_image(self, url: str) -> Optional[bytes]:
        """下载图片"""
        try:
            # 跳过占位符 URL
            if "example.com" in url or "picsum.photos" in url:
                # 返回模拟数据
                return b"MOCK_IMAGE"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.content
                return None
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")
            return None
    
    def _analyze_image(self, image_data: bytes) -> Dict[str, Any]:
        """分析图片基本属性"""
        # 简化实现，实际应使用 Pillow 或 OpenCV
        # 这里返回模拟数据
        if image_data == b"MOCK_IMAGE":
            return {
                "width": 1080,
                "height": 1920,
                "mean_brightness": 128,
                "laplacian_var": 500,
                "entropy": 7.0,
                "is_mock": True,
            }
        
        try:
            from PIL import Image
            import numpy as np
            
            img = Image.open(io.BytesIO(image_data))
            img_array = np.array(img.convert("RGB"))
            
            # 基本尺寸
            width, height = img.size
            
            # 平均亮度
            gray = np.mean(img_array, axis=2)
            mean_brightness = np.mean(gray)
            
            # Laplacian 方差（模糊检测）
            # 简化：使用梯度方差
            gx = np.gradient(gray, axis=0)
            gy = np.gradient(gray, axis=1)
            laplacian_var = np.var(gx) + np.var(gy)
            
            # 熵值
            hist, _ = np.histogram(gray.flatten(), bins=256, range=(0, 256))
            hist = hist / hist.sum()
            hist = hist[hist > 0]
            entropy = -np.sum(hist * np.log2(hist))
            
            return {
                "width": width,
                "height": height,
                "mean_brightness": mean_brightness,
                "laplacian_var": laplacian_var,
                "entropy": entropy,
                "is_mock": False,
            }
            
        except Exception as e:
            logger.warning(f"Image analysis failed: {e}")
            return {
                "width": 0,
                "height": 0,
                "mean_brightness": 128,
                "laplacian_var": 500,
                "entropy": 7.0,
                "is_mock": True,
            }
    
    def _check_resolution(self, info: Dict) -> Tuple[str, List[QAIssue]]:
        """检查分辨率"""
        issues = []
        width = info.get("width", 0)
        height = info.get("height", 0)
        
        if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
            issues.append(QAIssue(
                code="LOW_RESOLUTION",
                level=QAIssueLevel.ERROR,
                message=f"分辨率过低: {width}x{height}，需要 {self.MIN_WIDTH}x{self.MIN_HEIGHT}",
                details={"width": width, "height": height}
            ))
        
        return "resolution", issues
    
    def _check_black_image(self, info: Dict) -> Tuple[str, List[QAIssue]]:
        """检查黑图"""
        issues = []
        brightness = info.get("mean_brightness", 128)
        
        if brightness < self.BLACK_THRESHOLD:
            issues.append(QAIssue(
                code="BLACK_IMAGE",
                level=QAIssueLevel.ERROR,
                message=f"检测到黑图（亮度: {brightness:.1f}）",
                details={"brightness": brightness}
            ))
        
        return "black_image", issues
    
    def _check_overexposed(self, info: Dict) -> Tuple[str, List[QAIssue]]:
        """检查过曝"""
        issues = []
        brightness = info.get("mean_brightness", 128)
        
        if brightness > self.WHITE_THRESHOLD:
            issues.append(QAIssue(
                code="OVEREXPOSED",
                level=QAIssueLevel.WARNING,
                message=f"图片可能过曝（亮度: {brightness:.1f}）",
                details={"brightness": brightness}
            ))
        
        return "overexposed", issues
    
    def _check_blur(self, info: Dict) -> Tuple[str, List[QAIssue]]:
        """检查模糊"""
        issues = []
        laplacian_var = info.get("laplacian_var", 500)
        
        if laplacian_var < self.BLUR_THRESHOLD:
            issues.append(QAIssue(
                code="BLURRY",
                level=QAIssueLevel.WARNING,
                message=f"图片可能模糊（清晰度: {laplacian_var:.1f}）",
                details={"sharpness": laplacian_var}
            ))
        
        return "blur", issues
    
    def _check_entropy(self, info: Dict) -> Tuple[str, List[QAIssue]]:
        """检查熵（空图检测）"""
        issues = []
        entropy = info.get("entropy", 7.0)
        
        if entropy < self.MIN_ENTROPY:
            issues.append(QAIssue(
                code="LOW_ENTROPY",
                level=QAIssueLevel.WARNING,
                message=f"图片内容可能过于单一（熵: {entropy:.2f}）",
                details={"entropy": entropy}
            ))
        
        return "entropy", issues


# 全局实例
_qa_service: Optional[ImageQAService] = None


def get_qa_service() -> ImageQAService:
    """获取 QA 服务单例"""
    global _qa_service
    if _qa_service is None:
        _qa_service = ImageQAService()
    return _qa_service
