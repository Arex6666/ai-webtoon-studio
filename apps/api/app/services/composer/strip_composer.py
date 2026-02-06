"""
Strip Composer - 长条漫合成
将多个分镜图片合成为一张长条漫图片
"""
import io
import logging
from typing import List, Dict, Any, Optional, Tuple, Callable
from PIL import Image

from app.core.storage import storage_client

logger = logging.getLogger(__name__)


async def compose_strip_image(
    panel_image_paths: List[str],
    panel_slots: List[Dict[str, Any]],
    strip_width: int = 800,
    panel_gap: int = 20,
    background_color: str = "#FFFFFF",
    output_format: str = "png",
    progress_callback: Optional[Callable[[float], None]] = None
) -> Tuple[bytes, int]:
    """
    合成长条漫图片
    
    Args:
        panel_image_paths: 分镜图片存储路径列表
        panel_slots: 分镜槽位信息（包含权重和高度比例）
        strip_width: 输出宽度
        panel_gap: 分镜间距
        background_color: 背景颜色
        output_format: 输出格式 (png/jpg/webp)
        progress_callback: 进度回调函数
    
    Returns:
        (图片数据, 总高度)
    """
    if not panel_image_paths:
        raise ValueError("No panel images provided")
    
    # 加载所有图片
    images = []
    for i, path in enumerate(panel_image_paths):
        try:
            data = storage_client.download_file(path)
            if data:
                img = Image.open(io.BytesIO(data))
                images.append(img)
            else:
                logger.warning(f"Failed to download image: {path}")
        except Exception as e:
            logger.error(f"Error loading image {path}: {e}")
        
        if progress_callback:
            progress_callback((i + 1) / len(panel_image_paths) * 0.3)
    
    if not images:
        raise ValueError("No images could be loaded")
    
    # 计算每个分镜的目标高度
    panel_heights = []
    
    for i, img in enumerate(images):
        # 获取槽位信息
        slot = next(
            (s for s in panel_slots if i < len(panel_slots)),
            {"weight": "normal", "height_ratio": 1.0}
        )
        if i < len(panel_slots):
            slot = panel_slots[i]
        
        # 原始宽高比
        aspect_ratio = img.height / img.width
        
        # 根据权重调整基础高度
        weight = slot.get("weight", "normal")
        height_ratio = slot.get("height_ratio", 1.0)
        
        weight_multiplier = {
            "highlight": 1.5,
            "normal": 1.0,
            "transition": 0.6
        }.get(weight, 1.0)
        
        # 计算目标高度
        base_height = int(strip_width * aspect_ratio)
        target_height = int(base_height * height_ratio * weight_multiplier)
        
        panel_heights.append(target_height)
    
    # 计算总高度
    total_height = sum(panel_heights) + panel_gap * (len(images) - 1)
    
    # 解析背景颜色
    bg_color = parse_color(background_color)
    
    # 创建画布
    canvas = Image.new("RGB", (strip_width, total_height), bg_color)
    
    # 粘贴图片
    current_y = 0
    for i, (img, target_height) in enumerate(zip(images, panel_heights)):
        # 调整图片大小
        resized = img.resize(
            (strip_width, target_height),
            Image.LANCZOS
        )
        
        # 转换为 RGB
        if resized.mode in ("RGBA", "P"):
            # 创建白色背景
            bg = Image.new("RGB", resized.size, bg_color)
            if resized.mode == "RGBA":
                bg.paste(resized, mask=resized.split()[3])
            else:
                bg.paste(resized)
            resized = bg
        elif resized.mode != "RGB":
            resized = resized.convert("RGB")
        
        # 粘贴到画布
        canvas.paste(resized, (0, current_y))
        current_y += target_height + panel_gap
        
        if progress_callback:
            progress_callback(0.3 + (i + 1) / len(images) * 0.5)
    
    # 导出
    buffer = io.BytesIO()
    
    if output_format == "jpg":
        canvas.save(buffer, format="JPEG", quality=95)
    elif output_format == "webp":
        canvas.save(buffer, format="WebP", quality=95)
    else:
        canvas.save(buffer, format="PNG")
    
    if progress_callback:
        progress_callback(1.0)
    
    return buffer.getvalue(), total_height


def parse_color(color_str: str) -> Tuple[int, int, int]:
    """解析颜色字符串"""
    color_str = color_str.strip()
    
    if color_str.startswith("#"):
        # Hex 颜色
        hex_color = color_str[1:]
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    if color_str.startswith("rgb"):
        # RGB 格式
        import re
        match = re.search(r"(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color_str)
        if match:
            return tuple(int(x) for x in match.groups())
    
    # 默认白色
    return (255, 255, 255)


async def compose_motion_video(
    panel_image_paths: List[str],
    panel_slots: List[Dict[str, Any]],
    parallax_config: Optional[Dict[str, Any]] = None,
    output_width: int = 1080,
    fps: int = 30,
    duration_per_panel: float = 3.0
) -> bytes:
    """
    合成微动视频（V1 功能）
    
    TODO: 实现视差动画和视频导出
    """
    # MVP 暂不实现
    raise NotImplementedError("Motion video composition not yet implemented")
