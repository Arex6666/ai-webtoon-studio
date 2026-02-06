"""
Doubao Asset Generator - 使用豆包 Seedream 生成资产参考图

为角色生成定妆照、为场景生成空镜图
"""
import logging
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from app.core.config import settings
from app.services.layer_factory.doubao_image_provider import (
    DoubaoImageProvider,
    DoubaoImageRequest,
    DoubaoImageResult,
    get_doubao_image_provider,
)
from app.services.storage import get_object_store
from app.services.identity import get_face_extractor, get_embedding_storage
from app.models.asset import Asset
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class CharacterInfo:
    """角色信息"""
    name: str
    gender: Optional[str] = None  # male/female
    age_range: Optional[str] = None  # 年龄描述
    appearance_keywords: List[str] = None  # 外貌关键词
    personality_keywords: List[str] = None  # 性格关键词


@dataclass
class SceneInfo:
    """场景信息"""
    name: str
    description: str  # 环境描述
    time_of_day: Optional[str] = None  # 时间
    lighting: Optional[str] = None  # 光照
    mood: Optional[str] = None  # 氛围


class DoubaoAssetGenerator:
    """
    使用豆包 Seedream 生成资产参考图
    
    - 角色定妆照: 正面半身像, 清晰脸部
    - 场景空镜图: 无人背景, 适合控制图提取
    """
    
    def __init__(self):
        self.provider = get_doubao_image_provider()
        self.storage = get_object_store()
    
    async def generate_character_portrait(
        self,
        character: CharacterInfo,
        project_id: str,
        asset_id: Optional[str] = None,
        style_hint: str = "韩漫风格"
    ) -> Dict[str, Any]:
        """
        为角色生成定妆照
        
        Args:
            character: 角色信息
            project_id: 项目ID
            asset_id: 资产ID (可选)
            style_hint: 风格提示
        
        Returns:
            {
                "success": bool,
                "image_url": str,
                "thumbnail_url": str,
                "embedding_path": str,  # FaceID 路径
                "error": str
            }
        """
        result = {
            "success": False,
            "image_url": None,
            "thumbnail_url": None,
            "embedding_path": None,
            "error": None,
        }
        
        if not self.provider:
            result["error"] = "豆包服务未配置 (ARK_API_KEY 或 DOUBAO_API_KEY)"
            return result
        
        try:
            # 构建角色定妆照 prompt
            prompt = self._build_character_prompt(character, style_hint)
            negative_prompt = self._get_character_negative_prompt()
            
            logger.info(f"[DoubaoAsset] Generating portrait for {character.name}")
            logger.info(f"[DoubaoAsset] Prompt: {prompt[:200]}...")
            
            # 调用豆包 Seedream 生成 (最小像素要求: 3,686,400)
            request = DoubaoImageRequest(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=1440,
                height=2560,  # 9:16 portrait, 3,686,400 pixels
            )
            
            gen_result = await self.provider.generate(request)
            
            if not gen_result.success:
                result["error"] = gen_result.error
                return result
            
            image_url = gen_result.image_url
            
            # 上传到存储
            if self.storage and image_url:
                try:
                    # 下载图片
                    import httpx
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(image_url)
                        image_data = resp.content
                    
                    # 上传到对象存储
                    file_key = f"assets/{project_id}/characters/{asset_id or uuid.uuid4()}/portrait.png"
                    stored_url = await self.storage.upload(file_key, image_data, content_type="image/png")
                    result["image_url"] = stored_url
                    result["thumbnail_url"] = stored_url  # 可以后续生成缩略图
                except Exception as e:
                    logger.warning(f"Failed to upload to storage: {e}")
                    result["image_url"] = image_url  # 使用原始 URL
            else:
                result["image_url"] = image_url
            
            # 提取 FaceID embedding
            try:
                face_extractor = get_face_extractor()
                embedding_storage = get_embedding_storage()
                if face_extractor and embedding_storage:
                    embedding = await face_extractor.extract_embedding(result["image_url"])
                    if embedding is not None:
                        embedding_path = f"assets/{project_id}/characters/{asset_id or uuid.uuid4()}/face_embed.npy"
                        await embedding_storage.save_embedding(embedding_path, embedding)
                        result["embedding_path"] = embedding_path
                        logger.info(f"[AssetGen] FaceID extracted: {embedding_path}")
            except Exception as e:
                logger.warning(f"FaceID extraction failed: {e}")
            
            result["success"] = True
            logger.info(f"[AssetGen] Portrait generated for {character.name}: {result['image_url']}")
            return result
            
        except Exception as e:
            logger.error(f"[AssetGen] Portrait generation failed: {e}")
            result["error"] = str(e)
            return result
    
    async def generate_scene_background(
        self,
        scene: SceneInfo,
        project_id: str,
        asset_id: Optional[str] = None,
        style_hint: str = "韩漫风格"
    ) -> Dict[str, Any]:
        """
        为场景生成空镜图
        
        Args:
            scene: 场景信息
            project_id: 项目ID
            asset_id: 资产ID (可选)
            style_hint: 风格提示
        
        Returns:
            {
                "success": bool,
                "image_url": str,
                "thumbnail_url": str,
                "error": str
            }
        """
        result = {
            "success": False,
            "image_url": None,
            "thumbnail_url": None,
            "error": None,
        }
        
        if not self.provider:
            result["error"] = "豆包服务未配置 (ARK_API_KEY 或 DOUBAO_API_KEY)"
            return result
        
        try:
            # 构建场景空镜 prompt
            prompt = self._build_scene_prompt(scene, style_hint)
            negative_prompt = self._get_scene_negative_prompt()
            
            logger.info(f"[DoubaoAsset] Generating background for {scene.name}")
            logger.info(f"[DoubaoAsset] Prompt: {prompt[:200]}...")
            
            # 调用豆包 Seedream 生成 (最小像素要求: 3,686,400)
            request = DoubaoImageRequest(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=2560,
                height=1440,  # 16:9 landscape, 3,686,400 pixels
            )
            
            gen_result = await self.provider.generate(request)
            
            if not gen_result.success:
                result["error"] = gen_result.error
                return result
            
            image_url = gen_result.image_url
            
            # 上传到存储
            if self.storage and image_url:
                try:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(image_url)
                        image_data = resp.content
                    
                    file_key = f"assets/{project_id}/scenes/{asset_id or uuid.uuid4()}/background.png"
                    stored_url = await self.storage.upload(file_key, image_data, content_type="image/png")
                    result["image_url"] = stored_url
                    result["thumbnail_url"] = stored_url
                except Exception as e:
                    logger.warning(f"Failed to upload to storage: {e}")
                    result["image_url"] = image_url
            else:
                result["image_url"] = image_url
            
            result["success"] = True
            logger.info(f"[AssetGen] Background generated for {scene.name}: {result['image_url']}")
            return result
            
        except Exception as e:
            logger.error(f"[AssetGen] Background generation failed: {e}")
            result["error"] = str(e)
            return result
    
    def _build_character_prompt(self, character: CharacterInfo, style_hint: str) -> str:
        """构建角色定妆照提示词"""
        parts = [
            f"{style_hint}, masterpiece, best quality, highly detailed",
            "portrait photography, studio lighting, soft lighting",
            "1 person, solo, looking at viewer",
            "front view, upper body, half body shot",
            "clear face, detailed facial features, sharp focus on face",
            "clean simple background, solid color backdrop",
        ]
        
        # 性别
        if character.gender:
            gender_map = {"male": "1 boy, male", "female": "1 girl, female"}
            parts.append(gender_map.get(character.gender, ""))
        
        # 年龄
        if character.age_range:
            parts.append(character.age_range)
        
        # 外貌关键词
        if character.appearance_keywords:
            for kw in character.appearance_keywords[:8]:  # 限制数量
                parts.append(kw)
        
        # 名字暗示风格
        parts.append(f"character named {character.name}")
        
        return ", ".join(filter(None, parts))
    
    def _build_scene_prompt(self, scene: SceneInfo, style_hint: str) -> str:
        """构建场景空镜提示词"""
        parts = [
            f"{style_hint}, masterpiece, best quality, highly detailed",
            "background art, environment concept art",
            "no people, empty scene, landscape",
            f"location: {scene.name}",
        ]
        
        # 场景描述
        if scene.description:
            # 截取关键描述
            desc = scene.description[:200]
            parts.append(desc)
        
        # 时间
        if scene.time_of_day:
            time_map = {
                "dawn": "golden hour, early morning light",
                "morning": "morning light, bright daylight",
                "noon": "midday sunshine, harsh light",
                "afternoon": "afternoon sun, warm light",
                "dusk": "sunset, golden hour, warm orange light",
                "night": "night scene, moonlight, artificial lighting",
            }
            parts.append(time_map.get(scene.time_of_day, scene.time_of_day))
        
        # 光照
        if scene.lighting:
            lighting_map = {
                "dim": "dim lighting, low light",
                "bright": "bright lighting, well lit",
                "sunset": "sunset lighting, warm orange glow",
                "lantern": "lantern light, warm glow, traditional lighting",
                "moonlight": "moonlight, blue tint, night lighting",
            }
            parts.append(lighting_map.get(scene.lighting, scene.lighting))
        
        # 氛围
        if scene.mood:
            parts.append(f"{scene.mood} atmosphere")
        
        return ", ".join(filter(None, parts))
    
    def _get_character_negative_prompt(self) -> str:
        """角色负面提示词"""
        return (
            "bad anatomy, low quality, blurry face, deformed, ugly, "
            "multiple people, cropped, watermark, text, logo, "
            "looking away, side view, back view, profile, "
            "bad proportions, extra limbs, duplicated features"
        )
    
    def _get_scene_negative_prompt(self) -> str:
        """场景负面提示词"""
        return (
            "people, person, human, crowd, "
            "low quality, blurry, watermark, text, logo, "
            "deformed architecture, bad perspective"
        )


# 单例
_doubao_asset_generator: Optional[DoubaoAssetGenerator] = None


def get_doubao_asset_generator() -> Optional[DoubaoAssetGenerator]:
    """获取豆包资产生成器"""
    global _doubao_asset_generator
    if _doubao_asset_generator is None:
        # 检查豆包 API Key 是否配置
        api_key = settings.ARK_API_KEY or settings.DOUBAO_API_KEY
        if api_key:
            _doubao_asset_generator = DoubaoAssetGenerator()
    return _doubao_asset_generator

