"""
Video Prompt Compiler - 将结构化分镜数据编译为高质量视频 prompt

将 PanelDraft 的 camera_move, shot_type, actions, mood, weather,
composition_notes 等字段编译为精准的 motion prompt，
同时生成 negative_prompt 和 motion_strength。
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class CompiledVideoPrompt:
    """编译后的视频 prompt"""
    motion_prompt: str
    negative_prompt: str
    motion_strength: float
    duration_sec: float


# ============ 映射表 ============

# camera_move → 英文运动描述
CAMERA_MOVE_DESCRIPTIONS = {
    "static": "camera holds steady",
    "pan": "camera pans slowly across the scene",
    "tilt": "camera tilts vertically",
    "dolly_in": "camera slowly pushes forward, closing in on the subject",
    "dolly_out": "camera slowly pulls back, revealing the environment",
    "zoom_in": "lens zooms in smoothly toward the focal point",
    "zoom_out": "lens zooms out smoothly, widening the view",
    "handheld": "slight handheld camera shake, cinematic and organic",
}

# camera_move → motion_strength
CAMERA_MOVE_STRENGTH = {
    "static": 0.15,
    "pan": 0.40,
    "tilt": 0.35,
    "dolly_in": 0.55,
    "dolly_out": 0.55,
    "zoom_in": 0.45,
    "zoom_out": 0.45,
    "handheld": 0.65,
}

# shot_type → 运动幅度缩放因子 (特写=微动, 远景=可大幅运动)
SHOT_TYPE_MOTION_SCALE = {
    "ECU": 0.5,   # 极特写 → 极小运动
    "CU": 0.6,    # 特写 → 小运动
    "MS": 0.85,   # 中景 → 中等运动
    "LS": 1.0,    # 远景 → 正常运动
    "WS": 1.1,    # 大远景 → 稍大运动
    "OTS": 0.75,  # 过肩 → 受限运动
}

# shot_type → 构图提示
SHOT_TYPE_HINTS = {
    "ECU": "extreme close-up, shallow depth of field, fine detail visible",
    "CU": "close-up shot, facial expressions clearly visible",
    "MS": "medium shot, upper body framing",
    "LS": "long shot, full body visible with surrounding context",
    "WS": "wide establishing shot, environment dominates the frame",
    "OTS": "over-the-shoulder perspective, depth layering",
}

# weather → 视觉氛围补充
WEATHER_ATMOSPHERICS = {
    "clear": "",
    "rainy": "raindrops falling, wet reflective surfaces, rain streaks visible",
    "cloudy": "overcast soft lighting, muted shadows",
    "foggy": "atmospheric fog, reduced visibility, diffused light",
    "snowy": "snowflakes drifting, frost on surfaces, cold breath vapor",
}

# time_of_day → 光照提示
TIME_LIGHTING = {
    "day": "natural daylight",
    "night": "moonlit darkness, artificial light sources, high contrast shadows",
    "dawn": "warm golden hour light from the east, long shadows",
    "dusk": "warm sunset tones, orange and purple sky gradient",
}

# 默认 negative prompt — 避免常见 i2v 伪影
DEFAULT_NEGATIVE_PROMPT = (
    "blurry, distorted, morphing face, flickering, jitter, low quality, "
    "watermark, text overlay, sudden scene change, unnatural motion, "
    "static image, frame drop, color banding, oversaturated"
)


def compile_video_prompt(
    camera_move: Optional[str] = None,
    shot_type: Optional[str] = None,
    actions: Optional[str] = None,
    mood: Optional[str] = None,
    weather: Optional[str] = None,
    time_of_day: Optional[str] = None,
    composition_notes: Optional[List[str]] = None,
    visual_prompt: Optional[str] = None,
    lens_hint: Optional[str] = None,
    duration_sec: float = 5.0,
    original_prompt: Optional[str] = None,
) -> CompiledVideoPrompt:
    """
    将结构化分镜数据编译为精准的视频生成 prompt。

    当结构化字段不足时，回退到 original_prompt。
    """
    parts: List[str] = []

    # 1. 镜头运动
    cam = (camera_move or "").lower()
    cam_desc = CAMERA_MOVE_DESCRIPTIONS.get(cam)
    if cam_desc:
        parts.append(cam_desc)

    # 2. 镜头类型提示
    st = (shot_type or "").upper()
    shot_hint = SHOT_TYPE_HINTS.get(st)
    if shot_hint:
        parts.append(shot_hint)

    # 3. 镜头焦距
    if lens_hint and lens_hint != "50mm":
        parts.append(f"{lens_hint} lens characteristics")

    # 4. 角色动作 (最核心的内容)
    if actions and len(actions.strip()) > 5:
        parts.append(actions.strip())

    # 5. 情绪氛围
    if mood:
        parts.append(f"{mood} atmosphere")

    # 6. 天气视效
    w = (weather or "").lower()
    weather_atmo = WEATHER_ATMOSPHERICS.get(w, "")
    if weather_atmo:
        parts.append(weather_atmo)

    # 7. 光照
    tod = (time_of_day or "").lower()
    lighting = TIME_LIGHTING.get(tod, "")
    if lighting:
        parts.append(lighting)

    # 8. 构图要点 (取前 2 条，避免过长)
    if composition_notes:
        for note in composition_notes[:2]:
            if note.strip():
                parts.append(note.strip())

    # 9. 视觉描述 (如果其他字段不足，用 visual_prompt 兜底)
    if visual_prompt and len(parts) < 3:
        parts.append(visual_prompt)

    # 如果编译后内容太少，回退到原始 prompt
    if len(parts) < 2 and original_prompt:
        motion_prompt = original_prompt
    else:
        motion_prompt = ", ".join(parts) if parts else (original_prompt or "")

    # 确保不超过合理长度 (大多数视频模型有 prompt 长度限制)
    if len(motion_prompt) > 500:
        motion_prompt = motion_prompt[:497] + "..."

    # ---- motion_strength 计算 ----
    base_strength = CAMERA_MOVE_STRENGTH.get(cam, 0.4)
    scale = SHOT_TYPE_MOTION_SCALE.get(st, 1.0)
    motion_strength = round(min(base_strength * scale, 1.0), 2)

    # ---- negative_prompt ----
    neg_parts = [DEFAULT_NEGATIVE_PROMPT]
    # 特写镜头额外约束面部变形
    if st in ("ECU", "CU"):
        neg_parts.append("face deformation, eye asymmetry, teeth distortion")
    # 大远景额外约束边缘
    if st in ("WS", "LS"):
        neg_parts.append("edge warping, horizon tilting")

    negative_prompt = ", ".join(neg_parts)

    return CompiledVideoPrompt(
        motion_prompt=motion_prompt,
        negative_prompt=negative_prompt,
        motion_strength=motion_strength,
        duration_sec=duration_sec,
    )
