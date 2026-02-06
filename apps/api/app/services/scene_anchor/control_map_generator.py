"""
控制图生成器
生成 Depth Map、Canny Edge、Lineart 等控制图
用于 ControlNet 锁定场景结构
"""
import logging
import numpy as np
from typing import Optional, Dict, Tuple
from PIL import Image
import io

logger = logging.getLogger(__name__)


class ControlMapGenerator:
    """
    控制图生成器
    支持生成多种类型的控制图用于场景一致性锁定
    """
    
    def __init__(self):
        self._depth_estimator = None
        self._lineart_detector = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """延迟初始化（首次使用时加载模型）"""
        if self._initialized:
            return
        
        # 尝试加载高级模型，失败则使用基础方法
        try:
            # 尝试加载 controlnet_aux 的处理器
            from controlnet_aux import MidasDetector, LineartDetector
            self._depth_estimator = MidasDetector.from_pretrained("lllyasviel/Annotators")
            self._lineart_detector = LineartDetector.from_pretrained("lllyasviel/Annotators")
            logger.info("Loaded controlnet_aux processors")
        except ImportError:
            logger.warning("controlnet_aux not available, using basic methods")
        except Exception as e:
            logger.warning(f"Failed to load controlnet_aux: {e}, using basic methods")
        
        self._initialized = True
    
    def generate_canny(
        self, 
        image_data: bytes,
        low_threshold: int = 100,
        high_threshold: int = 200
    ) -> bytes:
        """
        生成 Canny 边缘图
        
        Args:
            image_data: 输入图像数据
            low_threshold: Canny 低阈值
            high_threshold: Canny 高阈值
            
        Returns:
            PNG 格式的边缘图
        """
        import cv2
        
        # 解码图像
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Failed to decode image")
        
        # 转灰度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 高斯模糊降噪
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Canny 边缘检测
        edges = cv2.Canny(blurred, low_threshold, high_threshold)
        
        # 转换为 RGB（白色边缘，黑色背景）
        edges_rgb = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
        
        # 编码为 PNG
        _, buffer = cv2.imencode('.png', edges_rgb)
        return buffer.tobytes()
    
    def generate_depth(self, image_data: bytes) -> bytes:
        """
        生成深度图
        
        Args:
            image_data: 输入图像数据
            
        Returns:
            PNG 格式的深度图
        """
        self._ensure_initialized()
        
        # 解码图像
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        if self._depth_estimator is not None:
            # 使用 MiDaS 模型
            try:
                depth_map = self._depth_estimator(img)
                
                # 转换为 bytes
                buffer = io.BytesIO()
                depth_map.save(buffer, format="PNG")
                return buffer.getvalue()
            except Exception as e:
                logger.warning(f"MiDaS depth estimation failed: {e}, using basic method")
        
        # 基础方法：使用灰度图近似深度
        logger.info("Using basic depth estimation (grayscale)")
        import cv2
        
        nparr = np.frombuffer(image_data, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 转灰度作为伪深度
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # 应用高斯模糊平滑
        depth = cv2.GaussianBlur(gray, (15, 15), 0)
        
        # 归一化到 0-255
        depth = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX)
        
        # 转 RGB
        depth_rgb = cv2.cvtColor(depth, cv2.COLOR_GRAY2RGB)
        
        _, buffer = cv2.imencode('.png', depth_rgb)
        return buffer.tobytes()
    
    def generate_lineart(self, image_data: bytes) -> bytes:
        """
        生成线稿图
        
        Args:
            image_data: 输入图像数据
            
        Returns:
            PNG 格式的线稿图
        """
        self._ensure_initialized()
        
        # 解码图像
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        if self._lineart_detector is not None:
            # 使用专业线稿检测器
            try:
                lineart = self._lineart_detector(img)
                
                buffer = io.BytesIO()
                lineart.save(buffer, format="PNG")
                return buffer.getvalue()
            except Exception as e:
                logger.warning(f"Lineart detection failed: {e}, using basic method")
        
        # 基础方法：使用边缘检测 + 反色
        logger.info("Using basic lineart extraction")
        import cv2
        
        nparr = np.frombuffer(image_data, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 转灰度
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # 反色
        inverted = 255 - gray
        
        # 高斯模糊
        blurred = cv2.GaussianBlur(inverted, (21, 21), 0)
        
        # 颜色减淡混合
        lineart = cv2.divide(gray, 255 - blurred, scale=256.0)
        
        # 增强对比度
        lineart = cv2.normalize(lineart, None, 0, 255, cv2.NORM_MINMAX)
        
        # 转 RGB
        lineart_rgb = cv2.cvtColor(lineart, cv2.COLOR_GRAY2RGB)
        
        _, buffer = cv2.imencode('.png', lineart_rgb)
        return buffer.tobytes()
    
    def generate_all(
        self, 
        image_data: bytes
    ) -> Dict[str, bytes]:
        """
        生成所有控制图
        
        Args:
            image_data: 输入图像数据
            
        Returns:
            包含所有控制图的字典 {type: image_data}
        """
        result = {}
        
        try:
            result["canny"] = self.generate_canny(image_data)
            logger.info("Generated canny edge map")
        except Exception as e:
            logger.error(f"Failed to generate canny: {e}")
        
        try:
            result["depth"] = self.generate_depth(image_data)
            logger.info("Generated depth map")
        except Exception as e:
            logger.error(f"Failed to generate depth: {e}")
        
        try:
            result["lineart"] = self.generate_lineart(image_data)
            logger.info("Generated lineart map")
        except Exception as e:
            logger.error(f"Failed to generate lineart: {e}")
        
        return result
    
    def get_image_size(self, image_data: bytes) -> Tuple[int, int]:
        """获取图像尺寸"""
        img = Image.open(io.BytesIO(image_data))
        return img.size  # (width, height)


# 单例实例
_control_map_generator: Optional[ControlMapGenerator] = None


def get_control_map_generator() -> ControlMapGenerator:
    """获取 ControlMapGenerator 单例"""
    global _control_map_generator
    if _control_map_generator is None:
        _control_map_generator = ControlMapGenerator()
    return _control_map_generator
