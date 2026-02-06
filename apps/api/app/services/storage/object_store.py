"""
Object Store - MinIO/S3 统一存储工具

提供文件下载、上传、检查等功能
"""
import os
import io
import logging
import httpx
from typing import Optional, BinaryIO, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ObjectStore:
    """对象存储统一接口"""
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        use_ssl: bool = True
    ):
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "webtoon-studio")
        self.use_ssl = use_ssl
        
        self._client = None
    
    @property
    def client(self):
        """获取 MinIO 客户端（懒加载）"""
        if self._client is None:
            try:
                from minio import Minio
                self._client = Minio(
                    self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=self.use_ssl
                )
            except ImportError:
                logger.warning("minio package not installed, using HTTP fallback")
                self._client = "http_fallback"
        return self._client
    
    def _is_url(self, path: str) -> bool:
        """检查是否是完整 URL"""
        return path.startswith("http://") or path.startswith("https://")
    
    def _get_storage_key(self, url_or_key: str) -> str:
        """从 URL 提取存储 key"""
        if self._is_url(url_or_key):
            parsed = urlparse(url_or_key)
            # 移除 bucket 前缀
            path = parsed.path.lstrip("/")
            if path.startswith(self.bucket + "/"):
                path = path[len(self.bucket) + 1:]
            return path
        return url_or_key
    
    async def download_to_file(self, url_or_key: str, local_path: str) -> None:
        """
        下载文件到本地（流式）
        
        Args:
            url_or_key: MinIO key 或完整 URL
            local_path: 本地保存路径
        """
        # 确保目录存在
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        if self._is_url(url_or_key):
            # HTTP 下载
            await self._http_download(url_or_key, local_path)
        else:
            # MinIO 下载
            await self._minio_download(url_or_key, local_path)
    
    async def _http_download(self, url: str, local_path: str) -> None:
        """HTTP 流式下载"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
    
    async def _minio_download(self, key: str, local_path: str) -> None:
        """MinIO 下载"""
        import asyncio
        
        def _download():
            if self.client == "http_fallback":
                # 构造 URL 进行下载
                url = f"http://{self.endpoint}/{self.bucket}/{key}"
                import requests
                response = requests.get(url, stream=True)
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            else:
                self.client.fget_object(self.bucket, key, local_path)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _download)
    
    async def upload_file(
        self, 
        local_path: str, 
        target_key: str, 
        content_type: Optional[str] = None
    ) -> str:
        """
        上传文件到存储
        
        Args:
            local_path: 本地文件路径
            target_key: 目标存储 key
            content_type: MIME 类型
            
        Returns:
            公开 URL
        """
        import asyncio
        
        if content_type is None:
            content_type = self._guess_content_type(local_path)
        
        def _upload():
            if self.client == "http_fallback":
                logger.warning("HTTP fallback: upload not implemented")
                return f"http://{self.endpoint}/{self.bucket}/{target_key}"
            
            self.client.fput_object(
                self.bucket,
                target_key,
                local_path,
                content_type=content_type
            )
            
            # 返回公开 URL
            protocol = "https" if self.use_ssl else "http"
            return f"{protocol}://{self.endpoint}/{self.bucket}/{target_key}"
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _upload)
    
    async def upload_bytes(
        self,
        data: bytes,
        target_key: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        上传字节数据
        
        Args:
            data: 字节数据
            target_key: 目标存储 key
            content_type: MIME 类型
            
        Returns:
            公开 URL
        """
        import asyncio
        
        def _upload():
            if self.client == "http_fallback":
                logger.warning("HTTP fallback: upload not implemented")
                return f"http://{self.endpoint}/{self.bucket}/{target_key}"
            
            data_stream = io.BytesIO(data)
            self.client.put_object(
                self.bucket,
                target_key,
                data_stream,
                length=len(data),
                content_type=content_type
            )
            
            protocol = "https" if self.use_ssl else "http"
            return f"{protocol}://{self.endpoint}/{self.bucket}/{target_key}"
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _upload)
    
    async def exists(self, url_or_key: str) -> bool:
        """检查文件是否存在"""
        import asyncio
        
        if self._is_url(url_or_key):
            # HTTP HEAD 请求
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.head(url_or_key)
                    return response.status_code == 200
            except Exception:
                return False
        else:
            # MinIO stat
            def _check():
                try:
                    if self.client == "http_fallback":
                        return True  # 假设存在
                    self.client.stat_object(self.bucket, url_or_key)
                    return True
                except Exception:
                    return False
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _check)
    
    async def get_file_info(self, url_or_key: str) -> Optional[dict]:
        """获取文件信息"""
        import asyncio
        
        key = self._get_storage_key(url_or_key)
        
        def _get_info():
            try:
                if self.client == "http_fallback":
                    return {"size": 0, "content_type": "application/octet-stream"}
                stat = self.client.stat_object(self.bucket, key)
                return {
                    "size": stat.size,
                    "content_type": stat.content_type,
                    "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                    "etag": stat.etag
                }
            except Exception as e:
                logger.warning(f"Failed to get file info: {e}")
                return None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_info)
    
    def _guess_content_type(self, path: str) -> str:
        """根据扩展名猜测 MIME 类型"""
        ext = os.path.splitext(path)[1].lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".json": "application/json",
            ".zip": "application/zip",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".txt": "text/plain",
        }
        return content_types.get(ext, "application/octet-stream")


# 全局单例
_object_store: Optional[ObjectStore] = None


def get_object_store() -> ObjectStore:
    """获取对象存储实例"""
    global _object_store
    if _object_store is None:
        _object_store = ObjectStore()
    return _object_store
