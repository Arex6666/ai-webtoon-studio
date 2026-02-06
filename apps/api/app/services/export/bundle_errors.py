"""
Bundle Errors - 导出错误类型

提供精确的错误定位信息
"""
from typing import Optional, Dict, Any


class BundleBuildError(Exception):
    """Bundle 构建基础错误"""
    
    def __init__(
        self, 
        code: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        panel_index: Optional[str] = None
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.panel_index = panel_index
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "panel_index": self.panel_index
        }


class MissingArtifactError(BundleBuildError):
    """缺少必要产物"""
    
    def __init__(
        self, 
        panel_index: str, 
        artifact_name: str, 
        expected_path_or_key: Optional[str] = None
    ):
        super().__init__(
            code="MISSING_ARTIFACT",
            message=f"Panel {panel_index} 缺少 {artifact_name}",
            details={
                "artifact_name": artifact_name,
                "expected_path": expected_path_or_key
            },
            panel_index=panel_index
        )
        self.artifact_name = artifact_name
        self.expected_path_or_key = expected_path_or_key


class CorruptManifestError(BundleBuildError):
    """清单文件损坏或无法解析"""
    
    def __init__(
        self, 
        panel_index: str, 
        manifest_url: str, 
        reason: str
    ):
        super().__init__(
            code="CORRUPT_MANIFEST",
            message=f"Panel {panel_index} 的 LayerPack manifest 无法解析: {reason}",
            details={
                "manifest_url": manifest_url,
                "reason": reason
            },
            panel_index=panel_index
        )
        self.manifest_url = manifest_url
        self.reason = reason


class DownloadError(BundleBuildError):
    """文件下载失败"""
    
    def __init__(
        self, 
        url_or_key: str, 
        reason: str,
        panel_index: Optional[str] = None
    ):
        super().__init__(
            code="DOWNLOAD_ERROR",
            message=f"下载失败: {url_or_key} - {reason}",
            details={
                "url_or_key": url_or_key,
                "reason": reason
            },
            panel_index=panel_index
        )
        self.url_or_key = url_or_key
        self.reason = reason


class UploadError(BundleBuildError):
    """文件上传失败"""
    
    def __init__(
        self, 
        target_key: str, 
        reason: str
    ):
        super().__init__(
            code="UPLOAD_ERROR",
            message=f"上传失败: {target_key} - {reason}",
            details={
                "target_key": target_key,
                "reason": reason
            }
        )
        self.target_key = target_key
        self.reason = reason


class GateRejectedError(BundleBuildError):
    """导出门禁拒绝"""
    
    def __init__(
        self, 
        reason: str, 
        panel_index: Optional[str] = None,
        gate_result: Optional[Dict] = None
    ):
        super().__init__(
            code="GATE_REJECTED",
            message=f"导出门禁拒绝: {reason}",
            details={
                "reason": reason,
                "gate_result": gate_result
            },
            panel_index=panel_index
        )
        self.reason = reason
        self.gate_result = gate_result


class ChapterNotFoundError(BundleBuildError):
    """章节不存在"""
    
    def __init__(self, chapter_id: str):
        super().__init__(
            code="CHAPTER_NOT_FOUND",
            message=f"章节不存在: {chapter_id}",
            details={"chapter_id": chapter_id}
        )
        self.chapter_id = chapter_id


class NoPanelsError(BundleBuildError):
    """章节没有面板"""
    
    def __init__(self, chapter_id: str):
        super().__init__(
            code="NO_PANELS",
            message=f"章节 {chapter_id} 没有任何面板",
            details={"chapter_id": chapter_id}
        )
        self.chapter_id = chapter_id


class NoLayerPackError(BundleBuildError):
    """面板没有可用的 LayerPack"""
    
    def __init__(self, panel_index: str, panel_id: str):
        super().__init__(
            code="NO_LAYERPACK",
            message=f"Panel {panel_index} 没有可用的 LayerPack",
            details={"panel_id": panel_id},
            panel_index=panel_index
        )
        self.panel_id = panel_id
