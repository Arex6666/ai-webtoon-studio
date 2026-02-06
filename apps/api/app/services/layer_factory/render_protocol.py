"""
Render Protocol - 统一渲染协议层
定义标准化的渲染上下文和输出结构，隔离具体 Provider 实现

Production MVP: 真实渲染功能核心模块
"""
import uuid
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class RenderJobType(str, Enum):
    """渲染任务类型"""
    PANEL_RENDER = "panel_render"      # 分镜渲染
    SCENE_ANCHOR = "scene_anchor"      # 场景锚点生成
    FACE_EMBED = "face_embed"          # FaceID 提取
    CONTROL_MAP = "control_map"        # 控制图生成
    TYPESET = "typeset"                # 气泡排版
    EXPORT = "export"                  # 导出


class RenderProviderType(str, Enum):
    """渲染提供商类型"""
    MOCK = "mock"
    COMFYUI_LOCAL = "comfyui_local"
    COMFYUI_CLOUD = "comfyui_cloud"
    KELING = "keling"
    TONGYI = "tongyi"
    DOUBAO = "doubao"


@dataclass
class CharacterContext:
    """角色渲染上下文"""
    character_id: str
    name: str
    ref_image_url: Optional[str] = None
    embedding_path: Optional[str] = None
    embedding_status: str = "missing"  # missing | pending | ready | failed
    consistency_prompt: Optional[str] = None


@dataclass
class SceneContext:
    """场景渲染上下文"""
    scene_id: str
    name: str
    description: Optional[str] = None
    anchor_image_url: Optional[str] = None
    anchor_status: str = "missing"  # missing | ready
    control_maps: Dict[str, str] = field(default_factory=dict)  # {depth_url, lineart_url, canny_url}
    control_status: str = "missing"  # missing | ready | failed


@dataclass
class PropContext:
    """物品渲染上下文"""
    prop_id: str
    name: str
    prop_type: str  # wardrobe | handprop | setdress
    ref_image_url: Optional[str] = None
    prompt_tokens: Optional[str] = None
    holder_character_id: Optional[str] = None


@dataclass
class CameraSettings:
    """相机设置"""
    shot_type: str = "medium"  # extreme_close | close | medium | full | wide | extreme_wide
    angle: str = "eye_level"   # eye_level | high | low | bird | worm | dutch
    focal_length: Optional[str] = None
    movement: Optional[str] = None


@dataclass
class SceneSettings:
    """场景设置"""
    location_description: Optional[str] = None
    time_of_day: str = "day"    # dawn | morning | noon | afternoon | dusk | night
    weather: str = "clear"      # clear | cloudy | rainy | snowy | foggy | stormy
    atmosphere: Optional[str] = None


@dataclass
class StyleSettings:
    """画风设置"""
    style_preset: str = "korean_webtoon"  # korean_webtoon | manga | manhwa | comic | realistic
    lora_path: Optional[str] = None
    lora_strength: float = 0.8
    color_palette: Optional[str] = None


@dataclass
class PanelRenderContext:
    """
    分镜渲染上下文
    封装渲染一个分镜所需的所有信息
    """
    # 基础信息
    panel_id: str
    project_id: str
    chapter_id: str
    panel_index: int
    
    # 内容描述
    action_description: str
    dialogue: Optional[str] = None
    
    # 资产锁定
    characters: List[CharacterContext] = field(default_factory=list)
    scene: Optional[SceneContext] = None
    props: List[PropContext] = field(default_factory=list)
    
    # 渲染参数
    camera: CameraSettings = field(default_factory=CameraSettings)
    scene_settings: SceneSettings = field(default_factory=SceneSettings)
    style: StyleSettings = field(default_factory=StyleSettings)
    
    # 控制参数
    use_faceid: bool = True
    use_controlnet: bool = True
    faceid_strength: float = 0.7
    controlnet_strength: float = 0.6
    
    # 输出参数
    width: int = 1080
    height: int = 1920
    seed: Optional[int] = None
    steps: int = 20
    cfg_scale: float = 7.0
    
    # 提示词
    positive_prompt_override: Optional[str] = None
    negative_prompt: str = "text, watermark, blurry, low quality, deformed, nsfw"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_panel_spec_and_assets(
        cls,
        panel_id: str,
        project_id: str,
        chapter_id: str,
        panel_spec: Dict[str, Any],
        assets_lock: Dict[str, Any],
    ) -> "PanelRenderContext":
        """
        从 PanelSpec 和 AssetsLock 构建渲染上下文
        """
        # 解析角色
        characters = []
        for char_lock in assets_lock.get("characters", []):
            characters.append(CharacterContext(
                character_id=char_lock.get("character_id", ""),
                name=char_lock.get("name", ""),
                ref_image_url=char_lock.get("ref_image_url"),
                embedding_path=char_lock.get("embedding_path"),
                embedding_status=char_lock.get("embedding_status", "missing"),
                consistency_prompt=char_lock.get("consistency_prompt"),
            ))
        
        # 解析场景
        scene_lock = assets_lock.get("scene")
        scene = None
        if scene_lock:
            scene = SceneContext(
                scene_id=scene_lock.get("scene_id", ""),
                name=scene_lock.get("name", ""),
                description=scene_lock.get("description"),
                anchor_image_url=scene_lock.get("anchor_image_url"),
                anchor_status=scene_lock.get("anchor_status", "missing"),
                control_maps=scene_lock.get("control_maps", {}),
                control_status=scene_lock.get("control_status", "missing"),
            )
        
        # 解析物品
        props = []
        for prop_lock in assets_lock.get("props", []):
            props.append(PropContext(
                prop_id=prop_lock.get("prop_id", ""),
                name=prop_lock.get("name", ""),
                prop_type=prop_lock.get("type", "handprop"),
                ref_image_url=prop_lock.get("ref_image_url"),
                prompt_tokens=prop_lock.get("prompt_tokens"),
                holder_character_id=prop_lock.get("holder_character_id"),
            ))
        
        # 解析相机
        camera_spec = panel_spec.get("camera", {})
        camera = CameraSettings(
            shot_type=camera_spec.get("shot_type", "medium"),
            angle=camera_spec.get("angle", "eye_level"),
            focal_length=camera_spec.get("focal_length"),
            movement=camera_spec.get("movement"),
        )
        
        # 解析场景设置
        scene_spec = panel_spec.get("scene", {})
        scene_settings = SceneSettings(
            location_description=scene_spec.get("location_description"),
            time_of_day=scene_spec.get("time_of_day", "day"),
            weather=scene_spec.get("weather", "clear"),
            atmosphere=scene_spec.get("atmosphere"),
        )
        
        # 解析画风
        look_spec = panel_spec.get("look", {})
        style = StyleSettings(
            style_preset=look_spec.get("style_preset", "korean_webtoon"),
            lora_path=look_spec.get("lora_path"),
            lora_strength=look_spec.get("lora_strength", 0.8),
            color_palette=look_spec.get("color_palette"),
        )
        
        return cls(
            panel_id=panel_id,
            project_id=project_id,
            chapter_id=chapter_id,
            panel_index=panel_spec.get("panel_index", 0),
            action_description=panel_spec.get("action_description", ""),
            dialogue=panel_spec.get("dialogue"),
            characters=characters,
            scene=scene,
            props=props,
            camera=camera,
            scene_settings=scene_settings,
            style=style,
        )


@dataclass
class LayerPackOutput:
    """
    图层包输出
    分镜渲染的标准化输出结构
    """
    # 标识
    layerpack_id: str
    panel_id: str
    attempt: int = 1
    
    # 输出 URLs
    full_url: str = ""          # 完整合成图
    bg_url: Optional[str] = None       # 背景层
    char_url: Optional[str] = None     # 角色层
    fg_url: Optional[str] = None       # 前景层
    mask_url: Optional[str] = None     # 蒙版
    manifest_url: Optional[str] = None # 清单文件
    
    # 元数据
    seed: Optional[int] = None
    prompt_hash: Optional[str] = None
    workflow_id: Optional[str] = None
    inputs_hash: Optional[str] = None
    provider: str = "comfyui"
    
    # 追溯信息
    trace_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def create_empty(cls, panel_id: str, attempt: int = 1) -> "LayerPackOutput":
        """创建空输出（用于失败情况）"""
        return cls(
            layerpack_id=f"lp-{int(time.time())}-{uuid.uuid4().hex[:6]}",
            panel_id=panel_id,
            attempt=attempt,
        )


@dataclass
class RenderResult:
    """
    渲染结果封装
    """
    success: bool
    layerpack: Optional[LayerPackOutput] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    retry_after: Optional[int] = None  # 秒，如队列满时
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {"success": self.success}
        if self.layerpack:
            result["layerpack"] = self.layerpack.to_dict()
        if self.error:
            result["error"] = self.error
            result["error_code"] = self.error_code
        if self.retry_after:
            result["retry_after"] = self.retry_after
        return result


def generate_trace_id() -> str:
    """生成追溯 ID"""
    return f"trace-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"


def compute_inputs_hash(context: PanelRenderContext) -> str:
    """计算输入哈希（用于缓存和追溯）"""
    import hashlib
    import json
    
    # 提取关键输入
    key_inputs = {
        "action": context.action_description,
        "camera": context.camera.shot_type,
        "style": context.style.style_preset,
        "characters": [c.character_id for c in context.characters],
        "scene": context.scene.scene_id if context.scene else None,
        "props": [p.prop_id for p in context.props],
    }
    
    content = json.dumps(key_inputs, sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()[:16]


# 导出
__all__ = [
    "RenderJobType",
    "RenderProviderType",
    "CharacterContext",
    "SceneContext",
    "PropContext",
    "CameraSettings",
    "SceneSettings",
    "StyleSettings",
    "PanelRenderContext",
    "LayerPackOutput",
    "RenderResult",
    "generate_trace_id",
    "compute_inputs_hash",
]
