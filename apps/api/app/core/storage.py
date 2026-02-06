"""
MinIO 对象存储客户端
"""
from minio import Minio
from minio.error import S3Error
from app.core.config import settings
import io
import uuid
from typing import Optional
import logging
import asyncio
from functools import partial

logger = logging.getLogger(__name__)


class StorageClient:
    """MinIO 存储客户端（同步 + 异步支持）"""
    
    def __init__(self, lazy: bool = False):
        self._client = None
        self.bucket = settings.MINIO_BUCKET
        self._available = False
        
        if not lazy:
            self._init_client()
    
    def _init_client(self):
        """初始化 MinIO 客户端"""
        try:
            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            self._ensure_bucket()
            self._available = True
            logger.info(f"MinIO storage connected: {settings.MINIO_ENDPOINT}")
        except Exception as e:
            logger.warning(f"MinIO storage not available: {e}. Storage features disabled.")
            self._available = False
    
    @property
    def client(self):
        """延迟获取客户端"""
        if self._client is None:
            self._init_client()
        return self._client
    
    @property
    def available(self) -> bool:
        """检查存储是否可用"""
        if self._client is None:
            self._init_client()
        return self._available
    
    def _ensure_bucket(self):
        """确保 bucket 存在"""
        try:
            if not self._client.bucket_exists(self.bucket):
                self._client.make_bucket(self.bucket)
                logger.info(f"Created bucket: {self.bucket}")
        except S3Error as e:
            logger.error(f"Failed to create bucket: {e}")
    
    def upload_file(
        self, 
        data: bytes, 
        filename: str, 
        content_type: str = "application/octet-stream",
        folder: str = ""
    ) -> str:
        """
        上传文件
        
        Args:
            data: 文件内容
            filename: 文件名
            content_type: MIME 类型
            folder: 文件夹路径
        
        Returns:
            str: 文件的完整路径
        """
        if not self.available:
            raise RuntimeError("Storage not available")
        
        # 生成唯一文件名
        ext = filename.split(".")[-1] if "." in filename else ""
        unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        
        # 构建完整路径
        object_name = f"{folder}/{unique_name}" if folder else unique_name
        object_name = object_name.lstrip("/")
        
        # 上传
        self.client.put_object(
            self.bucket,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type
        )
        
        return object_name
    
    def download_file(self, object_name: str) -> Optional[bytes]:
        """下载文件"""
        if not self.available:
            return None
        try:
            response = self.client.get_object(self.bucket, object_name)
            return response.read()
        except S3Error as e:
            logger.error(f"Failed to download file {object_name}: {e}")
            return None
        finally:
            if 'response' in locals():
                response.close()
                response.release_conn()
    
    def get_url(self, object_name: str, expires: int = 3600) -> str:
        """获取预签名 URL"""
        if not self.available:
            return ""
        from datetime import timedelta
        return self.client.presigned_get_object(
            self.bucket,
            object_name,
            expires=timedelta(seconds=expires)
        )
    
    def delete_file(self, object_name: str) -> bool:
        """删除文件"""
        if not self.available:
            return False
        try:
            self.client.remove_object(self.bucket, object_name)
            return True
        except S3Error as e:
            logger.error(f"Failed to delete file {object_name}: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> list:
        """列出文件"""
        if not self.available:
            return []
        objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]
    
    def exists(self, object_name: str) -> bool:
        """检查文件是否存在"""
        if not self.available:
            return False
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False
    
    def upload_bytes_sync(
        self,
        path: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        """同步上传字节数据到指定路径"""
        if not self.available:
            raise RuntimeError("Storage not available")
        self.client.put_object(
            self.bucket,
            path,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type
        )
        return path
    
    # ============ 异步方法包装 ============
    
    async def upload_bytes(
        self,
        path: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        """异步上传字节数据"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(self.upload_bytes_sync, path, data, content_type)
        )
    
    async def download_bytes(self, path: str) -> Optional[bytes]:
        """异步下载文件"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(self.download_file, path)
        )
    
    async def delete(self, path: str) -> bool:
        """异步删除文件"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(self.delete_file, path)
        )
    
    async def exists_async(self, path: str) -> bool:
        """异步检查文件是否存在"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(self.exists, path)
        )


# 单例 - 使用延迟初始化
_storage_client: Optional[StorageClient] = None


def get_storage_client() -> StorageClient:
    """获取存储客户端单例"""
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient(lazy=True)  # 延迟初始化
    return _storage_client


# 向后兼容 - 使用延迟初始化的代理
class _LazyStorageClient:
    """延迟初始化的存储客户端代理"""
    def __getattr__(self, name):
        return getattr(get_storage_client(), name)

storage_client = _LazyStorageClient()
