"""
FaceID Provider Abstraction
Production MVP: 支持 Mock 和真实 InsightFace 提取
"""
import abc
import numpy as np
import os
import logging
from typing import Dict, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class FaceIDProvider(abc.ABC):
    @abc.abstractmethod
    def extract(self, image_path: str) -> Tuple[Optional[np.ndarray], Dict]:
        """
        Extract FaceID embedding from image.
        
        Args:
            image_path: Path to image file or URL
            
        Returns:
            (embedding, meta)
            embedding: 512-d numpy array or None if failed
            meta: dict with details (det_score, bbox, landmarks, error)
        """
        pass


class MockFaceIDProvider(FaceIDProvider):
    """Mock provider for testing"""
    
    def extract(self, image_path: str) -> Tuple[Optional[np.ndarray], Dict]:
        # Return random 512-d vector
        embedding = np.random.rand(512).astype(np.float32)
        meta = {
            "det_score": 0.99,
            "bbox": [100, 100, 200, 200],
            "landmarks_count": 5,
            "model": "mock_v1",
            "provider": "mock"
        }
        logger.info(f"[MockFaceID] Generated mock embedding for {image_path}")
        return embedding, meta


class InsightFaceProvider(FaceIDProvider):
    """
    Real InsightFace provider using insightface library
    
    Requirements:
    - pip install insightface onnxruntime
    - ONNX model files in model path
    """
    
    def __init__(self, model_name: str = "buffalo_l"):
        self.model_name = model_name
        self._app = None
        self._initialized = False
    
    def _initialize(self):
        """Lazy initialization of InsightFace"""
        if self._initialized:
            return
        
        try:
            import insightface
            from insightface.app import FaceAnalysis
            
            # Initialize FaceAnalysis app
            self._app = FaceAnalysis(
                name=self.model_name,
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            self._app.prepare(ctx_id=0, det_size=(640, 640))
            self._initialized = True
            logger.info(f"[InsightFace] Initialized with model {self.model_name}")
            
        except ImportError as e:
            logger.warning(f"[InsightFace] Library not installed: {e}. Falling back to Mock.")
            self._initialized = False
        except Exception as e:
            logger.error(f"[InsightFace] Init error: {e}")
            self._initialized = False
    
    def extract(self, image_path: str) -> Tuple[Optional[np.ndarray], Dict]:
        """Extract face embedding using InsightFace"""
        self._initialize()
        
        # Fallback to Mock if not initialized
        if not self._initialized or self._app is None:
            logger.warning("[InsightFace] Not available, using Mock fallback")
            return MockFaceIDProvider().extract(image_path)
        
        try:
            import cv2
            import httpx
            
            # Load image (support local file or URL)
            if image_path.startswith(('http://', 'https://')):
                # Download from URL
                response = httpx.get(image_path, timeout=30)
                response.raise_for_status()
                img_array = np.frombuffer(response.content, np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            else:
                # Load local file
                img = cv2.imread(image_path)
            
            if img is None:
                return None, {"error": f"Failed to load image: {image_path}"}
            
            # Detect faces
            faces = self._app.get(img)
            
            if len(faces) == 0:
                return None, {"error": "No face detected in image"}
            
            # Use the largest face (by bbox area)
            largest_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            
            embedding = largest_face.embedding  # 512-d vector
            
            meta = {
                "det_score": float(largest_face.det_score),
                "bbox": largest_face.bbox.tolist(),
                "landmarks_count": len(largest_face.landmark_2d_106) if hasattr(largest_face, 'landmark_2d_106') else 5,
                "age": int(largest_face.age) if hasattr(largest_face, 'age') else None,
                "gender": "M" if (hasattr(largest_face, 'gender') and largest_face.gender == 1) else "F" if hasattr(largest_face, 'gender') else None,
                "faces_detected": len(faces),
                "model": self.model_name,
                "provider": "insightface"
            }
            
            logger.info(f"[InsightFace] Extracted embedding from {image_path}, det_score={meta['det_score']:.3f}")
            return embedding.astype(np.float32), meta
            
        except Exception as e:
            logger.error(f"[InsightFace] Extraction error: {e}")
            return None, {"error": str(e)}


def get_faceid_provider(provider_name: str = "auto") -> FaceIDProvider:
    """
    Get FaceID provider by name
    
    Args:
        provider_name: "mock", "insightface", or "auto" (try insightface, fallback to mock)
    """
    if provider_name == "mock":
        return MockFaceIDProvider()
    elif provider_name == "insightface":
        return InsightFaceProvider()
    elif provider_name == "auto":
        # Try insightface, fallback to mock
        try:
            import insightface
            return InsightFaceProvider()
        except ImportError:
            logger.info("[FaceID] InsightFace not available, using Mock")
            return MockFaceIDProvider()
    else:
        return MockFaceIDProvider()
