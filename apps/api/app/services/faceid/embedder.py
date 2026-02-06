"""
FaceID Embedder Service
Production MVP: 提取角色 FaceID 并保存到存储

使用流程:
1. 接收参考图 URL/路径
2. 使用 InsightFace 或 Mock 提取 512-d embedding
3. 保存到 MinIO/本地存储
4. 返回 embedding_path
"""
import os
import io
import logging
import uuid
import numpy as np
from typing import Optional, Tuple
from datetime import datetime

from .provider import get_faceid_provider, FaceIDProvider
from app.core.config import settings
from app.services.storage import get_object_store

logger = logging.getLogger(__name__)


async def embed_character_faceid(
    character_id: str,
    reference_image_path: str,
    project_id: str,
    provider_name: str = "auto"
) -> dict:
    """
    Extract FaceID embedding and save to storage.
    
    Args:
        character_id: Character asset ID
        reference_image_path: Path or URL to reference image
        project_id: Project ID for storage organization
        provider_name: "mock", "insightface", or "auto"
        
    Returns:
        {
            "success": bool,
            "embedding_path": str,   # Storage path to .npy file
            "meta": dict,            # Extraction metadata
            "error": str             # Error message if failed
        }
    """
    logger.info(f"[FaceID] Extracting for character {character_id} using {provider_name}")
    
    try:
        # 1. Get provider and extract embedding
        provider = get_faceid_provider(provider_name)
        embedding, meta = provider.extract(reference_image_path)
        
        if embedding is None:
            return {
                "success": False,
                "error": meta.get("error", "No face detected or extraction failed"),
                "meta": meta
            }
        
        # 2. Serialize embedding to bytes
        buffer = io.BytesIO()
        np.save(buffer, embedding)
        buffer.seek(0)
        embedding_bytes = buffer.read()
        
        # 3. Upload to storage
        storage = get_object_store()
        file_name = f"{character_id}.npy"
        storage_key = f"embeddings/{project_id}/{file_name}"
        
        try:
            embedding_url = await storage.upload_file(
                file_content=embedding_bytes,
                key=storage_key,
                content_type="application/octet-stream"
            )
            embedding_path = embedding_url
        except Exception as storage_error:
            # Fallback: return virtual path if storage fails
            logger.warning(f"[FaceID] Storage error, using virtual path: {storage_error}")
            embedding_path = f"/storage/{storage_key}"
        
        # 4. Add metadata
        meta["embedding_shape"] = list(embedding.shape)
        meta["extracted_at"] = datetime.utcnow().isoformat() + "Z"
        meta["character_id"] = character_id
        
        logger.info(f"[FaceID] Successfully extracted embedding for {character_id}: {embedding_path}")
        
        return {
            "success": True,
            "embedding_path": embedding_path,
            "meta": meta
        }
        
    except Exception as e:
        logger.error(f"[FaceID] Error extracting for {character_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def load_embedding(embedding_path: str) -> Optional[np.ndarray]:
    """
    Load embedding from storage path.
    
    Args:
        embedding_path: Storage URL or path to .npy file
        
    Returns:
        512-d numpy array or None
    """
    try:
        storage = get_object_store()
        
        # Download from storage
        data = await storage.download_file(embedding_path)
        buffer = io.BytesIO(data)
        embedding = np.load(buffer)
        
        return embedding
        
    except Exception as e:
        logger.error(f"[FaceID] Failed to load embedding from {embedding_path}: {e}")
        return None


async def compare_embeddings(
    embedding1: np.ndarray,
    embedding2: np.ndarray
) -> float:
    """
    Compare two face embeddings and return similarity score.
    
    Args:
        embedding1: First 512-d embedding
        embedding2: Second 512-d embedding
        
    Returns:
        Cosine similarity score (0-1, higher = more similar)
    """
    # Normalize
    e1 = embedding1 / np.linalg.norm(embedding1)
    e2 = embedding2 / np.linalg.norm(embedding2)
    
    # Cosine similarity
    similarity = float(np.dot(e1, e2))
    
    return max(0.0, min(1.0, similarity))


__all__ = [
    "embed_character_faceid",
    "load_embedding",
    "compare_embeddings",
]
