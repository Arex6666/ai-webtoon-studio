"""
Embedding 存储服务
将 FaceID Embedding 存储到 MinIO
"""
import logging
import io
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.storage import get_storage_client
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingStorage:
    """
    Embedding 存储管理器
    负责将 embedding 文件存储到 MinIO 并管理元数据
    """
    
    EMBEDDING_PREFIX = "embeddings/characters"
    
    def __init__(self):
        self._storage = None
    
    def _get_storage(self):
        """获取存储客户端"""
        if self._storage is None:
            self._storage = get_storage_client()
        return self._storage
    
    def _get_embedding_path(self, character_id: str) -> str:
        """生成 embedding 存储路径"""
        return f"{self.EMBEDDING_PREFIX}/{character_id}/embedding.npy"
    
    def _get_metadata_path(self, character_id: str) -> str:
        """生成元数据存储路径"""
        return f"{self.EMBEDDING_PREFIX}/{character_id}/metadata.json"
    
    async def save_embedding(
        self,
        character_id: str,
        embedding_data: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        保存 embedding 到存储
        
        Args:
            character_id: 角色 ID
            embedding_data: 序列化后的 embedding 数据
            metadata: 额外元数据（来源图片数量、提取时间等）
            
        Returns:
            存储路径
        """
        storage = self._get_storage()
        
        # 存储路径
        embedding_path = self._get_embedding_path(character_id)
        
        try:
            # 上传 embedding 文件
            await storage.upload_bytes(
                path=embedding_path,
                data=embedding_data,
                content_type="application/octet-stream"
            )
            
            logger.info(f"Saved embedding for character {character_id} to {embedding_path}")
            
            # 保存元数据（如果提供）
            if metadata:
                import json
                metadata["saved_at"] = datetime.utcnow().isoformat()
                metadata["embedding_path"] = embedding_path
                
                metadata_path = self._get_metadata_path(character_id)
                await storage.upload_bytes(
                    path=metadata_path,
                    data=json.dumps(metadata).encode("utf-8"),
                    content_type="application/json"
                )
                logger.info(f"Saved metadata for character {character_id}")
            
            return embedding_path
            
        except Exception as e:
            logger.error(f"Failed to save embedding for {character_id}: {e}")
            raise
    
    async def load_embedding(self, character_id: str) -> Optional[bytes]:
        """
        加载 embedding 数据
        
        Args:
            character_id: 角色 ID
            
        Returns:
            序列化的 embedding 数据
        """
        storage = self._get_storage()
        embedding_path = self._get_embedding_path(character_id)
        
        try:
            data = await storage.download_bytes(embedding_path)
            logger.info(f"Loaded embedding for character {character_id}")
            return data
            
        except Exception as e:
            logger.warning(f"Failed to load embedding for {character_id}: {e}")
            return None
    
    async def load_metadata(self, character_id: str) -> Optional[Dict[str, Any]]:
        """加载 embedding 元数据"""
        storage = self._get_storage()
        metadata_path = self._get_metadata_path(character_id)
        
        try:
            import json
            data = await storage.download_bytes(metadata_path)
            return json.loads(data.decode("utf-8"))
            
        except Exception as e:
            logger.warning(f"Failed to load metadata for {character_id}: {e}")
            return None
    
    async def delete_embedding(self, character_id: str) -> bool:
        """
        删除角色的 embedding
        
        Args:
            character_id: 角色 ID
            
        Returns:
            是否删除成功
        """
        storage = self._get_storage()
        
        try:
            embedding_path = self._get_embedding_path(character_id)
            metadata_path = self._get_metadata_path(character_id)
            
            await storage.delete(embedding_path)
            await storage.delete(metadata_path)
            
            logger.info(f"Deleted embedding for character {character_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete embedding for {character_id}: {e}")
            return False
    
    async def exists(self, character_id: str) -> bool:
        """检查角色是否有 embedding"""
        storage = self._get_storage()
        embedding_path = self._get_embedding_path(character_id)
        
        try:
            return await storage.exists(embedding_path)
        except Exception:
            return False
    
    def get_embedding_url(self, character_id: str) -> str:
        """获取 embedding 文件的访问 URL（用于 ComfyUI）"""
        storage = self._get_storage()
        embedding_path = self._get_embedding_path(character_id)
        return storage.get_url(embedding_path)


# 单例实例
_embedding_storage: Optional[EmbeddingStorage] = None


def get_embedding_storage() -> EmbeddingStorage:
    """获取 EmbeddingStorage 单例"""
    global _embedding_storage
    if _embedding_storage is None:
        _embedding_storage = EmbeddingStorage()
    return _embedding_storage
