"""
Asset Image Generator - 资产参考图自动生成
自动为角色生成定妆照、为场景生成空镜图
"""
import asyncio
import logging
import uuid
from typing import Optional, Dict, Any, List

from app.core.config import settings
from app.services.layer_factory.comfyui_client import get_comfyui_client
from app.services.layer_factory.workflow_builder import build_flux_workflow
from app.services.storage import get_object_store
from app.services.identity import get_face_extractor, get_embedding_storage
from app.services.scene_anchor import get_control_map_generator, get_anchor_storage
from app.models.asset import Asset
from app.schemas.script_ir import CharacterIR, SceneIR

logger = logging.getLogger(__name__)


class AssetImageGenerator:
    """
    资产图像自动生成器
    
    - 为角色生成定妆照 (正面半身像)
    - 为场景生成空镜图 (无人背景)
    """
    
    def __init__(self):
        self.client = get_comfyui_client()
        self.storage = get_object_store()
    
    async def generate_character_portrait(
        self,
        character: CharacterIR,
        asset: Asset,
        project_id: str,
    ) -> Dict[str, Any]:
        """
        为角色生成定妆照
        
        生成: 正面/半侧面半身像，清晰脸部，适合 FaceID 提取
        
        Returns:
            {"success": bool, "image_url": str, "embedding_path": str, ...}
        """
        result = {
            "success": False,
            "image_url": None,
            "embedding_path": None,
            "error": None,
        }
        
        try:
            # 构建角色定妆照 prompt
            prompt_parts = [
                "masterpiece, best quality, highly detailed",
                "portrait photography, studio lighting",
                "1 person, solo, looking at viewer",
                "front view, upper body",
                "clear face, detailed facial features",
                "clean background, solid color backdrop",
            ]
            
            # 添加角色特征
            if character.gender:
                prompt_parts.append(f"{character.gender}")
            if character.age_range:
                prompt_parts.append(f"{character.age_range}")
            
            # 外观关键词
            if character.appearance_keywords:
                prompt_parts.extend(character.appearance_keywords[:5])
            
            positive_prompt = ", ".join(prompt_parts)
            
            negative_prompt = (
                "bad anatomy, low quality, blurry face, deformed, "
                "multiple people, cropped, watermark, text, "
                "looking away, side view, back view"
            )
            
            # 提交生成任务
            workflow = build_flux_workflow(
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                width=768,  # 定妆照用 1:1 或 3:4
                height=1024,
                steps=25,
            )
            
            prompt_id = await self.client.submit_workflow(workflow)
            logger.info(f"Submitted character portrait job for {character.name}: {prompt_id}")
            
            # 等待完成
            await self._wait_for_completion(prompt_id)
            
            # 获取输出并上传
            outputs = await self.client.fetch_outputs(prompt_id)
            if not outputs:
                result["error"] = "生成失败：无输出图像"
                return result
            
            # 上传定妆照
            image_data = outputs[0]
            storage_key = f"assets/characters/{asset.id}/portrait.png"
            image_url = await self.storage.upload_file(
                file_content=image_data,
                key=storage_key,
                content_type="image/png"
            )
            
            result["image_url"] = image_url
            result["success"] = True
            logger.info(f"Generated portrait for {character.name}: {image_url}")
            
            # 自动提取 FaceID Embedding
            try:
                face_extractor = get_face_extractor()
                embedding, bbox_info = face_extractor.extract_embedding(image_data, return_bbox=True)
                
                if embedding is not None:
                    # 保存 embedding
                    embedding_storage = get_embedding_storage()
                    embedding_path = embedding_storage.save_embedding(
                        asset_id=asset.id,
                        embedding=embedding,
                        metadata={
                            "source": "auto_generated",
                            "bbox": bbox_info,
                        }
                    )
                    result["embedding_path"] = embedding_path
                    logger.info(f"Extracted FaceID for {character.name}")
                else:
                    result["error"] = "生成的图像未检测到人脸"
            except Exception as e:
                logger.warning(f"Failed to extract embedding for {character.name}: {e}")
                result["error"] = f"FaceID 提取失败: {e}"
            
            return result
            
        except Exception as e:
            logger.error(f"Generate portrait failed for {character.name}: {e}")
            result["error"] = str(e)
            return result
    
    async def generate_scene_background(
        self,
        scene: SceneIR,
        asset: Asset,
        project_id: str,
    ) -> Dict[str, Any]:
        """
        为场景生成空镜图
        
        生成: 无人背景图，用于生成控制图 (Depth/Canny/Lineart)
        
        Returns:
            {"success": bool, "image_url": str, "control_maps": dict, ...}
        """
        result = {
            "success": False,
            "image_url": None,
            "control_maps": {},
            "error": None,
        }
        
        try:
            # 构建场景空镜图 prompt
            prompt_parts = [
                "masterpiece, best quality, highly detailed",
                "empty scene, no people, no characters",
                "wide angle, establishing shot",
                "detailed environment, architectural details",
            ]
            
            # 添加场景特征
            if scene.location_type:
                prompt_parts.append(scene.location_type)
            
            if scene.time_period:
                prompt_parts.append(f"{scene.time_period} lighting")
            
            if scene.weather:
                prompt_parts.append(scene.weather)
            
            # 氛围关键词
            if scene.atmosphere_keywords:
                prompt_parts.extend(scene.atmosphere_keywords[:5])
            
            # 视觉描述
            if scene.visual_description:
                prompt_parts.append(scene.visual_description[:100])
            
            positive_prompt = ", ".join(prompt_parts)
            
            negative_prompt = (
                "people, person, character, figure, human, "
                "low quality, blurry, text, watermark"
            )
            
            # 生成竖版背景 (9:16)
            workflow = build_flux_workflow(
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                width=1080,
                height=1920,
                steps=25,
            )
            
            prompt_id = await self.client.submit_workflow(workflow)
            logger.info(f"Submitted scene background job for {scene.name}: {prompt_id}")
            
            # 等待完成
            await self._wait_for_completion(prompt_id)
            
            # 获取输出并上传
            outputs = await self.client.fetch_outputs(prompt_id)
            if not outputs:
                result["error"] = "生成失败：无输出图像"
                return result
            
            # 上传空镜图
            image_data = outputs[0]
            storage_key = f"assets/scenes/{asset.id}/anchor.png"
            image_url = await self.storage.upload_file(
                file_content=image_data,
                key=storage_key,
                content_type="image/png"
            )
            
            result["image_url"] = image_url
            result["success"] = True
            logger.info(f"Generated background for {scene.name}: {image_url}")
            
            # 自动生成控制图 (Depth/Canny/Lineart)
            try:
                control_generator = get_control_map_generator()
                control_maps = control_generator.generate_all(image_data)
                
                anchor_storage = get_anchor_storage()
                saved_maps = {}
                
                for map_type, map_data in control_maps.items():
                    map_key = f"assets/scenes/{asset.id}/{map_type}.png"
                    map_url = await self.storage.upload_file(
                        file_content=map_data,
                        key=map_key,
                        content_type="image/png"
                    )
                    saved_maps[map_type] = map_url
                
                # 记录到存储
                anchor_storage.save_anchor_info(
                    asset_id=asset.id,
                    anchor_path=image_url,
                    control_maps=saved_maps,
                )
                
                result["control_maps"] = saved_maps
                logger.info(f"Generated control maps for {scene.name}: {list(saved_maps.keys())}")
                
            except Exception as e:
                logger.warning(f"Failed to generate control maps for {scene.name}: {e}")
                result["error"] = f"控制图生成失败: {e}"
            
            return result
            
        except Exception as e:
            logger.error(f"Generate background failed for {scene.name}: {e}")
            result["error"] = str(e)
            return result
    
    async def _wait_for_completion(
        self,
        prompt_id: str,
        timeout: int = 300,
        poll_interval: float = 1.0,
    ):
        """等待任务完成"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = await self.client.poll_status(prompt_id)
            current_status = status.get("status", "pending")
            
            if current_status == "completed":
                return
            elif current_status == "failed":
                raise Exception(f"ComfyUI job failed: {status.get('error')}")
            
            await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"Job {prompt_id} timed out after {timeout}s")


# 单例
_generator: Optional[AssetImageGenerator] = None


def get_asset_image_generator() -> AssetImageGenerator:
    """获取资产图像生成器单例"""
    global _generator
    if _generator is None:
        _generator = AssetImageGenerator()
    return _generator
