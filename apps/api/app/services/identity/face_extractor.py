"""
FaceID Embedding 提取服务
使用 InsightFace 提取人脸特征向量
"""
import logging
import numpy as np
from typing import Optional, List, Tuple
from pathlib import Path
import io

logger = logging.getLogger(__name__)


class FaceExtractor:
    """
    人脸特征提取器
    使用 InsightFace 的 buffalo_l 模型提取 512 维 FaceID embedding
    """
    
    def __init__(self):
        self._app = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """延迟初始化 InsightFace（首次使用时加载模型）"""
        if self._initialized:
            return
        
        try:
            from insightface.app import FaceAnalysis
            
            # 使用 buffalo_l 模型（精度高，适合角色一致性）
            self._app = FaceAnalysis(
                name="buffalo_l",
                providers=["CPUExecutionProvider"]  # 可改为 CUDAExecutionProvider
            )
            self._app.prepare(ctx_id=0, det_size=(640, 640))
            self._initialized = True
            logger.info("FaceExtractor initialized with buffalo_l model")
            
        except ImportError:
            logger.warning("InsightFace not installed, using mock extractor")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize FaceExtractor: {e}")
            raise
    
    def extract_embedding(
        self, 
        image_data: bytes,
        return_bbox: bool = False
    ) -> Tuple[Optional[np.ndarray], Optional[dict]]:
        """
        从图像中提取人脸 embedding
        
        Args:
            image_data: 图像二进制数据 (PNG/JPG)
            return_bbox: 是否返回人脸边界框
            
        Returns:
            (embedding, bbox_info) - embedding 是 512 维向量，bbox_info 包含位置信息
        """
        self._ensure_initialized()
        
        if self._app is None:
            # Mock 模式：返回随机 embedding
            logger.warning("Using mock embedding (InsightFace not available)")
            mock_embedding = np.random.randn(512).astype(np.float32)
            mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
            return mock_embedding, {"mock": True}
        
        try:
            import cv2
            
            # 解码图像
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                logger.error("Failed to decode image")
                return None, None
            
            # 检测人脸并提取特征
            faces = self._app.get(img)
            
            if len(faces) == 0:
                logger.warning("No face detected in image")
                return None, None
            
            if len(faces) > 1:
                logger.info(f"Multiple faces detected ({len(faces)}), using largest one")
            
            # 选择最大的人脸（按面积）
            face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            
            # 归一化 embedding
            embedding = face.embedding
            embedding = embedding / np.linalg.norm(embedding)
            
            bbox_info = None
            if return_bbox:
                bbox_info = {
                    "bbox": face.bbox.tolist(),
                    "det_score": float(face.det_score),
                    "landmark": face.landmark_2d_106.tolist() if face.landmark_2d_106 is not None else None
                }
            
            logger.info(f"Extracted embedding with shape {embedding.shape}, det_score={face.det_score:.3f}")
            return embedding.astype(np.float32), bbox_info
            
        except Exception as e:
            logger.error(f"Failed to extract embedding: {e}")
            return None, None
    
    def extract_from_multiple(
        self, 
        images: List[bytes]
    ) -> Optional[np.ndarray]:
        """
        从多张图像提取并平均 embedding（提高稳定性）
        建议使用：正面照 + 侧面照 + 多种表情
        
        Args:
            images: 图像二进制数据列表
            
        Returns:
            平均后的 embedding 向量
        """
        embeddings = []
        
        for i, img_data in enumerate(images):
            emb, _ = self.extract_embedding(img_data)
            if emb is not None:
                embeddings.append(emb)
                logger.info(f"Extracted embedding from image {i+1}/{len(images)}")
            else:
                logger.warning(f"Failed to extract from image {i+1}/{len(images)}")
        
        if len(embeddings) == 0:
            logger.error("No valid embeddings extracted from any image")
            return None
        
        # 平均所有 embedding
        avg_embedding = np.mean(embeddings, axis=0)
        avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)
        
        logger.info(f"Averaged {len(embeddings)} embeddings into final embedding")
        return avg_embedding.astype(np.float32)
    
    def compute_similarity(
        self, 
        embedding1: np.ndarray, 
        embedding2: np.ndarray
    ) -> float:
        """
        计算两个 embedding 的相似度（余弦相似度）
        
        Args:
            embedding1: 第一个 embedding
            embedding2: 第二个 embedding
            
        Returns:
            相似度分数 [0, 1]，越高越相似
        """
        # 确保归一化
        e1 = embedding1 / np.linalg.norm(embedding1)
        e2 = embedding2 / np.linalg.norm(embedding2)
        
        # 余弦相似度
        similarity = np.dot(e1, e2)
        
        # 映射到 [0, 1]
        return float((similarity + 1) / 2)
    
    def serialize_embedding(self, embedding: np.ndarray) -> bytes:
        """将 embedding 序列化为字节（用于存储）"""
        buffer = io.BytesIO()
        np.save(buffer, embedding)
        return buffer.getvalue()
    
    def deserialize_embedding(self, data: bytes) -> np.ndarray:
        """从字节反序列化 embedding"""
        buffer = io.BytesIO(data)
        return np.load(buffer)


# 单例实例
_face_extractor: Optional[FaceExtractor] = None


def get_face_extractor() -> FaceExtractor:
    """获取 FaceExtractor 单例"""
    global _face_extractor
    if _face_extractor is None:
        _face_extractor = FaceExtractor()
    return _face_extractor
