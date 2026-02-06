"""
Bubble Placer - 气泡放置和图像合成
"""
import io
import logging
from typing import Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont

from app.schemas.panel_spec import PanelSpec, BubbleCandidate, BubbleStyle
from app.core.storage import storage_client
from .svg_renderer import render_bubble_svg, estimate_text_size

logger = logging.getLogger(__name__)

# 默认字体（系统字体）
DEFAULT_FONTS = [
    "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",    # 黑体
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",  # Linux
    "/System/Library/Fonts/PingFang.ttc",  # macOS
]


def get_font(size: int = 24) -> ImageFont.FreeTypeFont:
    """获取可用字体"""
    for font_path in DEFAULT_FONTS:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    # 回退到默认字体
    return ImageFont.load_default()


async def render_bubbles_to_image(
    panel_spec: PanelSpec,
    base_image_path: Optional[str] = None,
    canvas_size: Tuple[int, int] = (1024, 1024)
) -> bytes:
    """
    渲染气泡到图像
    
    Args:
        panel_spec: 分镜规格
        base_image_path: 底图路径（可选）
        canvas_size: 画布尺寸
    
    Returns:
        PNG 图像数据
    """
    width, height = canvas_size
    
    # 创建或加载底图
    if base_image_path:
        try:
            base_data = storage_client.download_file(base_image_path)
            if base_data:
                base_image = Image.open(io.BytesIO(base_data)).convert("RGBA")
                base_image = base_image.resize(canvas_size, Image.LANCZOS)
            else:
                base_image = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
        except Exception as e:
            logger.error(f"Failed to load base image: {e}")
            base_image = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
    else:
        # 透明背景
        base_image = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
    
    # 创建气泡图层
    bubble_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(bubble_layer)
    
    # 渲染每个气泡
    for bubble in panel_spec.bubbles:
        await _render_single_bubble(
            draw=draw,
            bubble=bubble,
            canvas_size=canvas_size
        )
    
    # 合并图层
    result = Image.alpha_composite(base_image, bubble_layer)
    
    # 转换为 bytes
    buffer = io.BytesIO()
    result.save(buffer, format="PNG")
    return buffer.getvalue()


async def _render_single_bubble(
    draw: ImageDraw.Draw,
    bubble: BubbleCandidate,
    canvas_size: Tuple[int, int]
):
    """渲染单个气泡"""
    width, height = canvas_size
    
    # 计算气泡位置
    if bubble.x is not None and bubble.y is not None:
        x = int(bubble.x * width)
        y = int(bubble.y * height)
    else:
        # 默认位置（根据 position_hint）
        x, y = _get_default_position(bubble.position_hint, width, height)
    
    # 计算气泡尺寸
    font_size = bubble.font_size
    text = bubble.text
    
    bubble_width, bubble_height = estimate_text_size(
        text, 
        font_size, 
        bubble.is_vertical
    )
    
    if bubble.width is not None:
        bubble_width = int(bubble.width * width)
    
    # 获取气泡样式
    style = bubble.style.value if isinstance(bubble.style, BubbleStyle) else str(bubble.style)
    
    # 绘制气泡背景
    _draw_bubble_background(
        draw=draw,
        x=x, y=y,
        width=bubble_width,
        height=bubble_height,
        style=style
    )
    
    # 绘制文字
    _draw_bubble_text(
        draw=draw,
        text=text,
        x=x, y=y,
        width=bubble_width,
        height=bubble_height,
        font_size=font_size,
        is_vertical=bubble.is_vertical,
        style=style
    )


def _get_default_position(hint: str, width: int, height: int) -> Tuple[int, int]:
    """根据位置提示获取默认位置"""
    positions = {
        "auto": (width // 2, height // 4),
        "top": (width // 2, 50),
        "bottom": (width // 2, height - 150),
        "left": (100, height // 2),
        "right": (width - 200, height // 2),
        "top-left": (100, 50),
        "top-right": (width - 200, 50),
        "bottom-left": (100, height - 150),
        "bottom-right": (width - 200, height - 150),
    }
    return positions.get(hint, positions["auto"])


def _draw_bubble_background(
    draw: ImageDraw.Draw,
    x: int, y: int,
    width: int, height: int,
    style: str
):
    """绘制气泡背景"""
    # 简化实现：使用 PIL 绘制基本形状
    # 完整实现应该用 CairoSVG 渲染 SVG 模板
    
    padding = 10
    
    if style == "narration":
        # 旁白框 - 半透明黑色矩形
        draw.rounded_rectangle(
            [x - width//2, y - padding, x + width//2, y + height - padding],
            radius=5,
            fill=(0, 0, 0, 200)
        )
    elif style == "thought":
        # 思考泡 - 云朵形状（简化为椭圆+小圆点）
        draw.ellipse(
            [x - width//2, y - padding, x + width//2, y + height - padding - 20],
            fill=(255, 255, 255, 255),
            outline=(0, 0, 0, 255),
            width=2
        )
        # 小圆点
        dot_y = y + height - padding - 15
        draw.ellipse([x - 20, dot_y, x - 5, dot_y + 15], fill="white", outline="black")
        draw.ellipse([x - 35, dot_y + 20, x - 25, dot_y + 30], fill="white", outline="black")
    elif style == "shout":
        # 喊叫泡 - 简化为带边框的多边形
        import math
        points = []
        cx, cy = x, y + height // 2 - padding
        for i in range(12):
            angle = (i * math.pi) / 6
            r = width // 2 if i % 2 == 0 else width // 3
            px = cx + r * math.cos(angle - math.pi/2)
            py = cy + r * 0.8 * math.sin(angle - math.pi/2)
            points.append((px, py))
        draw.polygon(points, fill="white", outline="black", width=3)
    elif style == "whisper":
        # 低语泡 - 虚线椭圆（简化为普通椭圆+不同颜色）
        draw.ellipse(
            [x - width//2, y - padding, x + width//2, y + height - padding],
            fill=(255, 255, 255, 255),
            outline=(128, 128, 128, 255),
            width=2
        )
    else:
        # 普通对话泡
        # 主体椭圆
        draw.ellipse(
            [x - width//2, y - padding, x + width//2, y + height - padding - 20],
            fill=(255, 255, 255, 255),
            outline=(0, 0, 0, 255),
            width=2
        )
        # 尾巴三角
        tail_y = y + height - padding - 20
        draw.polygon(
            [(x - 15, tail_y), (x + 15, tail_y), (x, tail_y + 25)],
            fill="white",
            outline="black"
        )


def _draw_bubble_text(
    draw: ImageDraw.Draw,
    text: str,
    x: int, y: int,
    width: int, height: int,
    font_size: int,
    is_vertical: bool,
    style: str
):
    """绘制气泡文字"""
    font = get_font(font_size)
    
    # 文字颜色
    text_color = "white" if style == "narration" else "black"
    
    # 计算文字区域
    text_x = x - width // 2 + 20
    text_y = y + 10
    text_width = width - 40
    text_height = height - 50
    
    if is_vertical:
        # 竖排文字
        _draw_vertical_text(draw, text, text_x, text_y, font, text_color)
    else:
        # 横排文字（自动换行）
        _draw_wrapped_text(
            draw, text, 
            x=text_x, y=text_y,
            width=text_width,
            font=font,
            color=text_color
        )


def _draw_wrapped_text(
    draw: ImageDraw.Draw,
    text: str,
    x: int, y: int,
    width: int,
    font: ImageFont.FreeTypeFont,
    color: str
):
    """绘制自动换行的文字"""
    words = text
    lines = []
    current_line = ""
    
    for char in words:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = char
    
    if current_line:
        lines.append(current_line)
    
    # 绘制每一行
    line_height = font.size + 5
    for i, line in enumerate(lines):
        draw.text((x, y + i * line_height), line, font=font, fill=color)


def _draw_vertical_text(
    draw: ImageDraw.Draw,
    text: str,
    x: int, y: int,
    font: ImageFont.FreeTypeFont,
    color: str
):
    """绘制竖排文字"""
    char_height = font.size + 2
    for i, char in enumerate(text):
        draw.text((x, y + i * char_height), char, font=font, fill=color)
