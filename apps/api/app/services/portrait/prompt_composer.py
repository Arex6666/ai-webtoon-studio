"""
S5-01 - Portrait Prompt Composer

将 CharacterPortraitSpec 组装成图像生成 prompt。
"""

from typing import Optional
from .spec_generator import CharacterPortraitSpec


# ============ Style Profiles ============

STYLE_PROFILES = {
    "A": {  # Semi-realistic cinematic (推荐)
        "positive": """semi-realistic cinematic portrait, clean face details, 
soft studio lighting, sharp focus, natural skin texture, high quality, 
professional headshot, detailed eyes, beautiful lighting""",
        "negative": """lowres, blurry, bad anatomy, deformed face, extra face, 
extra head, multiple people, watermark, text, logo, overexposed, 
underexposed, sunglasses, mask, heavy motion blur, ugly, disfigured, 
bad hands, missing fingers, cropped, worst quality, low quality"""
    },
    "B": {  # Anime style
        "positive": """anime style portrait, clean lines, soft shading, 
studio lighting, high quality illustration, detailed face, 
professional anime art, vivid colors""",
        "negative": """lowres, blurry, bad anatomy, deformed, multiple people, 
watermark, text, ugly, worst quality, low quality, 3d render, photo"""
    },
    "C": {  # Webtoon style
        "positive": """webtoon style portrait, clean lineart, flat colors, 
soft cel shading, high quality digital art, manhwa style, 
professional illustration""",
        "negative": """lowres, blurry, bad anatomy, deformed, multiple people, 
watermark, text, ugly, worst quality, low quality, 3d, realistic"""
    }
}


# ============ Portrait Template ============

PORTRAIT_TEMPLATE = """One person, {gender} {age_range}, {hair}, wearing {outfit}{accessory_clause}.
Expression: neutral, calm, natural.
Framing: head and shoulders, centered, looking at camera.
Background: plain neutral background, studio setting.
{style_positive}"""


def compose_portrait_prompt(
    spec: CharacterPortraitSpec,
    enhancement: Optional[str] = None
) -> tuple[str, str]:
    """
    组装肖像生成 prompt
    
    Args:
        spec: 角色肖像规格
        enhancement: 可选的增强 prompt（用于重试）
        
    Returns:
        (positive_prompt, negative_prompt)
    """
    style = STYLE_PROFILES.get(spec.style_profile, STYLE_PROFILES["A"])
    
    # 性别映射
    gender_map = {
        "female": "a woman",
        "male": "a man",
        "unknown": "a person"
    }
    gender_str = gender_map.get(spec.gender, "a person")
    
    # 年龄映射
    age_map = {
        "teen": "teenage",
        "young_adult": "young adult",
        "adult": "adult",
        "middle_aged": "middle-aged",
        "elder": "elderly"
    }
    age_str = age_map.get(spec.age_range, "adult")
    
    # 配饰子句
    accessory_clause = ""
    if spec.accessory and spec.accessory.lower() != "none":
        accessory_clause = f", with {spec.accessory}"
    
    # 组装正向 prompt
    positive = PORTRAIT_TEMPLATE.format(
        gender=gender_str,
        age_range=age_str,
        hair=spec.hair,
        outfit=spec.outfit,
        accessory_clause=accessory_clause,
        style_positive=style["positive"]
    )
    
    # 添加增强（重试时用）
    if enhancement:
        positive = f"{positive}, {enhancement}"
    
    # 添加 notes
    if spec.notes:
        positive = f"{positive}, {spec.notes}"
    
    # 负向 prompt
    negative = style["negative"]
    
    return positive.strip(), negative.strip()


def get_generation_params(
    spec: CharacterPortraitSpec,
    size: tuple[int, int] = (512, 512),
    seed: Optional[int] = None
) -> dict:
    """
    获取图像生成参数
    
    Returns:
        ComfyUI / API 通用的生成参数字典
    """
    positive, negative = compose_portrait_prompt(spec)
    
    return {
        "positive_prompt": positive,
        "negative_prompt": negative,
        "width": size[0],
        "height": size[1],
        "seed": seed,
        "steps": 25,
        "cfg_scale": 7.0,
        "sampler": "euler_ancestral",
        "scheduler": "normal"
    }
