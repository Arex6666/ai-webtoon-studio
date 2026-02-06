"""
SVG Renderer - 气泡 SVG 渲染
"""
from typing import Dict, Any, Optional
import re


# 气泡 SVG 模板
BUBBLE_TEMPLATES: Dict[str, str] = {
    "normal": '''
<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="2" dy="2" stdDeviation="3" flood-opacity="0.3"/>
        </filter>
    </defs>
    <ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" 
        fill="white" stroke="black" stroke-width="2" filter="url(#shadow)"/>
    <polygon points="{tail_points}" fill="white" stroke="black" stroke-width="2"/>
</svg>
''',
    
    "shout": '''
<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="2" dy="3" stdDeviation="2" flood-opacity="0.4"/>
        </filter>
    </defs>
    <polygon points="{spiky_points}" 
        fill="white" stroke="black" stroke-width="3" filter="url(#shadow)"/>
</svg>
''',
    
    "thought": '''
<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" 
        fill="white" stroke="black" stroke-width="2"/>
    <circle cx="{dot1_x}" cy="{dot1_y}" r="8" fill="white" stroke="black" stroke-width="1.5"/>
    <circle cx="{dot2_x}" cy="{dot2_y}" r="5" fill="white" stroke="black" stroke-width="1.5"/>
    <circle cx="{dot3_x}" cy="{dot3_y}" r="3" fill="white" stroke="black" stroke-width="1"/>
</svg>
''',
    
    "narration": '''
<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <rect x="0" y="0" width="{width}" height="{height}" 
        fill="rgba(0,0,0,0.85)" rx="5"/>
    <rect x="2" y="2" width="{inner_width}" height="{inner_height}" 
        fill="none" stroke="rgba(255,255,255,0.3)" rx="3"/>
</svg>
''',
    
    "whisper": '''
<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" 
        fill="white" stroke="gray" stroke-width="1.5" stroke-dasharray="5,3"/>
</svg>
'''
}


def render_bubble_svg(
    style: str,
    width: int,
    height: int,
    tail_direction: str = "bottom"  # top/bottom/left/right
) -> str:
    """
    渲染气泡 SVG
    
    Args:
        style: 气泡样式 (normal/shout/thought/narration/whisper)
        width: 宽度
        height: 高度
        tail_direction: 尾巴方向
    
    Returns:
        SVG 字符串
    """
    template = BUBBLE_TEMPLATES.get(style, BUBBLE_TEMPLATES["normal"])
    
    cx = width / 2
    cy = height / 2
    rx = (width - 20) / 2
    ry = (height - 30) / 2
    
    # 计算尾巴点
    tail_points = _calculate_tail_points(cx, cy, rx, ry, tail_direction, width, height)
    
    # 喊叫气泡的尖刺点
    spiky_points = _calculate_spiky_points(cx, cy, width, height)
    
    # 思考气泡的小圆点
    dot1_x = cx - rx * 0.3
    dot1_y = cy + ry + 20
    dot2_x = cx - rx * 0.5
    dot2_y = cy + ry + 35
    dot3_x = cx - rx * 0.6
    dot3_y = cy + ry + 45
    
    return template.format(
        width=width,
        height=height,
        cx=cx,
        cy=cy,
        rx=rx,
        ry=ry,
        tail_points=tail_points,
        spiky_points=spiky_points,
        dot1_x=dot1_x,
        dot1_y=dot1_y,
        dot2_x=dot2_x,
        dot2_y=dot2_y,
        dot3_x=dot3_x,
        dot3_y=dot3_y,
        inner_width=width - 4,
        inner_height=height - 4
    )


def _calculate_tail_points(
    cx: float, cy: float, 
    rx: float, ry: float,
    direction: str,
    width: int, height: int
) -> str:
    """计算对话气泡尾巴的点"""
    if direction == "bottom":
        return f"{cx-15},{cy+ry-5} {cx+15},{cy+ry-5} {cx},{height-5}"
    elif direction == "top":
        return f"{cx-15},{cy-ry+5} {cx+15},{cy-ry+5} {cx},5"
    elif direction == "left":
        return f"{cx-rx+5},{cy-15} {cx-rx+5},{cy+15} 5,{cy}"
    elif direction == "right":
        return f"{cx+rx-5},{cy-15} {cx+rx-5},{cy+15} {width-5},{cy}"
    return f"{cx-15},{cy+ry-5} {cx+15},{cy+ry-5} {cx},{height-5}"


def _calculate_spiky_points(cx: float, cy: float, width: int, height: int) -> str:
    """计算喊叫气泡的尖刺点"""
    import math
    points = []
    num_spikes = 12
    outer_radius = min(width, height) / 2 - 5
    inner_radius = outer_radius * 0.7
    
    for i in range(num_spikes * 2):
        angle = (i * math.pi) / num_spikes
        r = outer_radius if i % 2 == 0 else inner_radius
        x = cx + r * math.cos(angle - math.pi / 2)
        y = cy + r * math.sin(angle - math.pi / 2)
        points.append(f"{x:.1f},{y:.1f}")
    
    return " ".join(points)


def estimate_text_size(text: str, font_size: int = 24, is_vertical: bool = False) -> tuple:
    """
    估算文本所需的气泡尺寸
    
    Returns:
        (width, height)
    """
    # 简单估算，实际应该使用字体度量
    char_width = font_size * 0.6
    char_height = font_size * 1.2
    
    if is_vertical:
        # 竖排
        lines = len(text) // 8 + 1  # 每行约8个字
        max_chars = min(len(text), 8)
        width = lines * char_width + 40
        height = max_chars * char_height + 40
    else:
        # 横排
        lines = len(text) // 15 + 1  # 每行约15个字
        max_chars = min(len(text), 15)
        width = max_chars * char_width + 40
        height = lines * char_height + 40
    
    return int(width), int(height)
