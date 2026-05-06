"""
场景锚点存储服务
将空镜图像和控制图打包存储到 MinIO
"""
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.core.storage import get_storage_client

logger = logging.getLogger(__name__)


class AnchorStorage:
    """
    场景锚点存储管理器
    存储空镜底图及其对应的控制图（Depth/Canny/Lineart）
    """
    
    ANCHOR_PREFIX = "anchors/scenes"
    
    def __init__(self):
        self._storage = None
    
    def _get_storage(self):
        """获取存储客户端"""
        if self._storage is None:
            self._storage = get_storage_client()
        return self._storage
    
    def _get_base_path(self, scene_id: str) -> str:
        """获取场景的基础存储路径"""
        return f"{self.ANCHOR_PREFIX}/{scene_id}"
    
    def _get_anchor_image_path(self, scene_id: str) -> str:
        """获取空镜图像路径"""
        return f"{self._get_base_path(scene_id)}/anchor.png"
    
    def _get_control_map_path(self, scene_id: str, map_type: str) -> str:
        """获取控制图路径"""
        return f"{self._get_base_path(scene_id)}/{map_type}.png"
    
    def _get_metadata_path(self, scene_id: str) -> str:
        """获取元数据路径"""
        return f"{self._get_base_path(scene_id)}/metadata.json"
    
    async def save_anchor(
        self,
        scene_id: str,
        anchor_image: bytes,
        control_maps: Dict[str, bytes],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        保存场景锚点（空镜 + 控制图）
        
        Args:
            scene_id: 场景 ID
            anchor_image: 空镜图像数据
            control_maps: 控制图字典 {"depth": bytes, "canny": bytes, "lineart": bytes}
            metadata: 额外元数据
            
        Returns:
            存储路径字典
        """
        storage = self._get_storage()
        paths = {}
        
        try:
            # 保存空镜图像
            anchor_path = self._get_anchor_image_path(scene_id)
            await storage.upload_bytes(
                path=anchor_path,
                data=anchor_image,
                content_type="image/png"
            )
            paths["anchor"] = anchor_path
            logger.info(f"Saved anchor image for scene {scene_id}")
            
            # 保存各种控制图
            for map_type, map_data in control_maps.items():
                map_path = self._get_control_map_path(scene_id, map_type)
                await storage.upload_bytes(
                    path=map_path,
                    data=map_data,
                    content_type="image/png"
                )
                paths[map_type] = map_path
                logger.info(f"Saved {map_type} control map for scene {scene_id}")
            
            # 保存元数据
            meta = metadata or {}
            meta["saved_at"] = datetime.utcnow().isoformat()
            meta["paths"] = paths
            meta["control_map_types"] = list(control_maps.keys())
            
            metadata_path = self._get_metadata_path(scene_id)
            await storage.upload_bytes(
                path=metadata_path,
                data=json.dumps(meta).encode("utf-8"),
                content_type="application/json"
            )
            
            logger.info(f"Saved complete scene anchor for {scene_id}")
            return paths
            
        except Exception as e:
            logger.error(f"Failed to save anchor for {scene_id}: {e}")
            raise

    async def save_control_map(self, scene_id: str, map_type: str, data: bytes) -> str:
        """Upload a single control map PNG to MinIO. Returns the storage path.

        Used when control maps are extracted incrementally (one map at a time)
        rather than batched up-front. Counterpart to the all-in-one save_anchor.
        """
        storage = self._get_storage()
        path = self._get_control_map_path(scene_id, map_type)
        await storage.upload_bytes(
            path=path,
            data=data,
            content_type="image/png",
        )
        logger.info(f"Saved {map_type} control map for scene {scene_id}")
        return path

    async def load_anchor_image(self, scene_id: str) -> Optional[bytes]:
        """加载空镜图像"""
        storage = self._get_storage()
        path = self._get_anchor_image_path(scene_id)
        
        try:
            return await storage.download_bytes(path)
        except Exception as e:
            logger.warning(f"Failed to load anchor image for {scene_id}: {e}")
            return None
    
    async def load_control_map(self, scene_id: str, map_type: str) -> Optional[bytes]:
        """加载指定类型的控制图"""
        storage = self._get_storage()
        path = self._get_control_map_path(scene_id, map_type)
        
        try:
            return await storage.download_bytes(path)
        except Exception as e:
            logger.warning(f"Failed to load {map_type} map for {scene_id}: {e}")
            return None
    
    async def load_all_control_maps(self, scene_id: str) -> Dict[str, bytes]:
        """加载所有控制图"""
        result = {}
        
        for map_type in ["depth", "canny", "lineart"]:
            data = await self.load_control_map(scene_id, map_type)
            if data:
                result[map_type] = data
        
        return result
    
    async def load_metadata(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """加载元数据"""
        storage = self._get_storage()
        path = self._get_metadata_path(scene_id)
        
        try:
            data = await storage.download_bytes(path)
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load metadata for {scene_id}: {e}")
            return None
    
    async def delete_anchor(self, scene_id: str) -> bool:
        """删除场景的所有锚点数据"""
        storage = self._get_storage()
        
        try:
            # 删除所有文件
            files_to_delete = [
                self._get_anchor_image_path(scene_id),
                self._get_metadata_path(scene_id),
            ]
            
            for map_type in ["depth", "canny", "lineart"]:
                files_to_delete.append(self._get_control_map_path(scene_id, map_type))
            
            for path in files_to_delete:
                try:
                    await storage.delete(path)
                except Exception:
                    pass  # 文件可能不存在
            
            logger.info(f"Deleted anchor for scene {scene_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete anchor for {scene_id}: {e}")
            return False
    
    async def exists(self, scene_id: str) -> bool:
        """检查场景是否有锚点"""
        storage = self._get_storage()
        path = self._get_anchor_image_path(scene_id)
        
        try:
            return await storage.exists_async(path)
        except Exception:
            return False
    
    def get_anchor_url(self, scene_id: str) -> str:
        """获取空镜图像的访问 URL"""
        storage = self._get_storage()
        path = self._get_anchor_image_path(scene_id)
        return storage.get_url(path)
    
    def get_control_map_url(self, scene_id: str, map_type: str) -> str:
        """获取控制图的访问 URL"""
        storage = self._get_storage()
        path = self._get_control_map_path(scene_id, map_type)
        return storage.get_url(path)
    
    def get_all_urls(self, scene_id: str) -> Dict[str, str]:
        """获取所有文件的访问 URL"""
        return {
            "anchor": self.get_anchor_url(scene_id),
            "depth": self.get_control_map_url(scene_id, "depth"),
            "canny": self.get_control_map_url(scene_id, "canny"),
            "lineart": self.get_control_map_url(scene_id, "lineart"),
        }


# 单例实例
_anchor_storage: Optional[AnchorStorage] = None


def get_anchor_storage() -> AnchorStorage:
    """获取 AnchorStorage 单例"""
    global _anchor_storage
    if _anchor_storage is None:
        _anchor_storage = AnchorStorage()
    return _anchor_storage
