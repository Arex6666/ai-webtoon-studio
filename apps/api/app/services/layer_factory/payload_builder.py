"""
Payload Builder - 构建 ComfyUI 工作流 JSON
根据 PanelSpec 和资产信息生成 ComfyUI 可执行的工作流

支持资产注入：
- FaceID Embedding（角色一致性）
- Scene Anchor + ControlNet（场景一致性）
- Style Profile（画风一致性）
"""
import json
import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from app.schemas.panel_spec import PanelSpec, ShotType, CameraAngle

logger = logging.getLogger(__name__)

# 工作流模板目录
WORKFLOWS_DIR = Path(__file__).parent.parent.parent / "resources" / "workflows"


class AssetInjectionConfig:
    """资产注入配置"""
    
    def __init__(
        self,
        character_embeddings: Optional[Dict[str, str]] = None,  # {char_id: embedding_url}
        scene_anchor_url: Optional[str] = None,
        scene_control_maps: Optional[Dict[str, str]] = None,  # {type: url}
        style_lora: Optional[str] = None,
        style_strength: float = 0.8,
        faceid_strength: float = 0.7,
        controlnet_strength: float = 0.6,
    ):
        self.character_embeddings = character_embeddings or {}
        self.scene_anchor_url = scene_anchor_url
        self.scene_control_maps = scene_control_maps or {}
        self.style_lora = style_lora
        self.style_strength = style_strength
        self.faceid_strength = faceid_strength
        self.controlnet_strength = controlnet_strength


class PayloadBuilder:
    """
    ComfyUI Payload 构建器
    从 PanelSpec 和资产配置生成工作流 JSON
    """
    
    def __init__(self):
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Dict]:
        """加载工作流模板"""
        templates = {}
        
        if WORKFLOWS_DIR.exists():
            for file in WORKFLOWS_DIR.glob("*.json"):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        templates[file.stem] = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load workflow template {file}: {e}")
        
        return templates
    
    def build_character_workflow(
        self,
        panel_spec: PanelSpec,
        character_data: Optional[Dict] = None,
        scene_data: Optional[Dict] = None,
        style_profile: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        构建角色生成工作流
        
        Args:
            panel_spec: 分镜规格
            character_data: 角色资产数据
            scene_data: 场景资产数据
            style_profile: 风格配置
        
        Returns:
            ComfyUI workflow JSON
        """
        # 选择基础模板
        template = self.templates.get("base_character", self._get_default_template())
        
        # 构建提示词
        positive_prompt = self._build_positive_prompt(panel_spec, character_data, scene_data)
        negative_prompt = panel_spec.negative_prompt or "text, watermark, blurry, low quality"
        
        # 注入参数
        workflow = self._inject_params(
            template=template,
            params={
                "positive_prompt": positive_prompt,
                "negative_prompt": negative_prompt,
                "width": self._get_dimension(panel_spec.camera.shot_type, "width"),
                "height": self._get_dimension(panel_spec.camera.shot_type, "height"),
                "seed": -1,  # 随机种子
                "steps": 30,
                "cfg": 7.0,
            }
        )
        
        return workflow
    
    def build_inpaint_workflow(
        self,
        original_image_path: str,
        mask_path: str,
        prompt: str
    ) -> Dict[str, Any]:
        """
        构建补洞/重绘工作流
        """
        template = self.templates.get("background_inpaint", self._get_default_template())
        
        workflow = self._inject_params(
            template=template,
            params={
                "image_path": original_image_path,
                "mask_path": mask_path,
                "positive_prompt": f"{prompt}, seamless background, high quality",
                "negative_prompt": "character, person, figure, text, watermark",
                "denoise": 0.8,
            }
        )
        
        return workflow
    
    def build_layer_separator_workflow(
        self,
        image_path: str
    ) -> Dict[str, Any]:
        """
        构建图层分离工作流
        输出：人物层、背景层、蒙版
        """
        template = self.templates.get("layer_separator", self._get_default_template())
        
        workflow = self._inject_params(
            template=template,
            params={
                "image_path": image_path,
                "output_char": True,
                "output_bg": True,
                "output_mask": True,
            }
        )
        
        return workflow
    
    def build_workflow_with_assets(
        self,
        panel_spec: PanelSpec,
        asset_config: AssetInjectionConfig,
        character_data: Optional[Dict] = None,
        scene_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        构建带资产注入的完整工作流
        
        这是核心方法，整合所有一致性控制：
        - FaceID Embedding（通过 IP-Adapter 注入）
        - Scene Anchor（通过 ControlNet 注入）
        - Style LoRA（画风锁定）
        
        Args:
            panel_spec: 分镜规格
            asset_config: 资产注入配置
            character_data: 角色资产元数据
            scene_data: 场景资产元数据
            
        Returns:
            完整的 ComfyUI 工作流 JSON
        """
        # 选择基础模板
        if asset_config.character_embeddings and asset_config.scene_control_maps:
            template_name = "workflow_full_injection"
        elif asset_config.character_embeddings:
            template_name = "workflow_with_faceid"
        elif asset_config.scene_control_maps:
            template_name = "workflow_scene_lock"
        else:
            template_name = "base_character"
        
        template = self.templates.get(template_name, self._get_workflow_with_faceid_template())
        
        # 构建提示词
        positive_prompt = self._build_positive_prompt(panel_spec, character_data, scene_data)
        negative_prompt = panel_spec.negative_prompt or "text, watermark, blurry, low quality, deformed"
        
        # 基础参数
        params = {
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "width": self._get_dimension(panel_spec.camera.shot_type, "width"),
            "height": self._get_dimension(panel_spec.camera.shot_type, "height"),
            "seed": -1,
            "steps": 30,
            "cfg": 7.0,
        }
        
        # 添加资产注入参数
        if asset_config.character_embeddings:
            # 使用第一个角色的 embedding（多角色场景后续扩展）
            first_char_id = list(asset_config.character_embeddings.keys())[0]
            params["faceid_embedding_url"] = asset_config.character_embeddings[first_char_id]
            params["faceid_strength"] = asset_config.faceid_strength
        
        if asset_config.scene_control_maps:
            params["controlnet_strength"] = asset_config.controlnet_strength
            for map_type, url in asset_config.scene_control_maps.items():
                params[f"{map_type}_map_url"] = url
        
        if asset_config.style_lora:
            params["style_lora"] = asset_config.style_lora
            params["style_strength"] = asset_config.style_strength
        
        # 注入参数到工作流
        workflow = self._inject_params(template, params)
        
        # 添加资产注入节点
        workflow = self._inject_asset_nodes(workflow, asset_config)
        
        logger.info(f"Built workflow with assets: faceid={bool(asset_config.character_embeddings)}, "
                   f"scene={bool(asset_config.scene_control_maps)}, lora={bool(asset_config.style_lora)}")
        
        return workflow
    
    def _inject_asset_nodes(
        self,
        workflow: Dict[str, Any],
        asset_config: AssetInjectionConfig
    ) -> Dict[str, Any]:
        """
        向工作流注入资产节点
        """
        import copy
        workflow = copy.deepcopy(workflow)
        
        next_node_id = max(int(k) for k in workflow.keys() if k.isdigit()) + 1
        
        # 注入 FaceID Embedding 节点（如果有）
        if asset_config.character_embeddings:
            first_embedding_url = list(asset_config.character_embeddings.values())[0]
            
            # IP-Adapter FaceID 加载节点
            workflow[str(next_node_id)] = {
                "class_type": "IPAdapterFaceID",
                "inputs": {
                    "model": self._find_model_output(workflow),
                    "image": ["LoadImage", 0],  # 会被替换
                    "weight": asset_config.faceid_strength,
                    "weight_faceidv2": asset_config.faceid_strength,
                    "combine_embeds": "average",
                    "start_at": 0.0,
                    "end_at": 1.0,
                },
                "_meta": {
                    "title": "FaceID Injection",
                    "embedding_url": first_embedding_url
                }
            }
            next_node_id += 1
        
        # 注入 ControlNet 节点（如果有场景锚点）
        if asset_config.scene_control_maps:
            # Depth ControlNet
            if "depth" in asset_config.scene_control_maps:
                workflow[str(next_node_id)] = {
                    "class_type": "ControlNetApply",
                    "inputs": {
                        "conditioning": self._find_positive_conditioning(workflow),
                        "control_net": ["ControlNetLoader", 0],
                        "image": ["LoadImage", 0],
                        "strength": asset_config.controlnet_strength,
                    },
                    "_meta": {
                        "title": "Depth ControlNet",
                        "control_type": "depth",
                        "image_url": asset_config.scene_control_maps["depth"]
                    }
                }
                next_node_id += 1
            
            # Canny ControlNet
            if "canny" in asset_config.scene_control_maps:
                workflow[str(next_node_id)] = {
                    "class_type": "ControlNetApply",
                    "inputs": {
                        "conditioning": self._find_positive_conditioning(workflow),
                        "control_net": ["ControlNetLoader", 0],
                        "image": ["LoadImage", 0],
                        "strength": asset_config.controlnet_strength * 0.8,
                    },
                    "_meta": {
                        "title": "Canny ControlNet",
                        "control_type": "canny",
                        "image_url": asset_config.scene_control_maps["canny"]
                    }
                }
                next_node_id += 1
            
            # Lineart ControlNet
            if "lineart" in asset_config.scene_control_maps:
                workflow[str(next_node_id)] = {
                    "class_type": "ControlNetApply",
                    "inputs": {
                        "conditioning": self._find_positive_conditioning(workflow),
                        "control_net": ["ControlNetLoader", 0],
                        "image": ["LoadImage", 0],
                        "strength": asset_config.controlnet_strength * 0.7,
                    },
                    "_meta": {
                        "title": "Lineart ControlNet",
                        "control_type": "lineart",
                        "image_url": asset_config.scene_control_maps["lineart"]
                    }
                }
                next_node_id += 1
        
        # 注入 Style LoRA 节点（如果有）
        if asset_config.style_lora:
            workflow[str(next_node_id)] = {
                "class_type": "LoraLoader",
                "inputs": {
                    "model": self._find_model_output(workflow),
                    "clip": self._find_clip_output(workflow),
                    "lora_name": asset_config.style_lora,
                    "strength_model": asset_config.style_strength,
                    "strength_clip": asset_config.style_strength,
                },
                "_meta": {"title": "Style LoRA"}
            }
        
        return workflow
    
    def _find_model_output(self, workflow: Dict) -> List:
        """找到模型输出节点"""
        for node_id, node in workflow.items():
            if node.get("class_type") == "CheckpointLoaderSimple":
                return [node_id, 0]
        return ["4", 0]  # 默认
    
    def _find_clip_output(self, workflow: Dict) -> List:
        """找到 CLIP 输出节点"""
        for node_id, node in workflow.items():
            if node.get("class_type") == "CheckpointLoaderSimple":
                return [node_id, 1]
        return ["4", 1]  # 默认
    
    def _find_positive_conditioning(self, workflow: Dict) -> List:
        """找到正向条件节点"""
        for node_id, node in workflow.items():
            if node.get("class_type") == "CLIPTextEncode":
                meta = node.get("_meta", {})
                if "positive" in meta.get("title", "").lower():
                    return [node_id, 0]
        return ["6", 0]  # 默认
    
    def _get_workflow_with_faceid_template(self) -> Dict[str, Any]:
        """获取带 FaceID 的工作流模板"""
        base = self._get_default_template()
        
        # 添加 FaceID 相关节点占位
        base["10"] = {
            "class_type": "IPAdapterModelLoader",
            "inputs": {
                "ipadapter_file": "ip-adapter-faceid_sd15.bin"
            },
            "_meta": {"title": "Load IP-Adapter FaceID"}
        }
        
        base["11"] = {
            "class_type": "InsightFaceLoader",
            "inputs": {
                "provider": "CPU"
            },
            "_meta": {"title": "Load InsightFace"}
        }
        
        return base
    
    def _build_positive_prompt(
        self,
        panel_spec: PanelSpec,
        character_data: Optional[Dict] = None,
        scene_data: Optional[Dict] = None
    ) -> str:
        """构建正向提示词"""
        parts = []
        
        # 基础描述
        if panel_spec.action_description:
            parts.append(panel_spec.action_description)
        
        # 角色一致性提示
        if character_data:
            consistency = character_data.get("consistency_prompt", "")
            if consistency:
                parts.append(consistency)
        
        # 场景描述
        scene = panel_spec.scene
        if scene.location_description:
            parts.append(scene.location_description)
        
        # 时间/天气
        time_prompts = {
            "day": "daytime, bright lighting",
            "night": "nighttime, dark atmosphere, moon light",
            "dawn": "dawn, golden hour, warm light",
            "dusk": "dusk, sunset, orange sky"
        }
        parts.append(time_prompts.get(scene.time_of_day, ""))
        
        weather_prompts = {
            "clear": "clear weather",
            "rain": "rainy, wet ground, water droplets",
            "snow": "snowy, winter atmosphere",
            "cloudy": "cloudy sky, overcast"
        }
        parts.append(weather_prompts.get(scene.weather, ""))
        
        # 镜头语言
        camera = panel_spec.camera
        shot_prompts = {
            ShotType.EXTREME_CLOSE: "extreme close-up shot, face detail",
            ShotType.CLOSE: "close-up shot, portrait",
            ShotType.MEDIUM: "medium shot, upper body",
            ShotType.FULL: "full body shot",
            ShotType.WIDE: "wide shot, environment visible",
            ShotType.EXTREME_WIDE: "extreme wide shot, landscape"
        }
        parts.append(shot_prompts.get(camera.shot_type, ""))
        
        angle_prompts = {
            CameraAngle.EYE_LEVEL: "eye level view",
            CameraAngle.HIGH: "high angle, looking down",
            CameraAngle.LOW: "low angle, looking up, dramatic",
            CameraAngle.BIRD: "bird's eye view, top down",
            CameraAngle.WORM: "worm's eye view, from ground"
        }
        parts.append(angle_prompts.get(camera.angle, ""))
        
        # 画风
        look = panel_spec.look
        style_prompts = {
            "korean_webtoon": "korean webtoon style, clean lines, vibrant colors",
            "manga": "manga style, black and white, screentone",
            "manhwa": "manhwa style, soft colors, romantic",
            "comic": "western comic style, bold lines, saturated colors"
        }
        parts.append(style_prompts.get(look.style_preset, ""))
        
        # 质量标签
        parts.append("masterpiece, best quality, highly detailed")
        
        # 过滤空字符串并连接
        return ", ".join(p for p in parts if p)
    
    def _get_dimension(self, shot_type: ShotType, dim: str) -> int:
        """根据景别获取图片尺寸"""
        # 短漫通常是竖屏
        dimensions = {
            ShotType.EXTREME_CLOSE: {"width": 1024, "height": 1024},
            ShotType.CLOSE: {"width": 1024, "height": 1024},
            ShotType.MEDIUM: {"width": 768, "height": 1024},
            ShotType.FULL: {"width": 768, "height": 1280},
            ShotType.WIDE: {"width": 1024, "height": 768},
            ShotType.EXTREME_WIDE: {"width": 1280, "height": 720},
        }
        return dimensions.get(shot_type, {"width": 1024, "height": 1024})[dim]
    
    def _inject_params(
        self,
        template: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        将参数注入到模板中
        简化版：直接替换特定节点的值
        """
        import copy
        workflow = copy.deepcopy(template)
        
        # 遍历节点并注入参数
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            
            inputs = node.get("inputs", {})
            class_type = node.get("class_type", "")
            
            # KSampler 节点
            if "KSampler" in class_type:
                if "seed" in params:
                    inputs["seed"] = params["seed"]
                if "steps" in params:
                    inputs["steps"] = params["steps"]
                if "cfg" in params:
                    inputs["cfg"] = params["cfg"]
            
            # CLIP Text Encode 节点
            if "CLIPTextEncode" in class_type:
                # 根据节点标题判断是正向还是负向
                if node.get("_meta", {}).get("title", "").lower().find("negative") >= 0:
                    if "negative_prompt" in params:
                        inputs["text"] = params["negative_prompt"]
                else:
                    if "positive_prompt" in params:
                        inputs["text"] = params["positive_prompt"]
            
            # Empty Latent Image 节点
            if "EmptyLatentImage" in class_type:
                if "width" in params:
                    inputs["width"] = params["width"]
                if "height" in params:
                    inputs["height"] = params["height"]
        
        return workflow
    
    def _get_default_template(self) -> Dict[str, Any]:
        """获取默认工作流模板 (Flux)"""
        return {
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": 1024,
                    "height": 1024,
                    "batch_size": 1
                },
                "_meta": {"title": "Empty Latent"}
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "",
                    "clip": ["11", 0]
                },
                "_meta": {"title": "Positive"}
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "",
                    "clip": ["11", 0]
                },
                "_meta": {"title": "Negative"}
            },
            "10": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "Flux.1-dev",
                    "weight_dtype": "default"
                },
                "_meta": {"title": "Load Flux UNet"}
            },
            "11": {
                "class_type": "DualCLIPLoader",
                "inputs": {
                    "clip_name1": "t5xxl_fp16.safetensors",
                    "clip_name2": "clip_l.safetensors",
                    "type": "flux"
                },
                "_meta": {"title": "Load CLIP"}
            },
            "12": {
                "class_type": "VAELoader",
                "inputs": {
                    "vae_name": "ae.safetensors"
                },
                "_meta": {"title": "Load VAE"}
            },
            "13": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": -1,
                    "steps": 20,
                    "cfg": 3.5,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0,
                    "model": ["10", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                },
                "_meta": {"title": "KSampler"}
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["13", 0],
                    "vae": ["12", 0]
                },
                "_meta": {"title": "VAE Decode"}
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "WebtoonStudio",
                    "images": ["8", 0]
                },
                "_meta": {"title": "Save Image"}
            }
        }
