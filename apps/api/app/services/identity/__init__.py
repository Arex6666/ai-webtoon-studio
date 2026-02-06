"""
Identity Service - 角色一致性管理
包含 FaceID Embedding 提取和存储
"""
from .face_extractor import FaceExtractor, get_face_extractor
from .embedding_storage import EmbeddingStorage, get_embedding_storage

__all__ = [
    "FaceExtractor",
    "get_face_extractor",
    "EmbeddingStorage",
    "get_embedding_storage",
]
