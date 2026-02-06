"""
PromptCompiler - 提示词编译器
将分镜数据编译为优化的AI生图提示词
"""
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class PromptStyle(str, Enum):
    """提示词风格"""
    KOREAN_WEBTOON = "korean_webtoon"
    JAPANESE_MANGA = "japanese_manga"
    CHINESE_MANHUA = "chinese_manhua"
    AMERICAN_COMIC = "american_comic"
    REALISTIC = "realistic"
    ANIME = "anime"


class PromptPriority(str, Enum):
    """提示词优先级"""
    CRITICAL = "critical"    # 必须包含
    HIGH = "high"            # 优先包含
    MEDIUM = "medium"        # 一般优先级
    LOW = "low"              # 可省略


class PromptToken(BaseModel):
    """提示词令牌"""
    content: str = Field(..., description="令牌内容")
    category: str = Field(..., description="类别: character/scene/action/camera/style")
    priority: PromptPriority = Field(default=PromptPriority.MEDIUM)
    weight: float = Field(default=1.0, description="权重")


class CompiledPrompt(BaseModel):
    """编译后的提示词"""
    positive: str = Field(..., description="正向提示词")
    negative: str = Field(..., description="负向提示词")
    tokens: List[PromptToken] = Field(default_factory=list, description="令牌列表")
    estimated_length: int = Field(0, description="估计token长度")
    style: PromptStyle = Field(default=PromptStyle.KOREAN_WEBTOON)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# 风格基础提示词
STYLE_BASES = {
    PromptStyle.KOREAN_WEBTOON: {
        "positive": "korean webtoon style, manhwa, clean lines, vibrant colors, digital art, high quality",
        "negative": "photo, realistic, 3d render, blurry, low quality, deformed, ugly",
    },
    PromptStyle.JAPANESE_MANGA: {
        "positive": "manga style, japanese comic, black and white, screentone, dynamic lines",
        "negative": "color, photo, realistic, blurry, low quality, deformed",
    },
    PromptStyle.CHINESE_MANHUA: {
        "positive": "manhua style, chinese comic, detailed, colorful, artistic",
        "negative": "photo, realistic, 3d render, blurry, low quality",
    },
    PromptStyle.AMERICAN_COMIC: {
        "positive": "american comic style, bold lines, superhero aesthetic, dynamic composition",
        "negative": "manga, anime, photo, realistic, blurry",
    },
    PromptStyle.REALISTIC: {
        "positive": "photorealistic, detailed, cinematic lighting, high quality photograph",
        "negative": "cartoon, anime, drawing, blurry, low quality",
    },
    PromptStyle.ANIME: {
        "positive": "anime style, illustration, colorful, detailed, high quality anime art",
        "negative": "photo, realistic, 3d, blurry, low quality, deformed",
    },
}

# 镜头映射
CAMERA_TOKENS = {
    "extreme_close_up": "extreme close-up shot, face detail",
    "close_up": "close-up shot, portrait",
    "medium_close": "medium close-up, upper body",
    "medium": "medium shot, waist up",
    "medium_full": "medium full shot",
    "full": "full body shot, full figure",
    "wide": "wide shot, environment visible",
    "extreme_wide": "extreme wide shot, establishing shot",
}

ANGLE_TOKENS = {
    "eye_level": "eye level angle",
    "high_angle": "high angle, bird's eye view",
    "low_angle": "low angle, worm's eye view",
    "dutch": "dutch angle, tilted frame",
    "overhead": "overhead shot, top down view",
    "side": "side view, profile angle",
}


class PromptCompiler:
    """
    提示词编译器
    
    功能:
    1. 解析分镜数据生成结构化令牌
    2. 根据风格选择基础提示词
    3. 智能组合和排序令牌
    4. 生成优化的正向/负向提示词
    """

    def __init__(
        self,
        default_style: PromptStyle = PromptStyle.KOREAN_WEBTOON,
        max_tokens: int = 150,
    ):
        """
        初始化编译器
        
        Args:
            default_style: 默认风格
            max_tokens: 最大令牌数（用于截断）
        """
        self.default_style = default_style
        self.max_tokens = max_tokens

    def compile(
        self,
        panel_data: Dict[str, Any],
        characters: Optional[List[Dict[str, Any]]] = None,
        scene: Optional[Dict[str, Any]] = None,
        style: Optional[PromptStyle] = None,
    ) -> CompiledPrompt:
        """
        编译分镜数据为提示词
        
        Args:
            panel_data: 分镜数据
            characters: 角色数据列表
            scene: 场景数据
            style: 风格（可选）
            
        Returns:
            编译后的提示词
        """
        style = style or self.default_style
        tokens: List[PromptToken] = []
        
        # 1. 添加风格基础
        style_base = STYLE_BASES.get(style, STYLE_BASES[PromptStyle.KOREAN_WEBTOON])
        
        # 2. 提取场景令牌
        scene_tokens = self._extract_scene_tokens(panel_data, scene)
        tokens.extend(scene_tokens)
        
        # 3. 提取角色令牌
        char_tokens = self._extract_character_tokens(panel_data, characters or [])
        tokens.extend(char_tokens)
        
        # 4. 提取动作令牌
        action_tokens = self._extract_action_tokens(panel_data)
        tokens.extend(action_tokens)
        
        # 5. 提取镜头令牌
        camera_tokens = self._extract_camera_tokens(panel_data)
        tokens.extend(camera_tokens)
        
        # 6. 组合正向提示词
        positive = self._build_positive_prompt(tokens, style_base["positive"])
        
        # 7. 构建负向提示词
        negative = self._build_negative_prompt(panel_data, style_base["negative"])
        
        return CompiledPrompt(
            positive=positive,
            negative=negative,
            tokens=tokens,
            estimated_length=len(positive.split()),
            style=style,
            metadata={
                "panel_id": panel_data.get("panel_id", ""),
                "character_count": len(char_tokens),
            }
        )

    def _extract_scene_tokens(
        self,
        panel_data: Dict[str, Any],
        scene: Optional[Dict[str, Any]],
    ) -> List[PromptToken]:
        """提取场景相关令牌"""
        tokens = []
        
        # 场景描述
        scene_desc = panel_data.get("scene", "")
        if scene and isinstance(scene, dict):
            scene_desc = scene.get("description", scene.get("name", scene_desc))
        
        if scene_desc:
            tokens.append(PromptToken(
                content=str(scene_desc),
                category="scene",
                priority=PromptPriority.HIGH,
            ))
        
        # 时间
        time_of_day = panel_data.get("time_of_day", "")
        if time_of_day:
            time_mapping = {
                "day": "daytime, bright lighting",
                "night": "night time, dark atmosphere, artificial lights",
                "dawn": "dawn, golden hour, warm light",
                "dusk": "dusk, sunset, orange sky",
            }
            tokens.append(PromptToken(
                content=time_mapping.get(time_of_day, time_of_day),
                category="scene",
                priority=PromptPriority.MEDIUM,
            ))
        
        # 天气
        weather = panel_data.get("weather", "")
        if weather and weather != "clear":
            weather_mapping = {
                "rain": "rainy weather, wet surfaces",
                "snow": "snowy weather, winter scene",
                "cloudy": "cloudy sky, overcast",
                "fog": "foggy atmosphere, mist",
            }
            tokens.append(PromptToken(
                content=weather_mapping.get(weather, weather),
                category="scene",
                priority=PromptPriority.MEDIUM,
            ))
        
        return tokens

    def _extract_character_tokens(
        self,
        panel_data: Dict[str, Any],
        characters: List[Dict[str, Any]],
    ) -> List[PromptToken]:
        """提取角色相关令牌"""
        tokens = []
        
        panel_chars = panel_data.get("characters", [])
        char_count = len(panel_chars)
        
        # 人数提示
        if char_count > 0:
            count_mapping = {
                1: "1girl" if self._is_female_char(panel_chars[0], characters) else "1boy",
                2: "2people, duo",
                3: "3people, group",
            }
            if char_count <= 3:
                tokens.append(PromptToken(
                    content=count_mapping.get(char_count, f"{char_count}people, group"),
                    category="character",
                    priority=PromptPriority.HIGH,
                ))
            else:
                tokens.append(PromptToken(
                    content=f"{char_count}people, crowd, group shot",
                    category="character",
                    priority=PromptPriority.HIGH,
                ))
        
        # 角色外观描述
        for char_name in panel_chars:
            char_data = self._find_character(char_name, characters)
            if char_data:
                appearance = char_data.get("appearance", char_data.get("visual_prompt", ""))
                if appearance:
                    tokens.append(PromptToken(
                        content=str(appearance),
                        category="character",
                        priority=PromptPriority.HIGH,
                    ))
        
        return tokens

    def _extract_action_tokens(
        self,
        panel_data: Dict[str, Any],
    ) -> List[PromptToken]:
        """提取动作相关令牌"""
        tokens = []
        
        # 动作描述
        action = panel_data.get("action", panel_data.get("description", ""))
        if action:
            tokens.append(PromptToken(
                content=str(action),
                category="action",
                priority=PromptPriority.CRITICAL,
            ))
        
        # 表情
        expression = panel_data.get("expression", "")
        if expression:
            tokens.append(PromptToken(
                content=f"{expression} expression",
                category="action",
                priority=PromptPriority.MEDIUM,
            ))
        
        return tokens

    def _extract_camera_tokens(
        self,
        panel_data: Dict[str, Any],
    ) -> List[PromptToken]:
        """提取镜头相关令牌"""
        tokens = []
        
        camera = panel_data.get("camera", {})
        if isinstance(camera, str):
            camera = {"shot_type": camera}
        
        # 景别
        shot_type = camera.get("shot_type", "medium")
        shot_token = CAMERA_TOKENS.get(shot_type, shot_type)
        tokens.append(PromptToken(
            content=shot_token,
            category="camera",
            priority=PromptPriority.HIGH,
        ))
        
        # 角度
        angle = camera.get("angle", "eye_level")
        angle_token = ANGLE_TOKENS.get(angle, angle)
        if angle != "eye_level":  # 默认角度不需要特别强调
            tokens.append(PromptToken(
                content=angle_token,
                category="camera",
                priority=PromptPriority.MEDIUM,
            ))
        
        return tokens

    def _build_positive_prompt(
        self,
        tokens: List[PromptToken],
        style_base: str,
    ) -> str:
        """构建正向提示词"""
        # 按优先级排序
        priority_order = {
            PromptPriority.CRITICAL: 0,
            PromptPriority.HIGH: 1,
            PromptPriority.MEDIUM: 2,
            PromptPriority.LOW: 3,
        }
        sorted_tokens = sorted(tokens, key=lambda t: priority_order[t.priority])
        
        # 组合
        parts = [t.content for t in sorted_tokens]
        content = ", ".join(parts)
        
        # 添加风格基础
        positive = f"{content}, {style_base}"
        
        return positive

    def _build_negative_prompt(
        self,
        panel_data: Dict[str, Any],
        style_base: str,
    ) -> str:
        """构建负向提示词"""
        negative_parts = [style_base]
        
        # 通用负向词
        common_negative = [
            "bad anatomy", "bad hands", "missing fingers",
            "extra limbs", "watermark", "signature", "text",
        ]
        negative_parts.extend(common_negative)
        
        return ", ".join(negative_parts)

    def _find_character(
        self,
        name: str,
        characters: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """查找角色数据"""
        name_lower = str(name).lower()
        for char in characters:
            if isinstance(char, dict):
                char_name = char.get("name", "").lower()
                if char_name == name_lower:
                    return char
        return None

    def _is_female_char(
        self,
        char_name: str,
        characters: List[Dict[str, Any]],
    ) -> bool:
        """判断是否为女性角色"""
        char = self._find_character(char_name, characters)
        if char:
            gender = char.get("gender", "").lower()
            return gender in ["female", "f", "女"]
        # 基于名称的简单推测
        female_indicators = ["小红", "小丽", "小美", "姐", "妹", "娘"]
        return any(ind in str(char_name) for ind in female_indicators)

    def compile_batch(
        self,
        panels: List[Dict[str, Any]],
        storyboard_data: Optional[Dict[str, Any]] = None,
    ) -> List[CompiledPrompt]:
        """批量编译"""
        characters = []
        style = self.default_style
        
        if storyboard_data:
            characters = storyboard_data.get("characters", [])
            style_str = storyboard_data.get("style", "")
            if style_str:
                try:
                    style = PromptStyle(style_str)
                except ValueError:
                    pass
        
        results = []
        for panel in panels:
            scene = None
            scene_name = panel.get("scene", "")
            if storyboard_data and scene_name:
                for s in storyboard_data.get("scenes", []):
                    if isinstance(s, dict) and s.get("name") == scene_name:
                        scene = s
                        break
            
            compiled = self.compile(panel, characters, scene, style)
            results.append(compiled)
        
        return results
